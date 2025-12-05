#!/usr/bin/env python3
"""
CoPBit Q16 – 2-lane M8 (p_ref + data), common phase-noise + AWGN

목적:
- 1-lane M8 + DD-PLL 만으로는 CoPBit의 장점을 못 보여준다.
- 최소 2-lane (Lane0=p_ref, Lane1=data) 구조에서
  공통 위상 노이즈(oscillator drift)를 걸어주고,
  p_ref를 Kuramoto-style 위상락에 섞어 넣었을 때
  BER이 얼마나 개선되는지 보는 실험.

구조:
- Lane0: p_ref lane
    · 고정 M8 심볼 시퀀스 (ex. 모두 k_ref=0, 각도=0도) – 위상 기준 축
- Lane1: data lane
    · 랜덤 3bit/sym → M8

- 채널: 공통 phase noise + AWGN (no-ISI, h = [1])

- Rx 비교:
    1) No PLL            : lane1에 그냥 slicer
    2) Data-DD only      : lane1만 보고 φ 업데이트 (1-lane PLL 근사)
    3) Data + p_ref PLL  : lane0 + lane1 에러 phasor를 섞어서 φ 업데이트
"""

import argparse
import numpy as np


# ---------------------------------------------------------------------
# 기본 유틸
# ---------------------------------------------------------------------
def set_seed(seed: int):
    if seed is not None:
        np.random.seed(seed)


def parse_ebn0_list(s: str):
    return [float(x) for x in s.split(",") if x.strip()]


# ---------------------------------------------------------------------
# 노이즈 모델 (AWGN + 공통 위상 노이즈)
# ---------------------------------------------------------------------
def add_awgn_ebn0(x, ebn0_db, bits_per_sym: int):
    """
    Eb/N0 기준 AWGN 추가 (complex baseband).
    x 평균 에너지(Es)를 기준으로 N0 계산.
    """
    ebn0_linear = 10.0 ** (ebn0_db / 10.0)
    Es = np.mean(np.abs(x) ** 2)
    N0 = Es / (ebn0_linear * bits_per_sym)
    noise_var = N0  # complex baseband에서 variance = N0
    noise = np.sqrt(noise_var / 2.0) * (
        np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape)
    )
    return x + noise


def apply_common_phase_noise(x_ref, x_data, theta_std_deg: float):
    """
    공통 위상 노이즈 (Wiener process) 적용.
    - theta_std_deg: 심볼당 위상 증가량(Δφ)의 표준편차 [deg]

    x_ref, x_data: complex, shape=(N,)
    return: (y_ref, y_data)
    """
    N = len(x_ref)
    assert len(x_data) == N

    if theta_std_deg <= 0.0:
        return x_ref.astype(np.complex128), x_data.astype(np.complex128)

    sigma = np.deg2rad(theta_std_deg)
    dphi = np.random.randn(N) * sigma  # per-symbol increment
    phi = np.cumsum(dphi)              # 공통 위상 궤적

    phase_rot = np.exp(1j * phi)
    y_ref = x_ref * phase_rot
    y_data = x_data * phase_rot
    return y_ref, y_data


# ---------------------------------------------------------------------
# Modem: M8 (8-PSK)
# ---------------------------------------------------------------------
def bits_to_int(bits, k: int):
    """bit array -> 0..(2^k-1) int 배열"""
    bits = bits.reshape(-1, k)
    vals = np.zeros(bits.shape[0], dtype=int)
    for i in range(k):
        vals = (vals << 1) | bits[:, i]
    return vals


def int_to_bits(vals, k: int):
    N = vals.shape[0]
    bits = np.zeros((N, k), dtype=int)
    for i in range(k):
        bits[:, k - 1 - i] = (vals >> i) & 1
    return bits.reshape(-1)


def m8_mod_from_idx(idx):
    """0..7 index -> 8-PSK 심볼"""
    k = idx
    ang = 2.0 * np.pi * k / 8.0
    sym = np.exp(1j * ang)
    return sym


def m8_mod_bits(bits):
    """3bit/sym 랜덤 데이터용"""
    assert bits.size % 3 == 0
    idx = bits_to_int(bits, 3)  # 0..7
    return m8_mod_from_idx(idx), idx


def m8_slicer(y):
    """
    8-PSK slicer.
    """
    ang = np.angle(y)
    k = np.round((ang * 8.0) / (2.0 * np.pi)) % 8
    k = np.nan_to_num(k, nan=0.0, posinf=0.0, neginf=0.0)
    k = k.astype(int)
    dec_sym = np.exp(1j * (2.0 * np.pi * k / 8.0))
    return dec_sym, k


