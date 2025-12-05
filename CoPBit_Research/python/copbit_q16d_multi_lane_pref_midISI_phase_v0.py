#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q16d – Multi-lane p_ref + data (Channel-b mid-ISI + FFE + common phase-noise) v1
(FFE = block-MMSE 버전, LMS 발산 이슈 제거)

- Lane 구조:
  · N_ref lanes : p_ref (고정 8-PSK 심볼)
  · N_data lanes: data (랜덤 3bit/sym, M8)
- 채널 : Channel-b 5-tap mid-ISI (Q13/Q14와 동일 계열)
  · h_b_raw = [0.05, 0.5, 1.0, 0.5, 0.05]
  · h_midISI = h_b_raw / ||h_b_raw||_2 (에너지 정규화)
- 수신단: mid-ISI + AWGN → 공통 FFE(M8 기준) → 공통 위상 노이즈 → PLL 모드 비교
  * No PLL      : 위상 추적 없음 (각 data lane 독립 slicer)
  * Data-DD only: 모든 data lane의 결정 에러 평균으로 공통 φ 추적
  * Data+p_ref  : p_ref lane + data lane 에러를 섞어서 공통 φ 추적

이 스크립트는 Q16c(AWGN-only)의 mid-ISI + FFE 확장판으로,
(N_ref, N_data) = (1,1), (2,1), (8,56) 등을 바꿔가며
Channel-b 환경에서 p_ref 효과를 보는 용도.

※ v1 변경점
  - 기존 LMS FFE(design_ffe_lms)를 제거하고,
    block-MMSE FFE(design_ffe_mmse)로 교체.
  - --mu_ffe 인자는 MMSE ridge(정규화 항)로 재해석하여 사용.
  - train_frac 인자는 더 이상 FFE 계산에 직접 쓰이지 않지만,
    Q16/Q16c와의 인터페이스를 맞추기 위해 유지.
