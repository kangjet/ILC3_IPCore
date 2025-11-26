#!/usr/bin/env python
import numpy as np

# ... 기존 유틸 (pam3, ilc3, apply_channel, add_awgn 등) 위/아래 어디든 OK

def train_ffe_ls(y, d, L_ffe=7, ridge=1e-4):
    """
    y : 채널+노이즈 출력 (1D)
    d : desired 파형 (1D, y와 같은 길이에서 align)
    L_ffe : FFE tap 수
    ridge : 정규화 (작은 값, 예: 1e-4)

    (R^T R + ridge I)^{-1} R^T d 형태의 LS FFE 학습
    """
    N = len(d)
    half = L_ffe // 2

    rows = []
    tgt = []
    for n in range(half, N - half):
        rows.append(y[n-half:n+half+1])
        tgt.append(d[n])

    if len(rows) == 0:
        return np.zeros(L_ffe, dtype=float)

    R = np.array(rows)    # [M, L_ffe]
    p = np.array(tgt)     # [M]

    RtR = R.T @ R
    Rtp = R.T @ p

    A = RtR + ridge * np.eye(L_ffe)
    try:
        w = np.linalg.solve(A, Rtp)
    except np.linalg.LinAlgError:
        w, *_ = np.linalg.lstsq(A, Rtp, rcond=None)

    return w

def apply_ffe(y, w):
    """간단 FIR 적용 (same 모드)"""
    return np.convolve(y, w[::-1], mode="same")

# --- 공통 유틸 (기존 스크립트에서 그대로 가져오면 됨) ---

def pam3_symbols(N):
    s = np.random.randint(0, 3, size=N)
    levels = np.array([-1.0, 0.0, 1.0])
    x = levels[s]
    # 평균 에너지 1로 정규화 (기존과 맞춰야 하면 그대로 맞추기)
    Es = np.mean(x**2)
    x = x / np.sqrt(Es)
    return x, s

def apply_channel(x, h):
    y = np.convolve(x, h, mode="full")
    return y

def add_awgn(y, snr_db):
    Es = np.mean(np.abs(y)**2)
    snr_lin = 10.0**(snr_db / 10.0)
    N0 = Es / snr_lin
    sigma2 = N0 / 2.0
    noise = np.sqrt(sigma2) * (np.random.randn(*y.shape))
    return y + noise

def pam3_slicer(z):
    # 단순 3-level slicer
    out = np.zeros_like(z)
    out[z > 0.5] = 1.0
    out[(z <= 0.5) & (z >= -0.5)] = 0.0
    out[z < -0.5] = -1.0
    return out

def pam3_detect(z):
    z_hat = pam3_slicer(z)
    # 다시 심볼 index로
    levels = np.array([-1.0, 0.0, 1.0])
    # 각 샘플에 대해 가장 가까운 레벨 index 선택
    idx = np.argmin(np.abs(z_hat[..., None] - levels[None, ...]), axis=-1)
    return idx


# --- 채널 정의 ---

h_a = np.array([0.10, 0.40, 1.0, 0.40, 0.10])
h_b = np.array([0.05, 0.50, 1.0, 0.50, 0.05])
h_c = np.array([0.075, 0.45, 1.0, 0.45, 0.075])

channels = {
    "a": h_a,
    "b": h_b,
    "c": h_c,
}

# --- 메인 실험 루프 ---

def run_fairness_test():
    N_sym = 50000
    snr_list = [16.0, 19.0, 22.0, 25.0]
    L_list = [5, 7, 9, 11, 15]
    ridge_list = [1e-5, 1e-4, 1e-3, 1e-2]

    print("PAM3 FFE fairness sweep (channels a/b/c)")
    print(f"N_sym={N_sym}")
    print(f"SNR list={snr_list}")
    print(f"L_ffe list={L_list}")
    print(f"ridge list={ridge_list}")
    print("")

    for ch_name, h in channels.items():
        print(f"=== Channel {ch_name} ===")
        print(f"h = {h}")
        for snr_db in snr_list:
            # TX 생성
            x, s = pam3_symbols(N_sym)
            # 채널 + AWGN
            y = apply_channel(x, h)
            y_noisy = add_awgn(y, snr_db)

            # raw 기준 (중심 샘플만 간단히 사용)
            # 심볼 타이밍 정렬 (대략 h의 중앙 tap 기준)
            delay = len(h) // 2
            z_raw = y_noisy[delay:delay + N_sym]
            s_hat_raw = pam3_detect(z_raw)
            acc_raw = np.mean(s_hat_raw == s)
            ber_raw = 1.0 - acc_raw

            print(f"SNR={snr_db:4.1f} dB  raw_acc={acc_raw:.6f} raw_ber={ber_raw:.6f}")

            # FFE 스윕
            best_ber = 1.0
            best_cfg = None

            for L_ffe in L_list:
                for ridge in ridge_list:
                    # desired d[n] = 채널 없는 이상 출력 (TX x를 delay만큼 align)
                    # 아주 단순하게 x를 그대로 d로 쓰되 길이만 y_noisy와 맞춰 사용
                    d = np.zeros_like(y_noisy)
                    d[delay:delay + N_sym] = x[:len(d) - delay]

                    w = train_ffe_ls(y_noisy, d, L_ffe=L_ffe, ridge=ridge)
                    z_eq = apply_ffe(y_noisy, w)
                    z_eq_sym = z_eq[delay:delay + N_sym]
                    s_hat_eq = pam3_detect(z_eq_sym)
                    acc_eq = np.mean(s_hat_eq == s)
                    ber_eq = 1.0 - acc_eq

                    if ber_eq < best_ber:
                        best_ber = ber_eq
                        best_cfg = (L_ffe, ridge, acc_eq)

            if best_cfg is not None:
                L_best, ridge_best, acc_best = best_cfg
                print(
                    f"  -> best FFE (L={L_best}, ridge={ridge_best:.0e}) "
                    f"acc={acc_best:.6f} ber={best_ber:.6f}"
                )
        print("")

if __name__ == "__main__":
    run_fairness_test()