# ---------------------------------------------------------------------
# 위상 트래커 (Kuramoto-style, 2-lane)
# ---------------------------------------------------------------------
def phase_tracker_data_only(y_data, mu_phase: float):
    """
    1-lane M8 decision-directed PLL (data only).
    - y_data: complex, length N
    - mu_phase: 위상 업데이트 스텝
    """
    N = len(y_data)
    z_data = np.zeros(N, dtype=np.complex128)
    phi = 0.0

    for n in range(N):
        # 현재 추정 위상 제거
        z_n = y_data[n] * np.exp(-1j * phi)
        z_data[n] = z_n

        # 데이터 레인만 보고 DD 에러 계산
        d_n, _ = m8_slicer(z_n)
        err_phasor = d_n * np.conjugate(z_n)
        dphi = np.angle(err_phasor)

        # 안정 루프를 위해 음수 방향으로 업데이트
        phi -= mu_phase * dphi

    return z_data


def phase_tracker_data_plus_pref(
    y_ref,
    y_data,
    s_ref,
    mu_phase: float,
    alpha_ref: float,
):
    """
    2-lane Kuramoto-style 위상 트래커.
    - 공통 위상 φ_k를 한 개만 둔다.
    - lane0(p_ref), lane1(data) 모두의 에러 phasor를 섞어서 φ 업데이트.

    y_ref, y_data : 공통 phase-noise + AWGN 가해진 수신 심볼 (complex)
    s_ref         : 전송된 reference 심볼 시퀀스 (noise-free ideal)
    mu_phase      : 위상 업데이트 스텝
    alpha_ref     : 에러 섞을 때 data vs ref 비중
                    · total_err = (1-alpha_ref)*err_ref + alpha_ref*err_data
                      (alpha_ref가 0에 가까우면 ref 영향↑, 1이면 data-only)
    """
    assert 0.0 <= alpha_ref <= 1.0
    N = len(y_data)
    assert len(y_ref) == N and len(s_ref) == N

    z_data = np.zeros(N, dtype=np.complex128)
    phi = 0.0

    for n in range(N):
        # 현재 추정 위상 제거
        z_d = y_data[n] * np.exp(-1j * phi)
        z_r = y_ref[n] * np.exp(-1j * phi)

        z_data[n] = z_d

        # (1) data lane 에러
        d_d, _ = m8_slicer(z_d)
        err_data_phasor = d_d * np.conjugate(z_d)

        # (2) reference lane 에러
        #     - ref는 전송 심볼 s_ref[n]을 알고 있으므로
        #       ideal vs 현재 z_r 의 위상 차이를 error로 본다.
        err_ref_phasor = s_ref[n] * np.conjugate(z_r)

        # (3) 두 에러 phasor를 섞어서 φ 업데이트
        total_err = (1.0 - alpha_ref) * err_ref_phasor + alpha_ref * err_data_phasor
        dphi = np.angle(total_err)

        phi -= mu_phase * dphi

    return z_data


# ---------------------------------------------------------------------
# BER 계산
# ---------------------------------------------------------------------
def ber_from_indices(gt_idx, dec_idx, bits_per_sym: int = 3):
    """
    M8 index 기준 BER 계산 (Gray를 안 써도 평균적 BER 평가용).
    """
    assert gt_idx.shape == dec_idx.shape
    # 심볼 에러를 직접 BER로 보는 것도 한 방법이지만,
    # 여기서는 index->bit로 변환해서 실제 bit 단위로 계산.
    gt_bits = int_to_bits(gt_idx, bits_per_sym)
    dec_bits = int_to_bits(dec_idx, bits_per_sym)
    return np.mean(gt_bits != dec_bits)


