#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q16c – Multi-lane p_ref + data (AWGN + common phase-noise) v0

- Lane 구조:
  · N_ref lanes : p_ref (고정 8-PSK 심볼)
  · N_data lanes: data (랜덤 3bit/sym, M8)
- 채널 : no-ISI (h = [1]) + 공통 위상 노이즈 + AWGN
- PLL 모드:
  * No PLL      : 위상 추적 없음 (각 data lane 독립 slicer)
  * Data-DD only: 모든 data lane의 결정 에러 평균으로 공통 φ 추적
  * Data+p_ref  : p_ref lane + data lane 에러를 섞어서 공통 φ 추적

이 스크립트는 Q16(2-lane, 1 p_ref + 1 data)와 Q16b(3-lane, 2 p_ref + 1 data)를
포함한 일반화 버전이다. (N_ref, N_data)를 바꿔가며 스케일링 법칙을 보는 용도.

사용 예)
python copbit_q16c_multi_lane_pref_awgn_phase_v0.py \
  --n_sym 200000 \
  --ebn0_list "12,14,16" \
  --theta_std_deg 3.0 \
  --n_ref 1 \
  --n_data 1 \
  --mu_phase 0.05 \
  --alpha_ref 0.3 \
  --seed 1
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
# 메인 시뮬레이션
# -----------------------------
def run_q16c(args):
    np.random.seed(args.seed)

    n_sym = args.n_sym
    ebn0_list = parse_ebn0_list(args.ebn0_list)
    theta_std_deg = args.theta_std_deg
    mu_phase = args.mu_phase
    alpha_ref = args.alpha_ref
    n_ref = args.n_ref
    n_data = args.n_data

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

    # 결과 저장용 (Eb/N0별)
    ber_no_pll_list = []
    ber_dd_only_list = []
    ber_pref_list = []

    print("=== CoPBit Q16c – Multi-lane (N_ref p_ref + N_data data), AWGN + common phase-noise v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_std_deg  = {theta_std_deg}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] alpha_ref      = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] n_ref          = {n_ref}")
    print(f"[Param] n_data         = {n_data}")
    print(f"[Param] bits/symbol    = {BITS_PER_SYM}")
    print(f"[Param] seed           = {args.seed}")
    print("")
    print("[Info ] 채널: no-ISI (h=[1]), 공통 위상 노이즈 + AWGN")
    print("[Info ] PLL:")
    print("        - No PLL      : 각 data lane에 slicer만 적용 (공통 φ 추적 없음)")
    print("        - Data-DD only: 모든 data lane 에러 평균으로 공통 φ 추적")
    print("        - Data+p_ref  : p_ref + data 에러를 alpha_ref 비율로 섞어 공통 φ 추적")
    print("")

    for ebn0 in ebn0_list:
        # -------------------------
        # 공통 위상 노이즈 + AWGN
        # -------------------------
        phi_noise = generate_common_phase_noise(n_sym, theta_std_deg)  # (n_sym,)
        phasor = np.exp(1j * phi_noise)  # (n_sym,)

        # 각 lane에 공통 위상 드리프트 적용
        if n_ref > 0:
            y_ref = s_ref * phasor  # (n_ref, n_sym)
            y_ref_noisy = add_awgn(y_ref, ebn0)
        else:
            y_ref_noisy = np.zeros((0, n_sym), dtype=np.complex128)

        if n_data > 0:
            y_data = s_data * phasor  # (n_data, n_sym)
            y_data_noisy = add_awgn(y_data, ebn0)
        else:
            y_data_noisy = np.zeros((0, n_sym), dtype=np.complex128)

        # -------------------------
        # No PLL: 각 data lane에 대해 따로 slicer
        # -------------------------
        if n_data > 0:
            k_hat_no = slicer_m8(y_data_noisy)  # (n_data, n_sym)
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
                z_dd = y_data_noisy[:, i] * np.exp(-1j * phi_hat_dd)  # (n_data,)
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
                    z_ref = y_ref_noisy[:, i] * np.exp(-1j * phi_hat_pref)  # (n_ref,)
                    k_ref_hat = slicer_m8(z_ref)
                    s_ref_hat = const[k_ref_hat]
                    # e_ref: 실제 기준축(s_ref_const) vs 관측 z_ref
                    e_ref = np.angle(z_ref * np.conjugate(s_ref_const))  # (n_ref,)
                    e_ref_mean = np.mean(e_ref)
                else:
                    e_ref_mean = 0.0

                # data 측 에러
                z_data = y_data_noisy[:, i] * np.exp(-1j * phi_hat_pref)  # (n_data,)
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
    print(" - 이 Q16c v0 실험은 (N_ref, N_data)를 자유롭게 바꾸면서")
    print("   공통 위상 노이즈 환경에서 p_ref lane 수가 PLL 성능에")
    print("   어떤 영향을 주는지 보는 'multi-lane 최소 CoPBit 모델'이다.")
    print(" - N_ref=1, N_data=1  → 기존 Q16(2-lane)과 대응.")
    print(" - N_ref=2, N_data=1  → 기존 Q16b(3-lane)과 대응.")
    print(" - N_ref>1, N_data≫1 → Q13/Q14의 64-lane Kuramoto와의")
    print("   스케일링 법칙 연결용으로 사용 가능.")
    print(" - alpha_ref, mu_phase, theta_std_deg 등을 바꿔가며")
    print("   'CoPBit 설계 수식(필요한 p_ref 밀도 vs 위상 노이즈 강도)'를")
    print("   정리하는 데 활용 가능.")


# -----------------------------
# main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q16c – Multi-lane p_ref + data (AWGN + common phase-noise) v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000)
    parser.add_argument("--ebn0_list", type=str, default="12,14,16")
    parser.add_argument("--theta_std_deg", type=float, default=3.0)
    parser.add_argument("--mu_phase", type=float, default=0.05)
    parser.add_argument("--alpha_ref", type=float, default=0.3)
    parser.add_argument("--n_ref", type=int, default=1)
    parser.add_argument("--n_data", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    run_q16c(args)


if __name__ == "__main__":
    main()