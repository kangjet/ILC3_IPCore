#!/usr/bin/env python3
"""
CoPBit Q13d – lane & drift sweep with adaptive-step Kuramoto:
xN lanes CoPBit-M8(8-PSK) + Channel-b + FFE + adaptive + limited-step Kuramoto (Eb/N0 basis) v0.1

목표:
- 강 ISI 채널 b에서
  · CoPBit-M8(8-PSK) + 채널 + AWGN + FFE(5tap 근처)
  · xN lanes + 글로벌 위상 드리프트 + Kuramoto 위상 락
- 를 쓸 때,
  lane 수(n_lanes), drift_std_deg, Eb/N0에 따른
  · BER_base (Kuramoto OFF)
  · BER_kura_adapt (Kuramoto ON, adaptive μ + limited-step)
  변화를 보는 것.

변경 포인트(Q13c → Q13d):
- Kuramoto 위상 업데이트에서 μ를 고정 대신,
    err_phasor = mean(z_n * conj(s_hat))
    w         = |err_phasor|  (0..1, 신뢰도)
    delta     = mu_phase * w * err
    delta     = clip(delta, -phi_max_rad, +phi_max_rad)
    phi_est  += delta
- |err_phasor|가 작을수록(낮은 SNR, 위상 불안정) step을 자동으로 줄이고,
  |err_phasor|가 1에 가까울수록 더 적극적으로 락을 잡게 함.
"""

import argparse
import numpy as np


# -------------------------- 공통 유틸 함수들 --------------------------

def add_awgn_from_ebn0(x, ebn0_db, kbits, rng, complex_valued=False):
    """
    Eb/N0(dB)와 심볼당 비트수(kbits)를 기준으로
    Es/N0를 맞춘 후 AWGN을 추가.

    - x: 실수/복소 심볼 시퀀스 (배열, shape (...,))
    - Eb/N0(dB): ebn0_db
    - kbits: log2(M) (M8=3)
    - complex_valued: True면 복소 AWGN, False면 실수 AWGN
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * kbits  # Es/N0 = Eb/N0 * k (Es=1 기준)
    n0 = 1.0 / esn0_lin

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

    X = np.empty((N, L), dtype=np.complex128 if np.iscomplexobj(d_tr) else np.float64)
    for n in range(N):
        X[n, :] = y_pad[n:n + L]

    w, *_ = np.linalg.lstsq(X, d_tr, rcond=None)
    return w


# -------------------------- M8 (CoPBit 위상용 8-PSK) 모뎀 --------------------------

M8 = 8
# 바이너리 인덱스 0..7 -> 8-PSK 심벌 (unit circle)
M8_CONST = np.exp(1j * 2.0 * np.pi * np.arange(M8) / M8)


def m8_mod(bits):
    """
    bits: shape (N,3), binary
    반환:
    - x: shape (N,), 8-PSK 심벌 (complex)
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
    diff2 = np.abs(y[:, None] - M8_CONST[None, :]) ** 2
    idx_hat = np.argmin(diff2, axis=1)

    bits_hat = np.zeros((len(idx_hat), 3), dtype=np.int8)
    bits_hat[:, 0] = (idx_hat >> 2) & 1
    bits_hat[:, 1] = (idx_hat >> 1) & 1
    bits_hat[:, 2] = idx_hat & 1
    return bits_hat, idx_hat


def design_ffe_m8(channel_taps, ffe_len, train_frac, n_sym, rng):
    """
    M8(8-PSK)에 대해 채널 b 기준 FFE를 한 번 설계해서
    모든 lane/드리프트/EbN0 조합에서 공통 사용.
    """
    n_tr = max(16, int(train_frac * n_sym))
    bits_tr = rng.integers(0, 2, size=(n_tr, 3), endpoint=False)
    x_tr, _ = m8_mod(bits_tr)
    y_tr = np.convolve(x_tr, channel_taps, mode="same")
    w = solve_ffe_lstsq(y_tr, x_tr, ffe_len)
    return w


# -------------------------- xN lanes + EQ + adaptive + limited-step Kuramoto --------------------------

