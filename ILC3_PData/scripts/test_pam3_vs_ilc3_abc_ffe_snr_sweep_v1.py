import numpy as np
import os
from datetime import datetime

"""
PAM3 vs ILC3_0c_gp on channels a/b/c with AWGN+ISI+FFE, SNR sweep

- 채널 a/b/c: 5-tap ISI (사용자 정의)
- 스킴 1: PAM3 (심볼 {-1,0,+1})
- 스킴 2: ILC3_0c_gp (2샘플 코드워드)
- RX 모드: raw, FFE 2가지 모두 계산하지만
    * 타깃 BER 기준 SNR 비교는 FFE 기준으로 수행

- 기능:
    * SNR 범위를 8~36 dB, 0.5 dB 간격으로 스윕
    * 각 채널(a/b/c)에서 PAM3/ILC3의 FFE BER 곡선 계산
    * 타깃 BER 리스트(예: 5e-2, 2e-2, 1e-2, 5e-3)에 대해
        - BER_FFE <= target 이 되는 최소 SNR (PAM3, ILC3 각각) 탐색
        - ΔSNR = SNR(PAM3) - SNR(ILC3) 계산
    * 콘솔 출력 + CSV 2종 저장:
        1) full curve: channel,scheme,snr_db,acc_raw,ber_raw,acc_ffe,ber_ffe
        2) threshold: channel,target_ber,snr_pam3,snr_ilc3,delta_snr
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


def design_ffe_ls_1d(r: np.ndarray, x: np.ndarray, L_ffe: int):
    """
    1D LS 기반 FFE 설계 (ridge regularization + 안정성 보강 + λ 자동 선택).

    - r: 채널+AWGN 이후 수신 샘플 시퀀스
    - x: 타깃 시퀀스 (PAM3 심볼 또는 ILC3 코드워드)
    - L_ffe: FFE 탭 길이
    """
    r = np.asarray(r, dtype=float)
    x = np.asarray(x, dtype=float)
    assert len(r) == len(x), "r, x 길이는 동일해야 함"

    M = len(x) - L_ffe + 1
    if M <= 0:
        raise ValueError("L_ffe 가 시퀀스 길이보다 너무 큼")

    # Toeplitz 형태의 입력 행렬 R 구성
    R = np.zeros((M, L_ffe), dtype=float)
    for i in range(M):
        R[i, :] = r[i : i + L_ffe]

    # 타깃 시퀀스 정렬 (출력 정렬을 위해 뒤쪽에 맞춤)
    x_tr = x[L_ffe - 1 : L_ffe - 1 + M]

    # 공통 항목 미리 계산
    RtR = R.T @ R
    Rtx = R.T @ x_tr

    tr = float(np.trace(RtR))
    base = tr / max(L_ffe, 1)
    if base <= 0 or not np.isfinite(base):
        base = 1.0

    # 여러 λ 후보에 대해 MSE 최소가 되는 것을 선택
    lam_scales = (1e-5, 1e-4, 1e-3, 1e-2)
    best_w = None
    best_eq = None
    best_mse = np.inf

    for scale in lam_scales:
        lam = scale * base
        if not np.isfinite(lam) or lam <= 0:
            continue

        A = RtR + lam * np.eye(L_ffe, dtype=float)
        b = Rtx

        try:
            w = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            w, *_ = np.linalg.lstsq(R, x_tr, rcond=None)

        # 가중치 벡터 안정성 체크
        if not np.all(np.isfinite(w)):
            continue
        w_norm = np.linalg.norm(w)
        if not np.isfinite(w_norm) or w_norm > 1e6:
            continue

        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            eq_out = R @ w

        if not np.all(np.isfinite(eq_out)):
            eq_out = np.nan_to_num(eq_out, nan=0.0, posinf=0.0, neginf=0.0)

        mse = np.mean((eq_out - x_tr) ** 2)
        if mse < best_mse:
            best_mse = mse
            best_w = w
            best_eq = eq_out

    # 모든 λ 후보가 실패한 경우 fallback
    if best_w is None or best_eq is None:
        best_w = np.zeros(L_ffe, dtype=float)
        best_w[(L_ffe - 1) // 2] = 1.0
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            best_eq = R @ best_w
        if not np.all(np.isfinite(best_eq)):
            best_eq = np.nan_to_num(best_eq, nan=0.0, posinf=0.0, neginf=0.0)

    return best_w, best_eq, x_tr


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

    # raw
    x_hat_raw = pam3_slice(r)
    acc_raw = np.mean(x_hat_raw == x)
    ber_raw = 1.0 - acc_raw

    # FFE
    _, eq_out, x_tr = design_ffe_ls_1d(r, x, L_ffe=L_ffe)
    x_hat_ffe = pam3_slice(eq_out)
    acc_ffe = np.mean(x_hat_ffe == x_tr)
    ber_ffe = 1.0 - acc_ffe

    return acc_raw, ber_raw, acc_ffe, ber_ffe


# ------------------------------------------------------------
# ILC3_0c_gp 경로 (2샘플 코드워드)
# ------------------------------------------------------------

ILC3_CODEBOOK = np.array(
    [
        [-1.0, 0.0],  # 0
        [0.0, -1.0],  # 1
        [1.0, 0.0],   # 2
        [0.0, 1.0],   # 3
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
    """메모리리스 디텍션: (samples[2k], samples[2k+1]) vs 코드북."""
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

    # 채널 통과
    tx = np.convolve(u, h, mode="full")
    y = add_awgn(tx, snr_db)

    Lh = len(h)
    offset = (Lh - 1) // 2
    r = y[offset : offset + len(u)]

    # raw / FFE 공통 유효 심볼 범위
    k_start = (L_ffe - 1) // 2
    k_end = N_sym - 1

    # raw
    acc_raw, ber_raw = ilc3_detect_from_stream(r, sym_idx, k_start, k_end)

    # FFE: 샘플 도메인에서 u를 타겟으로 LS
    _, eq_out, u_tr = design_ffe_ls_1d(r, u, L_ffe=L_ffe)

    errors_eq = 0
    total_eq = 0
    for k in range(k_start, k_end + 1):
        p0 = 2 * k
        p1 = 2 * k + 1
        idx0 = p0 - (L_ffe - 1)
        idx1 = p1 - (L_ffe - 1)
        if idx0 < 0 or idx1 >= len(eq_out):
            continue
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
# 메인 루틴: SNR sweep + 타깃 BER 기준 ΔSNR 계산
# ------------------------------------------------------------

def main():
    N_sym = 50000           # 필요시 100000 등으로 조정 가능
    snr_min = 8.0
    snr_max = 36.0
    snr_step = 0.5
    SNR_dBs = np.arange(snr_min, snr_max + 1e-9, snr_step)

    target_bers = [5e-2, 2e-2, 1e-2, 5e-3]  # 느슨~엄격 4단계 타깃 BER

    # PAM3 쪽 FFE는 channel-fairness sweep 결과를 반영한 길이 사용
    L_ffe_pam3_map = {
        "a": 9,   # 채널 a: fairness sweep에서 L=9 최고
        "b": 15,  # 채널 b: L=15
        "c": 11,  # 채널 c: L=11
    }
    # ILC3_0c_gp: fairness sweep 결과를 반영한 탭 길이
    L_ffe_ilc3_map = {
        "a": 5,
        "b": 5,
        "c": 9,
    }

    channels = {
        "a": np.array([0.10, 0.40, 1.0, 0.40, 0.10], dtype=float),
        "b": np.array([0.05, 0.50, 1.0, 0.50, 0.05], dtype=float),
        "c": np.array([0.075, 0.45, 1.0, 0.45, 0.075], dtype=float),
    }

    print("PAM3 vs ILC3_0c_gp on channels a/b/c (AWGN+ISI + FFE, SNR sweep)")
    print(f"N_sym      = {N_sym}")
    print(f"SNR range  = {snr_min} .. {snr_max} dB (step {snr_step} dB)")
    print(f"target BER = {target_bers}")
    print("Channels:")
    for name, h in channels.items():
        print(f"  {name}: {h}")

    full_rows = []       # full curve CSV 용
    threshold_rows = []  # target BER 기준 ΔSNR 요약

    for ch_name in ["a", "b", "c"]:
        h = channels[ch_name]
        L_ffe_pam3 = L_ffe_pam3_map[ch_name]
        L_ffe_ilc3 = L_ffe_ilc3_map[ch_name]

        print(f"\n=== Channel {ch_name} ===")
        print(f"h = {h}")
        print(f"  FFE lengths: PAM3 L={L_ffe_pam3}, ILC3 L={L_ffe_ilc3}")

        pam3_snr_list = []
        pam3_ber_ffe_list = []
        ilc3_snr_list = []
        ilc3_ber_ffe_list = []

        for snr_db in SNR_dBs:
            # PAM3
            acc_raw_p, ber_raw_p, acc_ffe_p, ber_ffe_p = run_pam3_single(
                h, snr_db, N_sym=N_sym, L_ffe=L_ffe_pam3
            )
            full_rows.append(
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
            pam3_snr_list.append(snr_db)
            pam3_ber_ffe_list.append(ber_ffe_p)

            # ILC3
            acc_raw_i, ber_raw_i, acc_ffe_i, ber_ffe_i = run_ilc3_single(
                h, snr_db, N_sym=N_sym, L_ffe=L_ffe_ilc3
            )
            full_rows.append(
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
            ilc3_snr_list.append(snr_db)
            ilc3_ber_ffe_list.append(ber_ffe_i)

        pam3_snr_arr = np.array(pam3_snr_list, dtype=float)
        pam3_ber_arr = np.array(pam3_ber_ffe_list, dtype=float)
        ilc3_snr_arr = np.array(ilc3_snr_list, dtype=float)
        ilc3_ber_arr = np.array(ilc3_ber_ffe_list, dtype=float)

        for target in target_bers:
            # PAM3: BER_FFE <= target 인 최소 SNR 탐색
            idx_p = np.where(pam3_ber_arr <= target)[0]
            snr_pam3 = float(pam3_snr_arr[idx_p[0]]) if idx_p.size > 0 else np.nan

            # ILC3: BER_FFE <= target 인 최소 SNR 탐색
            idx_i = np.where(ilc3_ber_arr <= target)[0]
            snr_ilc3 = float(ilc3_snr_arr[idx_i[0]]) if idx_i.size > 0 else np.nan

            if np.isfinite(snr_pam3) and np.isfinite(snr_ilc3):
                delta = snr_pam3 - snr_ilc3
            else:
                delta = np.nan

            threshold_rows.append(
                (
                    ch_name,
                    target,
                    snr_pam3,
                    snr_ilc3,
                    delta,
                )
            )

            print(
                f"[target BER={target:.1e}] ch={ch_name}  "
                f"SNR_PAM3={snr_pam3:.2f} dB,  SNR_ILC3={snr_ilc3:.2f} dB,  "
                f"ΔSNR(PAM3-ILC3)={delta:.2f} dB"
            )

    # 결과 CSV 저장
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    full_path = os.path.join(results_dir, f"pam3_vs_ilc3_abc_ffe_snr_sweep_full_{ts}.csv")
    thr_path = os.path.join(results_dir, f"pam3_vs_ilc3_abc_ffe_snr_threshold_{ts}.csv")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write("channel,scheme,snr_db,acc_raw,ber_raw,acc_ffe,ber_ffe\n")
        for ch_name, scheme, snr_db, acc_r, ber_r, acc_e, ber_e in full_rows:
            f.write(
                f"{ch_name},{scheme},{snr_db:.2f},"
                f"{acc_r:.6f},{ber_r:.6f},{acc_e:.6f},{ber_e:.6f}\n"
            )

    with open(thr_path, "w", encoding="utf-8") as f:
        f.write("channel,target_ber,snr_pam3,snr_ilc3,delta_snr\n")
        for ch_name, target, snr_p, snr_i, delta in threshold_rows:
            f.write(
                f"{ch_name},{target:.1e},"
                f"{snr_p if np.isfinite(snr_p) else 'nan'},"
                f"{snr_i if np.isfinite(snr_i) else 'nan'},"
                f"{delta if np.isfinite(delta) else 'nan'}\n"
            )

    print(f"\n[WRITE] full curve   -> {full_path}")
    print(f"[WRITE] thresholds   -> {thr_path}")


if __name__ == "__main__":
    main()