"""

import argparse
import numpy as np

# -----------------------------
# 기본 설정
# -----------------------------
BITS_PER_SYM = 3  # M8 (3 bit / symbol)


def parse_ebn0_list(s: str):
    return [float(x) for x in s.split(",") if x.strip() != ""]


# -----------------------------
# 유틸: 비트 <-> 심볼 인덱스
# -----------------------------
def bits_to_ints(bits, k: int = BITS_PER_SYM):
    bits = bits.reshape(-1, k)
    vals = np.zeros(bits.shape[0], dtype=int)
    for i in range(k):
        vals = (vals << 1) | bits[:, i]
    return vals


def ints_to_bits(vals, k: int = BITS_PER_SYM):
    vals = np.array(vals, dtype=int).reshape(-1)
    bits = np.zeros((vals.shape[0], k), dtype=int)
    for i in range(k - 1, -1, -1):
        bits[:, i] = vals & 1
        vals >>= 1
    return bits.reshape(-1)


# -----------------------------
# M8 (8-PSK) 맵핑
# -----------------------------
def m8_constellation():
    """
    index k=0..7 → 8-PSK on unit circle: exp(j*2πk/8)
    """
    k = np.arange(8)
    return np.exp(1j * 2 * np.pi * k / 8.0)


def map_ints_to_m8(sym_idx):
    const = m8_constellation()
    return const[sym_idx]


def slicer_m8(z):
    """
    복소 샘플 z를 가장 가까운 8-PSK 포인트 index로 양자화
    """
    z = np.asarray(z)
    angles = np.angle(z)
    angles = np.where(angles < 0, angles + 2 * np.pi, angles)
    k_hat = np.round(angles * 8.0 / (2 * np.pi)) % 8
    return k_hat.astype(int)


# -----------------------------
# AWGN (Eb/N0 기준) – 다차원 지원
# -----------------------------
def add_awgn(x, ebn0_db, bits_per_sym: int = BITS_PER_SYM):
    """
    x: shape (n_sym,) 또는 (n_lane, n_sym) 복소 시퀀스
    """
    x = np.asarray(x)
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    es = np.mean(np.abs(x) ** 2)  # 평균 심볼 에너지
    n0 = es / (bits_per_sym * ebn0_lin)
    sigma2 = n0 / 2.0
    noise = np.sqrt(sigma2) * (
        np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape)
    )
    return x + noise


# -----------------------------
# 공통 위상 노이즈 (Wiener process)
# -----------------------------
def generate_common_phase_noise(n_sym, theta_std_deg: float):
    """
    공통 위상 노이즈: Δφ ~ N(0, σ^2), σ[deg]를 rad로 변환 후 누적 (Wiener)
    """
    sigma = theta_std_deg * np.pi / 180.0
    dphi = np.random.randn(n_sym) * sigma
    phi = np.cumsum(dphi)
    return phi  # length n_sym


# -----------------------------
# Channel-b 5-tap mid-ISI (symbol-rate)
# -----------------------------
def get_channel_b_taps():
    h_raw = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=np.float64)
    h_norm = h_raw / np.sqrt(np.sum(h_raw ** 2))
    return h_norm.astype(np.complex128)


def apply_mid_isi_channel(s, h):
    """
    s : (n_sym,) 또는 (n_lane, n_sym)
    h : (L,) 5-tap mid-ISI
    → np.convolve(..., mode='same') 사용해서 길이 n_sym 유지
    """
    s = np.asarray(s)
    if s.ndim == 1:
        s = s.reshape(1, -1)
    n_lane, _ = s.shape
    y_list = []
    for i in range(n_lane):
        y_i = np.convolve(s[i], h, mode="same")
        y_list.append(y_i)
    return np.stack(y_list, axis=0)  # (n_lane, n_sym)


# -----------------------------
# FFE 설계 (공통 FFE; block-MMSE 방식)
# -----------------------------
def design_ffe_mmse(y_train, d_train, ffe_len: int, ridge: float = 1e-4):
    """
    y_train : 채널+AWGN 통과한 시퀀스 (1D, length = n_sym)
    d_train : 송신 심볼 (complex, M8) (1D, length = n_sym)

    FFE 구조: y_hat[n] = w^H u[n], u[n] = [x[n], x[n-1], ..., x[n-ffe_len+1]]
    - 앞쪽 경계는 zero padding
    - block-MMSE 방식으로 w를 한 번에 계산:
        w = (R + ridge*I)^(-1) p
          · R = E[u u^H]
          · p = E[u d*]
    """
    y_train = np.asarray(y_train, dtype=np.complex128)
    d_train = np.asarray(d_train, dtype=np.complex128)
    n_sym = len(y_train)

    # 입력 버퍼 padding
    x_pad = np.concatenate(
        [np.zeros(ffe_len - 1, dtype=np.complex128), y_train]
    )

    # Toeplitz 형태의 입력 행렬 X: (n_sym, ffe_len)
    X = np.zeros((n_sym, ffe_len), dtype=np.complex128)
    for n in range(n_sym):
        X[n, :] = x_pad[n : n + ffe_len][::-1]

    # 통계량 계산
    R = (X.conj().T @ X) / n_sym          # (ffe_len, ffe_len)
    p = (X.conj().T @ d_train) / n_sym    # (ffe_len,)

    # ridge 추가해서 역행렬 안정화
    R = R + ridge * np.eye(ffe_len, dtype=np.complex128)

    # MMSE 해
    w = np.linalg.solve(R, p)             # (ffe_len,)

    # equalized 출력
    y_eq = X @ w                          # (n_sym,)

    return w, y_eq


def apply_ffe(y, w):
    """
    y : (n_sym,) 또는 (n_lane, n_sym)
    w : (ffe_len,)
    """
    y = np.asarray(y)
    if y.ndim == 1:
        y = y.reshape(1, -1)
    n_lane, n_sym = y.shape
    ffe_len = len(w)
    x_pad = np.concatenate(
        [np.zeros((n_lane, ffe_len - 1), dtype=np.complex128), y.astype(np.complex128)],
        axis=1,
    )
    y_eq = np.zeros_like(y, dtype=np.complex128)
    for n in range(n_sym):
        u = x_pad[:, n : n + ffe_len][:, ::-1]  # (n_lane, ffe_len)
        # 각 lane에 대해 y_hat = w^H u
        y_eq[:, n] = np.dot(u, np.conjugate(w))
    return y_eq


# -----------------------------
# 메인 시뮬레이션
# -----------------------------
def run_q16d(args):
    np.random.seed(args.seed)

    n_sym = args.n_sym
    ebn0_list = parse_ebn0_list(args.ebn0_list)
    theta_std_deg = args.theta_std_deg
    mu_phase = args.mu_phase
    alpha_ref = args.alpha_ref
    n_ref = args.n_ref
    n_data = args.n_data
    ffe_len = args.ffe_len
    mu_ffe = args.mu_ffe        # v1에서는 MMSE ridge로 사용
    train_frac = args.train_frac  # FFE에서는 직접 사용하지 않지만, 인터페이스 유지

    const = m8_constellation()
    k_ref_const = 0
    s_ref_const = const[k_ref_const]

    # -------------------------
    # Tx 심볼 생성
    # -------------------------
    # data bit / symbol들: lane마다 독립 랜덤
    n_bits = n_sym * BITS_PER_SYM
    tx_bits_data = np.random.randint(0, 2, size=(n_data, n_bits), dtype=int)  # (n_data, n_bits)
    tx_ints_data = np.stack(
        [bits_to_ints(tx_bits_data[i], k=BITS_PER_SYM) for i in range(n_data)],
        axis=0,
    )  # (n_data, n_sym)
    s_data = map_ints_to_m8(tx_ints_data)  # (n_data, n_sym)

    # p_ref lanes: 고정 심볼 시퀀스
    s_ref = np.full((n_ref, n_sym), s_ref_const, dtype=np.complex128)  # (n_ref, n_sym)

    # Channel-b taps
    h_mid = get_channel_b_taps()

    # 결과 저장용 (Eb/N0별)
    ber_no_pll_list = []
    ber_dd_only_list = []
    ber_pref_list = []

    print("=== CoPBit Q16d – Multi-lane (N_ref p_ref + N_data data), Channel-b mid-ISI + FFE + common phase-noise v1 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_std_deg  = {theta_std_deg}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] alpha_ref      = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] n_ref          = {n_ref}")
    print(f"[Param] n_data         = {n_data}")
    print(f"[Param] bits/symbol    = {BITS_PER_SYM}")
    print(f"[Param] ffe_len        = {ffe_len}")
    print(f"[Param] train_frac     = {train_frac}  (v1: FFE에는 직접 사용 안 함)")
    print(f"[Param] mu_ffe(ridge)  = {mu_ffe}")
    print(f"[Param] seed           = {args.seed}")
    print("")
    print(f"[Chan ] h_midISI (norm) = {h_mid.real}")
    print("[Info ] 수신 구조: mid-ISI + AWGN → 공통 FFE(M8, MMSE) → 공통 위상 노이즈 → PLL")
    print("[Info ] PLL:")
    print("        - No PLL      : 각 data lane에 slicer만 적용 (공통 φ 추적 없음)")
    print("        - Data-DD only: 모든 data lane 에러 평균으로 공통 φ 추적")
    print("        - Data+p_ref  : p_ref + data 에러를 alpha_ref 비율로 섞어 공통 φ 추적")
    print("")

    for ebn0 in ebn0_list:
        # -------------------------
        # mid-ISI 채널 + AWGN
        # -------------------------
        if n_ref > 0:
            y_ref_ch = apply_mid_isi_channel(s_ref, h_mid)  # (n_ref, n_sym)
            y_ref_noisy = add_awgn(y_ref_ch, ebn0)
        else:
            y_ref_noisy = np.zeros((0, n_sym), dtype=np.complex128)

        if n_data > 0:
            y_data_ch = apply_mid_isi_channel(s_data, h_mid)  # (n_data, n_sym)
            y_data_noisy = add_awgn(y_data_ch, ebn0)
        else:
            y_data_noisy = np.zeros((0, n_sym), dtype=np.complex128)

        # -------------------------
        # 공통 FFE 설계 (첫 번째 data lane 기준, block-MMSE)
        # -------------------------
        if n_data > 0:
            w_ffe, _ = design_ffe_mmse(
                y_train=y_data_noisy[0],
                d_train=s_data[0],
                ffe_len=ffe_len,
                ridge=mu_ffe if mu_ffe > 0 else 1e-4,
            )
        else:
            # data lane이 없다면 의미는 없지만, 형태 맞추기
            w_ffe = np.zeros(ffe_len, dtype=np.complex128)
            w_ffe[ffe_len // 2] = 1.0 + 0j

        # 모든 lane에 FFE 적용
        if n_ref > 0:
            y_ref_eq = apply_ffe(y_ref_noisy, w_ffe)  # (n_ref, n_sym)
        else:
            y_ref_eq = np.zeros((0, n_sym), dtype=np.complex128)

        if n_data > 0:
            y_data_eq = apply_ffe(y_data_noisy, w_ffe)  # (n_data, n_sym)
        else:
            y_data_eq = np.zeros((0, n_sym), dtype=np.complex128)

        # -------------------------
        # 공통 위상 노이즈 (FFE 이후에 곱해줌 – 선형 시스템과 교환 가능)
        # -------------------------
        phi_noise = generate_common_phase_noise(n_sym, theta_std_deg)  # (n_sym,)
        phasor = np.exp(1j * phi_noise)  # (n_sym,)

        if n_ref > 0:
            y_ref_eq_phase = y_ref_eq * phasor  # (n_ref, n_sym)
        else:
            y_ref_eq_phase = np.zeros((0, n_sym), dtype=np.complex128)

        if n_data > 0:
            y_data_eq_phase = y_data_eq * phasor  # (n_data, n_sym)
        else:
            y_data_eq_phase = np.zeros((0, n_sym), dtype=np.complex128)

        # -------------------------
        # No PLL: 각 data lane에 대해 그냥 slicer
        # -------------------------
        if n_data > 0:
            k_hat_no = slicer_m8(y_data_eq_phase)  # (n_data, n_sym)
            bits_hat_no = np.stack(
                [ints_to_bits(k_hat_no[i], k=BITS_PER_SYM) for i in range(n_data)],
                axis=0,
            )  # (n_data, n_bits)
            ber_no = np.mean(bits_hat_no != tx_bits_data)
        else:
            ber_no = 0.0

        # -------------------------
        # Data-DD only: 모든 data lane 에러 평균으로 φ 추적
        # -------------------------
        phi_hat_dd = 0.0
        bits_hat_dd = np.zeros_like(tx_bits_data, dtype=int)

        if n_data > 0:
            for i in range(n_sym):
                # 공통 φ_hat로 모든 data lane 보정
                z_dd = y_data_eq_phase[:, i] * np.exp(-1j * phi_hat_dd)  # (n_data,)
                k_dec = slicer_m8(z_dd)  # (n_data,)
                s_dec = const[k_dec]     # (n_data,)
                e = np.angle(z_dd * np.conjugate(s_dec))  # (n_data,)
                e_mean = np.mean(e)
                phi_hat_dd += mu_phase * e_mean

                # 비트 복원
                bits_block = np.stack(
                    [ints_to_bits(k_dec[j], k=BITS_PER_SYM) for j in range(n_data)],
                    axis=0,
                )  # (n_data, BITS_PER_SYM)
                bits_hat_dd[:, i * BITS_PER_SYM : (i + 1) * BITS_PER_SYM] = bits_block

            ber_dd = np.mean(bits_hat_dd != tx_bits_data)
        else:
            ber_dd = 0.0

        # -------------------------
        # Data + p_ref: p_ref + data 에러 혼합
        # -------------------------
        phi_hat_pref = 0.0
        bits_hat_pref = np.zeros_like(tx_bits_data, dtype=int)

        if n_data > 0:
            for i in range(n_sym):
                # p_ref 측 에러
                if n_ref > 0:
                    z_ref = y_ref_eq_phase[:, i] * np.exp(-1j * phi_hat_pref)  # (n_ref,)
                    # slicer 결과는 형식상 계산이지만, e_ref는 s_ref_const 기준
                    e_ref = np.angle(z_ref * np.conjugate(s_ref_const))  # (n_ref,)
                    e_ref_mean = np.mean(e_ref)
                else:
                    e_ref_mean = 0.0

                # data 측 에러
                z_data = y_data_eq_phase[:, i] * np.exp(-1j * phi_hat_pref)  # (n_data,)
                k_data_hat = slicer_m8(z_data)
                s_data_hat = const[k_data_hat]
                e_data = np.angle(z_data * np.conjugate(s_data_hat))  # (n_data,)
                e_data_mean = np.mean(e_data)

                # p_ref vs data 혼합
                e_total = (1.0 - alpha_ref) * e_ref_mean + alpha_ref * e_data_mean
                phi_hat_pref += mu_phase * e_total

                bits_block_pref = np.stack(
                    [ints_to_bits(k_data_hat[j], k=BITS_PER_SYM) for j in range(n_data)],
                    axis=0,
                )
                bits_hat_pref[:, i * BITS_PER_SYM : (i + 1) * BITS_PER_SYM] = bits_block_pref

            ber_pref = np.mean(bits_hat_pref != tx_bits_data)
        else:
            ber_pref = 0.0

        ber_no_pll_list.append(ber_no)
        ber_dd_only_list.append(ber_dd)
        ber_pref_list.append(ber_pref)

    # -----------------------------
    # 결과 출력
    # -----------------------------
    print("")
    print("===============================================================")
    print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef       ")
    print("---------------------------------------------------------------")
    for eb, b0, b1, b2 in zip(ebn0_list, ber_no_pll_list, ber_dd_only_list, ber_pref_list):
        print(f"{eb:9.1f} | {b0:12.6f} | {b1:12.6f} | {b2:12.6f}")
    print("---------------------------------------------------------------")
    print("")
    print("※ 주석")
    print(" - 이 Q16d v1 실험은 Channel-b mid-ISI + block-MMSE FFE 환경에서 (N_ref, N_data)를")
    print("   자유롭게 바꾸면서 공통 위상 노이즈에 대한 p_ref lane 수의 효과를 보는")
    print("   'multi-lane CoPBit 최소 모델'이다.")
    print(" - N_ref=1, N_data=1  → Q16(2-lane)에 대응 (mid-ISI 확장판).")
    print(" - N_ref=2, N_data=1  → Q16b(3-lane)에 대응 (mid-ISI 확장판).")
    print(" - N_ref=8, N_data=56 → 64-lane CoPBit(Q13/Q14)와 동일 lane 수에서")
    print("   필요한 p_ref 밀도 vs θ_std_deg, Eb/N0 관계를 정리하는 용도로 사용 가능.")
    print(" - mu_ffe 인자는 block-MMSE에서 ridge(정규화 항)로 사용된다.")
    print(" - alpha_ref, mu_phase, theta_std_deg, ffe_len, mu_ffe, train_frac 등을")
    print("   바꿔가며 'CoPBit PhaseLock_std 설계 수식'을 도출하는 데 활용 가능.")


# -----------------------------
# main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q16d – Multi-lane p_ref + data (Channel-b mid-ISI + FFE + common phase-noise) v1 (MMSE-FFE)"
    )
    parser.add_argument("--n_sym", type=int, default=200000)
    parser.add_argument("--ebn0_list", type=str, default="12,14,16")
    parser.add_argument("--theta_std_deg", type=float, default=3.0)
    parser.add_argument("--mu_phase", type=float, default=0.05)
    parser.add_argument("--alpha_ref", type=float, default=0.3)
    parser.add_argument("--n_ref", type=int, default=1)
    parser.add_argument("--n_data", type=int, default=1)
    parser.add_argument("--ffe_len", type=int, default=7)
    parser.add_argument("--mu_ffe", type=float, default=0.003)      # v1: ridge로 사용
    parser.add_argument("--train_frac", type=float, default=0.5)    # 인터페이스 유지용
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    run_q16d(args)


if __name__ == "__main__":
    main()