def simulate_m8_xn_eq_kuramoto_ber_adaptive(
    ebn0_db,
    n_sym,
    n_lanes,
    channel_taps,
    w_ffe_m8,
    drift_std_deg,
    mu_phase,
    phi_max_deg,
    rng,
):
    """
    xN lanes 8-PSK (M8) + 채널 b + AWGN + FFE +
    글로벌 위상 드리프트 + adaptive + limited-step Kuramoto 위상 추적

    반환:
    - ber_base: Kuramoto 없이, 각 레인을 독립 8-PSK로 디코딩한 BER
    - ber_kura: adaptive + limited-step Kuramoto 위상 추적 후 디코딩한 BER
    """
    kbits = 3

    # 1) 비트 & 심볼 생성
    bits = rng.integers(0, 2, size=(n_lanes, n_sym, kbits), endpoint=False)
    bits_flat = bits.reshape(-1, kbits)
    x_flat, _ = m8_mod(bits_flat)
    x = x_flat.reshape(n_lanes, n_sym)

    # 2) 채널 통과
    h = channel_taps
    y_ch = np.empty_like(x, dtype=np.complex128)
    for l in range(n_lanes):
        y_ch[l, :] = np.convolve(x[l, :], h, mode="same")

    # 3) AWGN 추가 (Eb/N0 기준)
    y_noisy = add_awgn_from_ebn0(y_ch, ebn0_db, kbits=kbits, rng=rng, complex_valued=True)

    # 4) FFE 적용 (각 레인 동일 계수 사용)
    y_eq = np.empty_like(y_noisy, dtype=np.complex128)
    for l in range(n_lanes):
        y_eq[l, :] = np.convolve(y_noisy[l, :], w_ffe_m8, mode="same")

    # 5) 글로벌 위상 드리프트 (random walk)
    drift_std_rad = np.deg2rad(drift_std_deg)
    dphi = drift_std_rad * rng.standard_normal(size=n_sym)
    phi_true = np.cumsum(dphi)
    phase_rot = np.exp(1j * phi_true)[None, :]  # (1, N)
    z = y_eq * phase_rot  # (L, N)  실제 RX에서 보는 심벌

    # 6) Base 디코딩 (Kuramoto 없이)
    z_flat = z.reshape(-1)
    bits_hat_base_flat, _ = m8_demod_to_bits(z_flat)
    bits_hat_base = bits_hat_base_flat.reshape(n_lanes, n_sym, kbits)
    bit_errors_base = np.count_nonzero(bits_hat_base != bits)
    ber_base = bit_errors_base / bits.size

    # 7) adaptive + limited-step Kuramoto 기반 글로벌 위상 추적 + 디코딩
    phi_est = 0.0
    phi_max_rad = np.deg2rad(phi_max_deg)
    idx_hat_kura = np.empty((n_lanes, n_sym), dtype=np.int64)

    for n in range(n_sym):
        # 현재 추정 위상 제거
        z_n = z[:, n] * np.exp(-1j * phi_est)  # shape (L,)

        # 각 레인 독립 디코딩
        diff2 = np.abs(z_n[:, None] - M8_CONST[None, :]) ** 2
        idx_n = np.argmin(diff2, axis=1)  # (L,)
        idx_hat_kura[:, n] = idx_n

        # 피드백용 이상 심벌
        s_hat = M8_CONST[idx_n]  # (L,)

        # Kuramoto-style 집단 위상 오차 추정
        err_phasor = np.mean(z_n * np.conj(s_hat))
        err = np.angle(err_phasor)
        w = np.abs(err_phasor)  # 0..1, 위상 신뢰도(코히어런스)

        # adaptive-step + limited-step 업데이트
        delta = mu_phase * w * err
        if delta > phi_max_rad:
            delta = phi_max_rad
        elif delta < -phi_max_rad:
            delta = -phi_max_rad

        phi_est += delta

    # Kuramoto 후 비트 복원
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
        description="CoPBit Q13d – lane & drift sweep for xN lanes M8 + Channel-b + FFE + adaptive + limited-step Kuramoto (Eb/N0 basis) v0.1"
    )
    p.add_argument("--n_sym", type=int, default=100000,
                   help="심볼 수 (lane 당) [기본: 100000]")
    p.add_argument("--ebn0_list", type=str, default="10,12,14",
                   help="콤마 구분 Eb/N0 리스트 (dB) [기본: '10,12,14']")
    p.add_argument("--lanes_list", type=str, default="4,16,64,256",
                   help="콤마 구분 lane 수 리스트 [기본: '4,16,64,256']")
    p.add_argument("--drift_list", type=str, default="0.5,1.0,2.0,3.0",
                   help="콤마 구분 드리프트 표준편차 리스트 (deg) [기본: '0.5,1.0,2.0,3.0']")
    p.add_argument("--ffe_len", type=int, default=5,
                   help="FFE tap 수 (홀수 권장) [기본: 5]")
    p.add_argument("--train_frac", type=float, default=0.2,
                   help="FFE 설계에 사용할 training 심볼 비율 [기본: 0.2]")
    p.add_argument("--mu_phase", type=float, default=0.1,
                   help="Kuramoto 위상 업데이트 base 스텝 크기 [기본: 0.1]")
    p.add_argument("--phi_max_deg", type=float, default=10.0,
                   help="Kuramoto 1-step 최대 위상 변경량 (deg) [기본: 10.0]")
    p.add_argument("--seed", type=int, default=1,
                   help="난수 시드 [기본: 1]")
    return p.parse_args()


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    ebn0_list = [float(v) for v in args.ebn0_list.split(",") if v.strip() != ""]
    lanes_list = [int(v) for v in args.lanes_list.split(",") if v.strip() != ""]
    drift_list = [float(v) for v in args.drift_list.split(",") if v.strip() != ""]

    # 강 ISI 채널 b
    h_b = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=np.float64)

    print("=== CoPBit Q13d – lane & drift sweep for xN lanes M8 + Channel-b + FFE + adaptive + limited-step Kuramoto (Eb/N0 basis) v0.1 ===")
    print(f"[Param] n_sym          = {args.n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] lanes_list     = {lanes_list}")
    print(f"[Param] drift_list(deg)= {drift_list}")
    print(f"[Param] channel        = b (taps = {h_b.tolist()})")
    print(f"[Param] ffe_len        = {args.ffe_len}")
    print(f"[Param] train_frac     = {args.train_frac}")
    print(f"[Param] mu_phase       = {args.mu_phase}  (base, adaptive 전)")
    print(f"[Param] phi_max_deg    = {args.phi_max_deg}")
    print(f"[Param] seed           = {args.seed}")
    print("")

    # 1) 채널 b 기준 M8 FFE 설계 (한 번만)
    w_m8 = design_ffe_m8(h_b, args.ffe_len, args.train_frac, args.n_sym, rng)
    print(f"[INFO] Designed M8 FFE (len={len(w_m8)}, train_frac={args.train_frac})")
    print("")

    for drift_std_deg in drift_list:
        print(f"================ drift_std_deg = {drift_std_deg:.2f} deg =================")
        print(" n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)")
        print("------------------------------------------------------")

        for n_lanes in lanes_list:
            for ebn0_db in ebn0_list:
                ber_base, ber_kura = simulate_m8_xn_eq_kuramoto_ber_adaptive(
                    ebn0_db=ebn0_db,
                    n_sym=args.n_sym,
                    n_lanes=n_lanes,
                    channel_taps=h_b,
                    w_ffe_m8=w_m8,
                    drift_std_deg=drift_std_deg,
                    mu_phase=args.mu_phase,
                    phi_max_deg=args.phi_max_deg,
                    rng=rng,
                )
                print(f"{n_lanes:7d} | {ebn0_db:7.1f} |  {ber_base:10.3e} |  {ber_kura:10.3e}")
        print("------------------------------------------------------")
        print("")

    print("※ 주석")
    print(" - 채널 b: [0.05, 0.5, 1.0, 0.5, 0.05] 5-tap ISI 채널.")
    print(" - M8: CoPBit 위상용 8-PSK (3bit/sym), unit circle, Eb/N0 기반 bit-fair AWGN.")
    print(" - Q13c 대비 변경점:")
    print("     · Kuramoto 위상 업데이트 스텝에 |err_phasor| 가중치를 곱해 adaptive-step 적용.")
    print("     · phasor 코히어런스가 낮을수록 step을 줄여서 발산을 억제.")
    print("     · phi_max_deg로 1-step 최대 변화를 제한해 과도한 튐을 추가로 방지.")
    print(" - lane 수(L)를 늘리면 평균 phasor의 잡음이 줄어들어 |err_phasor|가 커지고,")
    print("   adaptive-step이 자연스럽게 더 큰 스텝으로 위상 락을 잡게 된다.")
    print(" - drift_std_deg가 커질수록 err_phasor의 위상/크기 분포가 넓어지는데,")
    print("   이때 adaptive-step이 Q13b/13c 대비 얼마나 더 안정적으로 버티는지 비교하면,")
    print("   CoPBit 멀티레인 위상 락의 '실제 허용 드리프트 범위'를 한층 더 정교하게 조정할 수 있다.")


if __name__ == "__main__":
    main()