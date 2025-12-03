#!/usr/bin/env python3
"""
CoPBit Q13 – x16 lanes PAM4 vs CoPBit-M8 Channel-b + FFE + Kuramoto (Eb/N0 basis) v0.1

목표:
- 강 ISI 채널 b에서
  · PAM4 + 채널 + AWGN + FFE(5tap)
  · CoPBit-M8(8-PSK) + 채널 + AWGN + FFE(5tap) + x16 lane Kuramoto 위상 락
  의 BER을 Eb/N0 기준으로 비교하는 멀티레인 실험 스크립트.

주의:
- 채널은 실수 5-tap FIR (b 채널): [0.05, 0.5, 1.0, 0.5, 0.05]
- FFE는 심볼 레이트 LS 기반, 길이 L=ffe_len (기본 5), train_frac 비율만큼의 심볼로 설계
- PAM4는 단일 레인 기준 BER만 계산 (멀티레인 의미가 없기 때문)
- CoPBit-M8은 x16 lanes + 글로벌 위상 드리프트 + Kuramoto 위상 추적으로
  base vs kura 두 가지 BER을 동시에 계산
"""

import argparse
import numpy as np


# -------------------------- 공통 유틸 함수들 --------------------------

def add_awgn_from_ebn0(x, ebn0_db, kbits, rng, complex_valued=False):
    """
    Eb/N0(dB)와 심볼당 비트수(kbits)를 기준으로
    Es/N0를 맞춘 후 AWGN을 추가.

    - x: 실수/복소 심볼 시퀀스 (배열)
    - Eb/N0(dB): ebn0_db
    - kbits: log2(M) (PAM4=2, 8-PSK=3)
    - complex_valued: True면 복소 AWGN, False면 실수 AWGN
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * kbits  # Es/N0 = Eb/N0 * k
    n0 = 1.0 / esn0_lin          # Es = 1 기준 (TX 심볼 에너지)

    if complex_valued:
        sigma = np.sqrt(n0 / 2.0)
        noise = sigma * (rng.standard_normal(size=x.shape) +
                         1j * rng.standard_normal(size=x.shape))
    else:
        sigma = np.sqrt(n0 / 2.0)
        noise = sigma * rng.standard_normal(size=x.shape)

    return x + noise


def solve_ffe_lstsq(y_tr, d_tr, ffe_len):
    """
    심볼 레이트 FFE를 LS로 설계.
    - y_tr: 채널 출력 (noiseless training 구간), shape (N,)
    - d_tr: 타겟 심볼 시퀀스 (원래 송신 심볼), shape (N,)
    - ffe_len: FFE tap 수 (홀수 권장)

    반환:
    - w: FFE 계수, shape (ffe_len,)
    """
    L = ffe_len
    half = L // 2

    y_pad = np.pad(y_tr, (half, half), mode="constant")
    N = len(d_tr)

    # 디자인 매트릭스 (N x L)
    X = np.empty((N, L), dtype=np.complex128 if np.iscomplexobj(d_tr) else np.float64)
    for n in range(N):
        X[n, :] = y_pad[n:n + L]

    # LS 해: X w ≈ d_tr
    w, *_ = np.linalg.lstsq(X, d_tr, rcond=None)
    return w


# -------------------------- PAM4 모뎀 --------------------------

# Gray mapping: idx -> bits
# idx: 0,1,2,3  -> bits: 00,01,11,10
PAM4_IDX2BITS = np.array([[0, 0],
                          [0, 1],
                          [1, 1],
                          [1, 0]], dtype=np.int8)

# bits(Gray) -> idx 매핑용: g = 2*b0 + b1  (00->0, 01->1, 10->2, 11->3)
# g_to_idx[g] = idx
PAM4_G_TO_IDX = np.array([0, 1, 3, 2], dtype=np.int64)

# PAM4 레벨 (평균 에너지 1)
PAM4_LEVELS = np.array([-3, -1, 1, 3], dtype=np.float64) / np.sqrt(5.0)


def pam4_mod(bits):
    """
    bits: shape (N,2), Gray bits (00,01,11,10)
    반환: x: shape (N,), 실수 PAM4 레벨
    """
    g = bits[:, 0] * 2 + bits[:, 1]
    idx = PAM4_G_TO_IDX[g]
    x = PAM4_LEVELS[idx]
    return x, idx


def pam4_demod_levels_to_bits(y):
    """
    실수 입력 y를 PAM4 4레벨에 최근접 매칭 후,
    Gray bit pair로 복원.

    반환:
    - bits_hat: shape (N,2)
    - idx_hat: shape (N,)
    """
    # (N,1) vs (1,4) 브로드캐스트 후 최소거리 인덱스
    diff = y[:, None] - PAM4_LEVELS[None, :]
    idx_hat = np.argmin(diff * diff, axis=1)
    bits_hat = PAM4_IDX2BITS[idx_hat]
    return bits_hat, idx_hat


def design_ffe_pam4(channel_taps, ffe_len, train_frac, n_sym, rng):
    n_tr = max(16, int(train_frac * n_sym))
    bits_tr = rng.integers(0, 2, size=(n_tr, 2), endpoint=False)
    x_tr, _ = pam4_mod(bits_tr)
    # 채널 통과 (noiseless)
    y_tr = np.convolve(x_tr, channel_taps, mode="same")
    # FFE 설계
    w = solve_ffe_lstsq(y_tr, x_tr, ffe_len)
    return w


def simulate_pam4_channel_eq_ber(ebn0_db, n_sym, channel_taps, w_ffe, rng):
    """
    단일 레인 PAM4 + 채널 b + AWGN + FFE(고정 w_ffe)에 대해
    Eb/N0별 pre-FEC BER 계산.
    """
    bits = rng.integers(0, 2, size=(n_sym, 2), endpoint=False)
    x, idx = pam4_mod(bits)
    # 채널 통과
    y = np.convolve(x, channel_taps, mode="same")
    # AWGN (Eb/N0 기준)
    y_noisy = add_awgn_from_ebn0(y, ebn0_db, kbits=2, rng=rng, complex_valued=False)
    # FFE
    y_eq = np.convolve(y_noisy, w_ffe, mode="same")
    # 디코딩
    bits_hat, _ = pam4_demod_levels_to_bits(y_eq)

    bit_errors = np.count_nonzero(bits_hat != bits)
    ber = bit_errors / bits.size
    return ber


# -------------------------- M8 (CoPBit 위상용 8-PSK) 모뎀 --------------------------

M8 = 8
# 바이너리 인덱스 0..7 -> 8-PSK 심볼 (unit circle)
M8_CONST = np.exp(1j * 2.0 * np.pi * np.arange(M8) / M8)


def m8_mod(bits):
    """
    bits: shape (N,3), binary
    반환:
    - x: shape (N,), 8-PSK 심볼 (complex)
    - idx: shape (N,), 0..7
    """
    idx = (bits[:, 0] << 2) | (bits[:, 1] << 1) | bits[:, 2]
    x = M8_CONST[idx]
    return x, idx


def m8_demod_to_bits(y):
    """
    y: shape (N,), complex
    8-PSK 최근접 점으로 디코딩 후, binary bits로 복원.
    """
    # (N,1) vs (1,8)
    diff2 = np.abs(y[:, None] - M8_CONST[None, :]) ** 2
    idx_hat = np.argmin(diff2, axis=1)

    bits_hat = np.zeros((len(idx_hat), 3), dtype=np.int8)
    bits_hat[:, 0] = (idx_hat >> 2) & 1
    bits_hat[:, 1] = (idx_hat >> 1) & 1
    bits_hat[:, 2] = idx_hat & 1
    return bits_hat, idx_hat


def design_ffe_m8(channel_taps, ffe_len, train_frac, n_sym, rng):
    n_tr = max(16, int(train_frac * n_sym))
    bits_tr = rng.integers(0, 2, size=(n_tr, 3), endpoint=False)
    x_tr, _ = m8_mod(bits_tr)
    y_tr = np.convolve(x_tr, channel_taps, mode="same")
    w = solve_ffe_lstsq(y_tr, x_tr, ffe_len)
    return w


# -------------------------- Q13: x16 lanes + EQ + Kuramoto --------------------------

def simulate_m8_xn_eq_kuramoto_ber(
    ebn0_db,
    n_sym,
    n_lanes,
    channel_taps,
    w_ffe_m8,
    drift_std_deg,
    mu_phase,
    rng,
):
    """
    xN lanes 8-PSK (M8) + 채널 b + AWGN + FFE + 글로벌 위상 드리프트 + Kuramoto 위상 추적

    반환:
    - ber_base: Kuramoto 없이, 각 레인을 독립 8-PSK로 디코딩한 BER
    - ber_kura: xN lane Kuramoto 위상 추적 후 디코딩한 BER
    """
    kbits = 3
    # 1) 비트 & 심볼 생성
    bits = rng.integers(0, 2, size=(n_lanes, n_sym, kbits), endpoint=False)
    bits_flat = bits.reshape(-1, kbits)

    x_flat, idx_flat = m8_mod(bits_flat)
    x = x_flat.reshape(n_lanes, n_sym)

    # 2) 채널 통과
    h = channel_taps
    y_ch = np.empty_like(x, dtype=np.complex128)
    for l in range(n_lanes):
        y_ch[l, :] = np.convolve(x[l, :], h, mode="same")

    # 3) AWGN 추가 (Eb/N0 기준)
    y_noisy = add_awgn_from_ebn0(y_ch, ebn0_db, kbits=kbits, rng=rng, complex_valued=True)

    # 4) FFE 적용 (각 레인 동일 계수 w_ffe_m8 사용)
    L = len(w_ffe_m8)
    y_eq = np.empty_like(y_noisy, dtype=np.complex128)
    for l in range(n_lanes):
        y_eq[l, :] = np.convolve(y_noisy[l, :], w_ffe_m8, mode="same")

    # 5) 글로벌 위상 드리프트 생성 및 적용
    drift_std_rad = np.deg2rad(drift_std_deg)
    dphi = drift_std_rad * rng.standard_normal(size=n_sym)
    phi = np.cumsum(dphi)  # phi[0]부터 random walk
    phase_rot = np.exp(1j * phi)[None, :]  # (1, N)

    z = y_eq * phase_rot  # (L, N)

    # 6) Base 디코딩 (Kuramoto 없이)
    # vectorized demod
    z_flat = z.reshape(-1)
    bits_hat_base_flat, _ = m8_demod_to_bits(z_flat)
    bits_hat_base = bits_hat_base_flat.reshape(n_lanes, n_sym, kbits)

    bit_errors_base = np.count_nonzero(bits_hat_base != bits)
    ber_base = bit_errors_base / bits.size

    # 7) Kuramoto 기반 글로벌 위상 추적 + 디코딩
    phi_est = 0.0
    idx_hat_kura = np.empty((n_lanes, n_sym), dtype=np.int64)

    for n in range(n_sym):
        # 현재 추정 위상 제거
        z_n = z[:, n] * np.exp(-1j * phi_est)  # shape (L,)

        # 각 레인 독립 디코딩
        # (L,1) vs (1,8) 브로드캐스트
        diff2 = np.abs(z_n[:, None] - M8_CONST[None, :]) ** 2
        idx_n = np.argmin(diff2, axis=1)  # shape (L,)
        idx_hat_kura[:, n] = idx_n

        # 피드백용 이상 심볼
        s_hat = M8_CONST[idx_n]  # shape(L,)

        # Kuramoto-style 집단 위상 오차 추정
        err_phasor = np.mean(z_n * np.conj(s_hat))
        err = np.angle(err_phasor)

        # 추정 위상 업데이트
        phi_est += mu_phase * err

    # Kuramoto 후 bit 복원
    idx_hat_kura_flat = idx_hat_kura.reshape(-1)
    bits_hat_kura_flat = np.zeros((idx_hat_kura_flat.size, 3), dtype=np.int8)
    bits_hat_kura_flat[:, 0] = (idx_hat_kura_flat >> 2) & 1
    bits_hat_kura_flat[:, 1] = (idx_hat_kura_flat >> 1) & 1
    bits_hat_kura_flat[:, 2] = idx_hat_kura_flat & 1

    bits_hat_kura = bits_hat_kura_flat.reshape(n_lanes, n_sym, kbits)
    bit_errors_kura = np.count_nonzero(bits_hat_kura != bits)
    ber_kura = bit_errors_kura / bits.size

    return ber_base, ber_kura


# -------------------------- main --------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="CoPBit Q13 – x16 lanes PAM4 vs CoPBit-M8 Channel-b + FFE + Kuramoto (Eb/N0 basis) v0.1"
    )
    p.add_argument("--n_sym", type=int, default=200000,
                   help="심볼 수 (lane 당) [기본: 200000]")
    p.add_argument("--n_lanes", type=int, default=16,
                   help="lane 수 [기본: 16]")
    p.add_argument("--ebn0_list", type=str, default="4,6,8,10,12,14,16",
                   help="콤마 구분 Eb/N0 리스트 (dB) [기본: '4,6,8,10,12,14,16']")
    p.add_argument("--drift_std_deg", type=float, default=0.5,
                   help="글로벌 위상 드리프트 1-step 표준편차 (deg) [기본: 0.5]")
    p.add_argument("--mu_phase", type=float, default=0.1,
                   help="Kuramoto 위상 업데이트 스텝 크기 [기본: 0.1]")
    p.add_argument("--ffe_len", type=int, default=5,
                   help="FFE tap 수 (홀수 권장) [기본: 5]")
    p.add_argument("--train_frac", type=float, default=0.2,
                   help="FFE 설계에 사용할 training 심볼 비율 [기본: 0.2]")
    p.add_argument("--seed", type=int, default=1,
                   help="난수 시드 [기본: 1]")
    return p.parse_args()


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    ebn0_list = [float(v) for v in args.ebn0_list.split(",") if v.strip() != ""]

    # 채널 b (강 ISI)
    h_b = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=np.float64)

    print("=== CoPBit Q13 – x16 lanes PAM4 vs CoPBit-M8 Channel-b + FFE + Kuramoto (Eb/N0 basis) v0.1 ===")
    print(f"[Param] n_sym           = {args.n_sym}")
    print(f"[Param] n_lanes         = {args.n_lanes}")
    print(f"[Param] Eb/N0_list(dB)  = {ebn0_list}")
    print(f"[Param] channel         = b (taps = {h_b.tolist()})")
    print(f"[Param] ffe_len         = {args.ffe_len}")
    print(f"[Param] train_frac      = {args.train_frac}")
    print(f"[Param] drift_std_deg   = {args.drift_std_deg}")
    print(f"[Param] mu_phase        = {args.mu_phase}")
    print(f"[Param] seed            = {args.seed}")
    print("")
    print("PAM4는 단일 레인 기준 채널-equalized BER,")
    print("M8(CoPBit 위상)는 xN lanes + 글로벌 드리프트 + Kuramoto 기준 BER을 출력.")
    print("")
    print(" EbN0_dB | BER_PAM4_FFE | BER_M8_base | BER_M8_kura")
    print("-------------------------------------------------------")

    # 1) FFE 설계 (채널 b 기준, PAM4/M8 각각 한 번만)
    w_pam4 = design_ffe_pam4(h_b, args.ffe_len, args.train_frac, args.n_sym, rng)
    w_m8 = design_ffe_m8(h_b, args.ffe_len, args.train_frac, args.n_sym, rng)

    for ebn0_db in ebn0_list:
        # PAM4 + 채널 b + FFE
        ber_pam4 = simulate_pam4_channel_eq_ber(ebn0_db, args.n_sym, h_b, w_pam4, rng)

        # M8 + 채널 b + FFE + xN lanes + 글로벌 드리프트 + Kuramoto
        ber_m8_base, ber_m8_kura = simulate_m8_xn_eq_kuramoto_ber(
            ebn0_db=ebn0_db,
            n_sym=args.n_sym,
            n_lanes=args.n_lanes,
            channel_taps=h_b,
            w_ffe_m8=w_m8,
            drift_std_deg=args.drift_std_deg,
            mu_phase=args.mu_phase,
            rng=rng,
        )

        print(f"{ebn0_db:8.1f} |  {ber_pam4:11.3e} |  {ber_m8_base:10.3e} |  {ber_m8_kura:10.3e}")

    print("-------------------------------------------------------")
    print("※ 주석")
    print(" - 채널 b: [0.05, 0.5, 1.0, 0.5, 0.05] 5-tap ISI 채널.")
    print(" - PAM4_FFE: 실수 4레벨 PAM4 + 채널 b + AWGN + FFE(심볼 레이트, LS).")
    print(" - M8_base: 8-PSK(CoPBit 위상용) + 채널 b + AWGN + FFE까지 적용 후,")
    print("            글로벌 위상 드리프트를 무시하고 각 레인 독립 디코딩한 BER.")
    print(" - M8_kura: 같은 조건에서 xN lane 관측을 이용해 Kuramoto-style 위상 추적을 수행한 뒤")
    print("            디코딩한 BER.")
    print(" - Eb/N0는 비트당 에너지 기준 (PAM4: 2bit/sym, M8: 3bit/sym)으로 맞춘 공정 비교.")
    print(" - Q12c에서 찾은 sweet spot (ffe_len=5, train_frac≈0.2)를 멀티레인 Kuramoto 실험에 적용한 버전.")

if __name__ == "__main__":
    main()