# ---------------------------------------------------------------------
# 메인 실험 루틴 (Q16)
# ---------------------------------------------------------------------
def run_q16(
    n_sym: int,
    ebn0_list,
    theta_std_deg: float,
    mu_phase: float,
    alpha_ref: float,
    seed: int,
):
    set_seed(seed)

    print("=== CoPBit Q16 – 2-lane M8 (p_ref + data), common phase-noise + AWGN v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_std_deg  = {theta_std_deg}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] alpha_ref      = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] seed           = {seed}")
    print()

    # -----------------------------
    # 1. 심볼 생성 (Lane0=p_ref, Lane1=data)
    # -----------------------------
    # Lane0: reference lane – 모든 심볼을 같은 M8 index로 고정
    k_ref_const = 0  # 각도=0도 (원하면 1→45°, 2→90° 등으로 바꿔도 OK)
    idx_ref = np.full(n_sym, k_ref_const, dtype=int)
    s_ref = m8_mod_from_idx(idx_ref)

    # Lane1: data lane – 랜덤 M8 데이터
    bits_data = np.random.randint(0, 2, size=3 * n_sym, dtype=int)
    s_data, idx_data = m8_mod_bits(bits_data)

    # -----------------------------
    # 2. 공통 phase-noise + AWGN 채널 통과
    # -----------------------------
    # (no-ISI, h=[1]) 가정
    print("[INFO] 채널: no-ISI (h=[1]), 공통 위상 노이즈 + AWGN")
    print()

    print("===============================================================")
    print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef       ")
    print("---------------------------------------------------------------")

    for eb in ebn0_list:
        # (1) 공통 phase noise
        y_ref_phase, y_data_phase = apply_common_phase_noise(
            s_ref, s_data, theta_std_deg=theta_std_deg
        )

        # (2) AWGN
        y_ref = add_awgn_ebn0(y_ref_phase, eb, bits_per_sym=3)
        y_data = add_awgn_ebn0(y_data_phase, eb, bits_per_sym=3)

        # -------------------------
        # Rx #1: no PLL (그냥 slicer)
        # -------------------------
        dec_sym_np, idx_dec_np = m8_slicer(y_data)
        ber_no_pll = ber_from_indices(idx_data, idx_dec_np, bits_per_sym=3)

        # -------------------------
        # Rx #2: data-only DD-PLL
        # -------------------------
        z_data_dd = phase_tracker_data_only(y_data, mu_phase=mu_phase)
        dec_sym_dd, idx_dec_dd = m8_slicer(z_data_dd)
        ber_dd = ber_from_indices(idx_data, idx_dec_dd, bits_per_sym=3)

        # -------------------------
        # Rx #3: data + p_ref Kuramoto
        # -------------------------
        z_data_kur = phase_tracker_data_plus_pref(
            y_ref=y_ref,
            y_data=y_data,
            s_ref=s_ref,
            mu_phase=mu_phase,
            alpha_ref=alpha_ref,
        )
        dec_sym_kur, idx_dec_kur = m8_slicer(z_data_kur)
        ber_kur = ber_from_indices(idx_data, idx_dec_kur, bits_per_sym=3)

        print(f" {eb:7.1f} |   {ber_no_pll:1.9f} |   {ber_dd:1.9f} |   {ber_kur:1.9f}")

    print("---------------------------------------------------------------")
    print()
    print("※ 주석")
    print(" - Lane0: p_ref lane – 모든 심볼이 동일한 8-PSK index(k_ref_const).")
    print(" - Lane1: data lane – 3bit/sym 랜덤 데이터.")
    print(" - 공통 위상 노이즈: Δφ ~ N(0, σ^2), σ=theta_std_deg[deg]를 rad로 변환 후 누적 (Wiener process).")
    print(" - No PLL       : data lane에 slicer만 적용.")
    print(" - Data-DD only : data lane만 보고 φ 업데이트 (1-lane PLL 근사).")
    print(" - Data+p_ref   : p_ref lane(s_ref vs z_ref) 에러 + data lane 에러를 섞어서 φ 업데이트.")
    print("   · total_err = (1-α)*err_ref + α*err_data (α=alpha_ref).")
    print("   · α→0 이면 p_ref 축에 더 강하게 락, α→1 이면 data-only PLL로 수렴.")
    print(" - 이 Q16 v0 실험은 2-lane 구조에서 p_ref가 실제로 공통 위상 드리프트에")
    print("   얼마나 도움을 주는지 보는 '최소 CoPBit 모델'에 해당한다.")
    print("   (multi-lane 64L Kuramoto를 2L로 축소한 개념 검증 단계).")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q16 – 2-lane M8 (p_ref + data), common phase-noise + AWGN v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000, help="심볼 수 (기본: 200000)")
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="8,10,12,14,16",
        help='Eb/N0 리스트 (쉼표 구분, 예: "8,10,12,14,16")',
    )
    parser.add_argument(
        "--theta_std_deg",
        type=float,
        default=3.0,
        help="심볼당 위상 증가량(Δφ)의 표준편차 [deg] (기본: 3deg)",
    )
    parser.add_argument(
        "--mu_phase",
        type=float,
        default=0.05,
        help="위상 트래커 step (기본: 0.05)",
    )
    parser.add_argument(
        "--alpha_ref",
        type=float,
        default=0.3,
        help="p_ref vs data 에러 비중 (0→ref-only, 1→data-only, 기본: 0.3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드 (기본: 1)",
    )

    args = parser.parse_args()
    ebn0_list = parse_ebn0_list(args.ebn0_list)

    run_q16(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        theta_std_deg=args.theta_std_deg,
        mu_phase=args.mu_phase,
        alpha_ref=args.alpha_ref,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()