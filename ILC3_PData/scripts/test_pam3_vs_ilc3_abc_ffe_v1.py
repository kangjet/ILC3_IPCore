import numpy as np
import os
from datetime import datetime

"""\nPAM3 vs ILC3_0c_gp on channels a/b/c with AWGN+ISI and FFE

- 채널 a/b/c: 5-tap ISI (사용자 정의)
- 스킴 1: PAM3 (심볼 {-1,0,+1})
- 스킴 2: ILC3_0c_gp (2샘플 코드워드)
- RX 2가지 모드:
    1) raw  : 메모리리스 slicer (기존 베이스라인과 유사)
    2) +FFE : 선형 등화기(LS 기반) 적용 후 slicer

- 출력:
    * 콘솔: 채널/스킴/SNR별 raw vs FFE acc/ber 비교
    * CSV : results/pam3_vs_ilc3_abc_ffe_YYYY-MM-DD_HH-MM-SS.csv
"""

np.random.seed(1234)

# ------------------------------------------------------------
# 공통 유틸
# ------------------------------------------------------------

def add_awgn(x: np.ndarray, snr_db: float) -> np.ndarray:
    """실수 신호 x 에 SNR_dB 기준 AWGN 추가.
    SNR은 신호 평균전력 / 노이즈전력 기준.
    """
    x = np.asarray(x, dtype=float)
    p_sig = np.mean(x ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_var = p_sig / snr_lin
    noise = np.sqrt(noise_var) * np.random.randn(*x.shape)
    return x + noise


def design_ffe_ls_1d(r: np.ndarray, x: np.ndarray, L_ffe: int):
    """1D LS 기반 FFE 설계.

    r: 등화 전 샘플 (len(r) == len(x))
    x: 타겟 심볼(또는 타겟 샘플)
    L_ffe: FFE tap 길이

    반환:
        w      : (L_ffe,) FFE 계수
        eq_out : R @ w  (길이 M = len(x) - L_ffe + 1)
        x_tr   : eq_out 와 정렬된 타겟 시퀀스 (길이 M)
    """
    r = np.asarray(r, dtype=float)
    x = np.asarray(x, dtype=float)
    assert len(r) == len(x), "r, x 길이는 동일해야 함"

    M = len(x) - L_ffe + 1
    if M <= 0:
        raise ValueError("L_ffe 가 시퀀스 길이보다 너무 큼")

    # Toeplitz-like 행렬 구성
    R = np.zeros((M, L_ffe), dtype=float)
    for i in range(M):
        R[i, :] = r[i : i + L_ffe]

    # 타겟 시퀀스 정렬 (기존과 동일)
    x_tr = x[L_ffe - 1 : L_ffe - 1 + M]

    # --------------------------------------------------------
    # Ridge-regularized LS: (R^T R + lambda I) w = R^T x_tr
    # RtR / Rtp 계산 시 경고 억제 + NaN/inf 치환
    # --------------------------------------------------------
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        RtR = R.T @ R
        Rtp = R.T @ x_tr

    RtR = np.nan_to_num(RtR, nan=0.0, posinf=0.0, neginf=0.0)
    Rtp = np.nan_to_num(Rtp, nan=0.0, posinf=0.0, neginf=0.0)

    # 채널 상태에 따라 스케일이 달라지지 않도록 trace 기반으로 lambda 스케일링
    tr = float(np.trace(RtR))
    base = tr / max(L_ffe, 1)
    if base <= 0 or not np.isfinite(base):
        base = 1.0
    lam = 1e-3 * base  # 살짝 더 강한 regularization

    A = RtR + lam * np.eye(L_ffe, dtype=float)
    b = Rtp

    # 1차 시도: 정규화된 normal equation 해
    try:
        w = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        # singular 등 예외 발생 시, 직접 R 에 대해 최소제곱 해 구하기
        w, *_ = np.linalg.lstsq(R, x_tr, rcond=None)

    # 혹시라도 수치 불안정으로 inf/NaN 또는 과도하게 큰 계수가 나오면 안전한 fallback 사용
    need_fallback = False
    if not np.all(np.isfinite(w)):
        need_fallback = True
    else:
        # 계수 노름이 비정상적으로 큰 경우도 fallback
        w_norm = np.linalg.norm(w)
        if not np.isfinite(w_norm) or w_norm > 1e6:
            need_fallback = True

    if need_fallback:
        # fallback 1: R 에 대한 최소제곱 해
        w_ls, *_ = np.linalg.lstsq(R, x_tr, rcond=None)
        if np.all(np.isfinite(w_ls)):
            w_norm_ls = np.linalg.norm(w_ls)
            if np.isfinite(w_norm_ls) and w_norm_ls <= 1e6:
                w = w_ls
            else:
                # 계수가 여전히 비정상적으로 크면 중앙 탭 1.0, 나머지 0 필터 사용
                w = np.zeros(L_ffe, dtype=float)
                w[(L_ffe - 1) // 2] = 1.0
        else:
            # fallback 2: 중앙 탭 1.0, 나머지 0 인 단순 지연 필터
            w = np.zeros(L_ffe, dtype=float)
            w[(L_ffe - 1) // 2] = 1.0

    # eq_out 계산 시 overflow/invalid 경고 억제 및 후처리
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        eq_out = R @ w

    # 만약 eq_out 안에 NaN/inf 가 섞여 있으면 안전한 값으로 치환
    if not np.all(np.isfinite(eq_out)):
        eq_out = np.nan_to_num(eq_out, nan=0.0, posinf=0.0, neginf=0.0)

    return w, eq_out, x_tr


# ------------------------------------------------------------
# PAM3 경로
# ------------------------------------------------------------

PAM3_LEVELS = np.array([-1.0, 0.0, 1.0], dtype=float)


def pam3_generate_symbols(N_sym: int):
    idx = np.random.randint(0, 3, size=N_sym)
    return PAM3_LEVELS[idx], idx


def pam3_slice(y: np.ndarray) -> np.ndarray:
    """PAM3 slicer: y 를 {-1,0,1} 중 가장 가까운 값으로 양자화."""
    y = y.reshape(-1, 1)
    d2 = (y - PAM3_LEVELS.reshape(1, -1)) ** 2
    idx_hat = np.argmin(d2, axis=1)
    return PAM3_LEVELS[idx_hat]


def run_pam3_single(h: np.ndarray, snr_db: float, N_sym: int, L_ffe: int):
    """하나의 채널 h, 하나의 SNR에서 PAM3 raw vs FFE 수행."""
    h = np.asarray(h, dtype=float)

    x, _ = pam3_generate_symbols(N_sym)

    # 채널 통과
    tx = np.convolve(x, h, mode="full")
    y = add_awgn(tx, snr_db)

    # 심볼 타이밍 샘플링 (채널 중심 탭 기준)
    Lh = len(h)
    offset = (Lh - 1) // 2
    r = y[offset : offset + N_sym]

    # --- raw 디텍션 ---
    x_hat_raw = pam3_slice(r)
    acc_raw = np.mean(x_hat_raw == x)
    ber_raw = 1.0 - acc_raw

    # --- FFE 설계 + 디텍션 ---
    w, eq_out, x_tr = design_ffe_ls_1d(r, x, L_ffe=L_ffe)
    x_hat_ffe = pam3_slice(eq_out)
    acc_ffe = np.mean(x_hat_ffe == x_tr)
    ber_ffe = 1.0 - acc_ffe

    return acc_raw, ber_raw, acc_ffe, ber_ffe


# ------------------------------------------------------------
# ILC3_0c_gp 경로 (2샘플 코드워드)
# ------------------------------------------------------------

# 코드북: 0->[-1,0], 1->[0,-1], 2->[+1,0], 3->[0,+1]
ILC3_CODEBOOK = np.array(
    [
        [-1.0, 0.0],
        [0.0, -1.0],
        [1.0, 0.0],
        [0.0, 1.0],
    ],
    dtype=float,
)


def ilc3_generate_symbols(N_sym: int):
    sym_idx = np.random.randint(0, 4, size=N_sym)
    return sym_idx


def ilc3_encode(sym_idx: np.ndarray) -> np.ndarray:
    """심볼 인덱스(0..3)를 2샘플 코드 시퀀스로 변환."""
    N_sym = len(sym_idx)
    u = np.zeros(2 * N_sym, dtype=float)
    for k in range(N_sym):
        u[2 * k : 2 * k + 2] = ILC3_CODEBOOK[sym_idx[k]]
    return u


def ilc3_detect_from_stream(samples: np.ndarray, sym_idx: np.ndarray, k_start: int, k_end: int):
    """메모리리스 디텍션: (samples[2k], samples[2k+1])를 코드북과 거리 비교."""
    errors = 0
    total = 0

    for k in range(k_start, k_end + 1):
        p0 = 2 * k
        p1 = 2 * k + 1
        v = np.array([samples[p0], samples[p1]], dtype=float)
        d2 = np.sum((ILC3_CODEBOOK - v.reshape(1, -1)) ** 2, axis=1)
        dec = int(np.argmin(d2))
        if dec != int(sym_idx[k]):
            errors += 1
        total += 1

    acc = 1.0 - errors / total
    ber = errors / total
    return acc, ber


def run_ilc3_single(h: np.ndarray, snr_db: float, N_sym: int, L_ffe: int):
    """하나의 채널 h, 하나의 SNR에서 ILC3_0c_gp raw vs FFE 수행."""
    h = np.asarray(h, dtype=float)

    sym_idx = ilc3_generate_symbols(N_sym)
    u = ilc3_encode(sym_idx)  # 길이 2*N_sym

    # 채널 통과 (샘플 도메인)
    tx = np.convolve(u, h, mode="full")
    y = add_awgn(tx, snr_db)

    Lh = len(h)
    offset = (Lh - 1) // 2
    # u 길이에 맞춰 중심 정렬
    r = y[offset : offset + len(u)]

    # raw / FFE 모두에서 공통으로 사용할 유효 심볼 범위
    # FFE 설계에서 eq_out[i]는 u[L_ffe-1 + i]에 매칭되므로,
    # sample index n 에 대한 eq_out index는 n - (L_ffe-1).
    k_start = (L_ffe - 1) // 2
    k_end = N_sym - 1

    # --- raw 디텍션 ---
    acc_raw, ber_raw = ilc3_detect_from_stream(r, sym_idx, k_start, k_end)

    # --- FFE 설계 (샘플 도메인에서 u를 타겟으로 LS) ---
    w, eq_out, u_tr = design_ffe_ls_1d(r, u, L_ffe=L_ffe)

    # eq_out[i] ~ u[L_ffe-1 + i] 에 정렬되어 있음
    # sample index n 는 eq_out index (n - (L_ffe-1))에 해당

    # 유효 영역 내에서만 디텍션
    errors_eq = 0
    total_eq = 0

    for k in range(k_start, k_end + 1):
        p0 = 2 * k
        p1 = 2 * k + 1

        idx0 = p0 - (L_ffe - 1)
        idx1 = p1 - (L_ffe - 1)
        if idx0 < 0 or idx1 >= len(eq_out):
            continue  # 안전장치 (이론상 발생하지 않아야 함)

        v = np.array([eq_out[idx0], eq_out[idx1]], dtype=float)
        d2 = np.sum((ILC3_CODEBOOK - v.reshape(1, -1)) ** 2, axis=1)
        dec = int(np.argmin(d2))
        if dec != int(sym_idx[k]):
            errors_eq += 1
        total_eq += 1

    acc_ffe = 1.0 - errors_eq / total_eq
    ber_ffe = errors_eq / total_eq

    return acc_raw, ber_raw, acc_ffe, ber_ffe


# ------------------------------------------------------------
# 메인 루틴
# ------------------------------------------------------------

def main():
    N_sym = 50000
    SNR_dBs = [10.0, 13.0, 16.0, 19.0, 22.0, 25.0]
    L_ffe_pam3 = 11  # 공통 FFE 길이 (fairness: PAM3/ILC3 동일)
    L_ffe_ilc3 = 11  # 공통 FFE 길이 (fairness: PAM3/ILC3 동일)

    # 채널 정의 (사용자 정의 a/b/c)
    channels = {
        "a": np.array([0.10, 0.40, 1.0, 0.40, 0.10], dtype=float),    # 가장 깨끗한 채널
        "b": np.array([0.05, 0.50, 1.0, 0.50, 0.05], dtype=float),    # ISI 가장 강한 채널
        "c": np.array([0.075, 0.45, 1.0, 0.45, 0.075], dtype=float),  # 중간 강도 채널
    }

    print("PAM3 vs ILC3_0c_gp on channels a/b/c (AWGN+ISI + FFE)")
    print(f"N_sym = {N_sym}")
    print("Channels:")
    for name, h in channels.items():
        print(f"  {name}: {h}")

    rows = []  # CSV 저장용

    for ch_name in ["a", "b", "c"]:
        h = channels[ch_name]
        print(f"\n=== Channel {ch_name} ===")
        print(f"h = {h}")

        for snr_db in SNR_dBs:
            # PAM3
            acc_raw_p, ber_raw_p, acc_ffe_p, ber_ffe_p = run_pam3_single(
                h, snr_db, N_sym=N_sym, L_ffe=L_ffe_pam3
            )
            print(
                f"PAM3       ch={ch_name}  SNR={snr_db:.1f} dB  "
                f"raw_acc={acc_raw_p:.6f} raw_ber={ber_raw_p:.6f}  "
                f"FFE_acc={acc_ffe_p:.6f} FFE_ber={ber_ffe_p:.6f}"
            )
            rows.append(
                (
                    ch_name,
                    "PAM3",
                    snr_db,
                    acc_raw_p,
                    ber_raw_p,
                    acc_ffe_p,
                    ber_ffe_p,
                )
            )

            # ILC3_0c_gp
            acc_raw_i, ber_raw_i, acc_ffe_i, ber_ffe_i = run_ilc3_single(
                h, snr_db, N_sym=N_sym, L_ffe=L_ffe_ilc3
            )
            print(
                f"ILC3_0c_gp  ch={ch_name}  SNR={snr_db:.1f} dB  "
                f"raw_acc={acc_raw_i:.6f} raw_ber={ber_raw_i:.6f}  "
                f"FFE_acc={acc_ffe_i:.6f} FFE_ber={ber_ffe_i:.6f}"
            )
            rows.append(
                (
                    ch_name,
                    "ILC3_0c_gp",
                    snr_db,
                    acc_raw_i,
                    ber_raw_i,
                    acc_ffe_i,
                    ber_ffe_i,
                )
            )

    # 결과 CSV로 저장
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = os.path.join(results_dir, f"pam3_vs_ilc3_abc_ffe_{ts}.csv")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("channel,scheme,snr_db,acc_raw,ber_raw,acc_ffe,ber_ffe\n")
        for ch_name, scheme, snr_db, acc_r, ber_r, acc_e, ber_e in rows:
            f.write(
                f"{ch_name},{scheme},{snr_db:.1f},{acc_r:.6f},{ber_r:.6f},{acc_e:.6f},{ber_e:.6f}\n"
            )

    print(f"\n[WRITE] {out_path}")


if __name__ == "__main__":
    main()