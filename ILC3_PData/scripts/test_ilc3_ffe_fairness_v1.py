import numpy as np
import os
from datetime import datetime

"""
ILC3_0c_gp FFE fairness sweep (channels a/b/c)

- 목적:
  * ILC3_0c_gp에 대해서도 FFE 탭 길이(L_ffe)와 ridge(정규화)를 스윕해서
    채널 a/b/c + 여러 SNR에서 "최적 FFE 설정"을 찾는다.
  * PAM3 FFE fairness 결과와 대칭되는 실험.

- 환경:
  * 채널 a/b/c: 5-tap ISI
  * 스킴: ILC3_0c_gp (2샘플 코드워드)
  * 노이즈: AWGN
  * SNR 리스트: [16, 19, 22, 25] dB (필요시 수정)
  * L_ffe 리스트: [5, 7, 9, 11, 15]
  * ridge 리스트: [1e-5, 1e-4, 1e-3, 1e-2]
  * 각 (채널, SNR)에 대해:
      - raw BER 1개
      - (L_ffe, ridge) 조합 중 BER 최소가 되는 설정 1개 선택
"""

np.random.seed(1234)


# ------------------------------------------------------------
# 공통 유틸
# ------------------------------------------------------------

def add_awgn(x: np.ndarray, snr_db: float) -> np.ndarray:
    """실수 신호 x 에 SNR_dB 기준 AWGN 추가."""
    x = np.asarray(x, dtype=float)
    p_sig = np.mean(x ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_var = p_sig / snr_lin
    noise = np.sqrt(noise_var) * np.random.randn(*x.shape)
    return x + noise


def design_ffe_ls_1d(r: np.ndarray, x: np.ndarray, L_ffe: int, ridge: float):
    """
    1D LS 기반 FFE 설계
      - 입력 r: 채널 출력 시퀀스 (equalizer 입력)
      - 타겟 x: 이상적인 시퀀스 (PAM3나 ILC3 코드 시퀀스 등)
      - L_ffe: FFE 탭 길이
      - ridge: 정규화 스케일 (예: 1e-5, 1e-4, 1e-3, 1e-2)

    (R^T R + lambda I) w = R^T x_tr
    lambda = ridge * base, base는 trace(R^T R)/L_ffe
    """
    r = np.asarray(r, dtype=float)
    x = np.asarray(x, dtype=float)
    assert len(r) == len(x), "r, x 길이는 동일해야 함"

    M = len(x) - L_ffe + 1
    if M <= 0:
        raise ValueError("L_ffe 가 시퀀스 길이보다 너무 큼")

    R = np.zeros((M, L_ffe), dtype=float)
    for i in range(M):
        R[i, :] = r[i : i + L_ffe]

    # 타겟 시퀀스 정렬
    x_tr = x[L_ffe - 1 : L_ffe - 1 + M]

    # Ridge-regularized LS: (R^T R + lambda I) w = R^T x_tr
    RtR = R.T @ R
    tr = float(np.trace(RtR))
    base = tr / max(L_ffe, 1)
    if base <= 0 or not np.isfinite(base):
        base = 1.0

    lam = float(ridge) * base

    A = RtR + lam * np.eye(L_ffe, dtype=float)
    b = R.T @ x_tr

    try:
        w = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        w, *_ = np.linalg.lstsq(R, x_tr, rcond=None)

    need_fallback = False
    if not np.all(np.isfinite(w)):
        need_fallback = True
    else:
        w_norm = np.linalg.norm(w)
        if not np.isfinite(w_norm) or w_norm > 1e6:
            need_fallback = True

    if need_fallback:
        w_ls, *_ = np.linalg.lstsq(R, x_tr, rcond=None)
        if np.all(np.isfinite(w_ls)) and np.linalg.norm(w_ls) <= 1e6:
            w = w_ls
        else:
            # 완전 붕괴 시에는 단위 임펄스 필터로 fallback
            w = np.zeros(L_ffe, dtype=float)
            w[(L_ffe - 1) // 2] = 1.0

    # equalizer 출력 계산 (수치 안정성 옵션)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        eq_out = R @ w
    if not np.all(np.isfinite(eq_out)):
        eq_out = np.nan_to_num(eq_out, nan=0.0, posinf=0.0, neginf=0.0)

    return w, eq_out, x_tr


# ------------------------------------------------------------
# ILC3_0c_gp 경로 (2샘플 코드워드)
# ------------------------------------------------------------

ILC3_CODEBOOK = np.array(
    [
        [-1.0, 0.0],  # 0
        [0.0, -1.0],  # 1
        [1.0,  0.0],  # 2
        [0.0,  1.0],  # 3
    ],
    dtype=float,
)


def ilc3_generate_symbols(N_sym: int):
    """0..3 중 랜덤 심볼 인덱스 생성."""
    sym_idx = np.random.randint(0, 4, size=N_sym)
    return sym_idx


def ilc3_encode(sym_idx: np.ndarray) -> np.ndarray:
    """심볼 인덱스(0..3)를 2샘플 코드 시퀀스로 변환."""
    N_sym = len(sym_idx)
    u = np.zeros(2 * N_sym, dtype=float)
    for k in range(N_sym):
        u[2 * k : 2 * k + 2] = ILC3_CODEBOOK[sym_idx[k]]
    return u


def ilc3_detect_raw(samples: np.ndarray, sym_idx: np.ndarray, L_ffe_ref: int):
    """
    채널 출력 samples(길이 2*N_sym)에 대해 raw detection 수행.
    - L_ffe_ref: FFE 길이를 참조해서 k_start를 맞춰줌
      (FFE와 동일한 유효 심볼 범위를 사용하기 위함)
    """
    N_sym = len(sym_idx)
    k_start = (L_ffe_ref - 1) // 2
    k_end = N_sym - 1

    errors = 0
    total = 0
    for k in range(k_start, k_end + 1):
        p0 = 2 * k
        p1 = 2 * k + 1
        if p1 >= len(samples):
            break
        v = np.array([samples[p0], samples[p1]], dtype=float)
        d2 = np.sum((ILC3_CODEBOOK - v.reshape(1, -1)) ** 2, axis=1)
        dec = int(np.argmin(d2))
        if dec != int(sym_idx[k]):
            errors += 1
        total += 1

    if total == 0:
        return 0.0, 1.0  # degenerate

    acc = 1.0 - errors / total
    ber = errors / total
    return acc, ber


def ilc3_detect_eq(eq_out: np.ndarray, sym_idx: np.ndarray, L_ffe: int):
    """
    FFE 출력 eq_out에 대해 ILC3 코드북 디텍션.
    - eq_out 길이: M = len(u) - L_ffe + 1
    - k 에 대해서:
        p0 = 2k, p1 = 2k+1
        idx0 = p0 - (L_ffe - 1)
        idx1 = p1 - (L_ffe - 1)
      를 사용해서 eq_out에서 샘플을 꺼낸다.
    """
    N_sym = len(sym_idx)
    k_start = (L_ffe - 1) // 2
    k_end = N_sym - 1

    errors = 0
    total = 0
    M = len(eq_out)

    for k in range(k_start, k_end + 1):
        p0 = 2 * k
        p1 = 2 * k + 1
        idx0 = p0 - (L_ffe - 1)
        idx1 = p1 - (L_ffe - 1)
        if idx0 < 0 or idx1 >= M:
            continue
        v = np.array([eq_out[idx0], eq_out[idx1]], dtype=float)
        d2 = np.sum((ILC3_CODEBOOK - v.reshape(1, -1)) ** 2, axis=1)
        dec = int(np.argmin(d2))
        if dec != int(sym_idx[k]):
            errors += 1
        total += 1

    if total == 0:
        return 0.0, 1.0

    acc = 1.0 - errors / total
    ber = errors / total
    return acc, ber


# ------------------------------------------------------------
# 메인: ILC3 FFE fairness sweep
# ------------------------------------------------------------

def main():
    N_sym = 50000
    SNR_list = [16.0, 19.0, 22.0, 25.0]
    L_ffe_list = [5, 7, 9, 11, 15]
    ridge_list = [1e-5, 1e-4, 1e-3, 1e-2]

    channels = {
        "a": np.array([0.10, 0.40, 1.0, 0.40, 0.10], dtype=float),
        "b": np.array([0.05, 0.50, 1.0, 0.50, 0.05], dtype=float),
        "c": np.array([0.075, 0.45, 1.0, 0.45, 0.075], dtype=float),
    }

    print("ILC3_0c_gp FFE fairness sweep (channels a/b/c)")
    print(f"N_sym={N_sym}")
    print(f"SNR list={SNR_list}")
    print(f"L_ffe list={L_ffe_list}")
    print(f"ridge list={ridge_list}\n")

    rows = []  # CSV 저장용: channel, snr_db, raw_acc, raw_ber, best_L, best_ridge, best_acc, best_ber

    for ch_name in ["a", "b", "c"]:
        h = channels[ch_name]
        print(f"=== Channel {ch_name} ===")
        print(f"h = {h}")

        for snr_db in SNR_list:
            # 1) 심볼 + 코드 시퀀스 생성
            sym_idx = ilc3_generate_symbols(N_sym)
            u = ilc3_encode(sym_idx)  # 길이 2*N_sym

            # 2) 채널 + AWGN
            tx = np.convolve(u, h, mode="full")
            y = add_awgn(tx, snr_db)

            # 3) 채널 중심 정렬 (PAM3/ILC3 공통)
            Lh = len(h)
            offset = (Lh - 1) // 2
            r = y[offset : offset + len(u)]  # 길이 ≈ 2*N_sym

            # 4) raw detection (L_ffe_ref는 가장 큰 값 기준)
            L_ref = max(L_ffe_list)
            acc_raw, ber_raw = ilc3_detect_raw(r, sym_idx, L_ffe_ref=L_ref)
            print(f"SNR={snr_db:.1f} dB  raw_acc={acc_raw:.6f} raw_ber={ber_raw:.6f}")

            best_acc = -1.0
            best_ber = 1.0
            best_L = None
            best_ridge = None

            # 5) FFE sweep: (L_ffe, ridge) 조합 탐색
            for L_ffe in L_ffe_list:
                for ridge in ridge_list:
                    try:
                        w, eq_out, u_tr = design_ffe_ls_1d(r, u, L_ffe=L_ffe, ridge=ridge)
                    except Exception as e:
                        # 수치 문제 시 continue
                        # print(f"  [WARN] L={L_ffe} ridge={ridge} -> {e}")
                        continue

                    acc_ffe, ber_ffe = ilc3_detect_eq(eq_out, sym_idx, L_ffe=L_ffe)

                    if acc_ffe > best_acc:
                        best_acc = acc_ffe
                        best_ber = ber_ffe
                        best_L = L_ffe
                        best_ridge = ridge

            print(
                f"  -> best FFE (L={best_L}, ridge={best_ridge}) "
                f"acc={best_acc:.6f} ber={best_ber:.6f}"
            )

            rows.append(
                (
                    ch_name,
                    snr_db,
                    acc_raw,
                    ber_raw,
                    best_L,
                    best_ridge,
                    best_acc,
                    best_ber,
                )
            )

        print("")  # 채널 구분용 빈 줄

    # --------------------------------------------------------
    # CSV 저장
    # --------------------------------------------------------
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = os.path.join(results_dir, f"ilc3_ffe_fairness_{ts}.csv")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(
            "channel,snr_db,raw_acc,raw_ber,"
            "best_L_ffe,best_ridge,best_acc,best_ber\n"
        )
        for ch_name, snr_db, acc_raw, ber_raw, best_L, best_ridge, best_acc, best_ber in rows:
            f.write(
                f"{ch_name},{snr_db:.1f},"
                f"{acc_raw:.6f},{ber_raw:.6f},"
                f"{best_L},{best_ridge},"
                f"{best_acc:.6f},{best_ber:.6f}\n"
            )

    print(f"[WRITE] ILC3 FFE fairness CSV -> {out_path}")


if __name__ == "__main__":
    main()