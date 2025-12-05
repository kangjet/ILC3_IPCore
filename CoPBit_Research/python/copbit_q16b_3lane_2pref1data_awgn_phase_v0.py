#!/usr/bin/env python3
"""
CoPBit Q16b – 3-lane (2 p_ref + 1 data) M8, 공통 위상 노이즈 + AWGN v0

- Lane0, Lane1 : p_ref lane (고정된 8-PSK 심볼)
- Lane2        : data lane (랜덤 3bit/sym, M8)

테스트 목적:
  - 2개의 p_ref 레인을 사용했을 때, 공통 위상 드리프트(phase noise)에서
    data-only PLL 대비 BER이 어떻게 개선되는지 확인.
  - Q16 (2-lane: 1 p_ref + 1 data) 결과와 비교해,
    "P_ref 레인 수를 늘리면 허용 가능한 phase noise budget이 늘어난다"는
    CoPBit 설계 직관을 검증하기 위함.

출력:
  - Eb/N0별로
      BER_noPLL   : 위상 추적 없이 그냥 slicer
      BER_DDonly  : data lane만 보고 φ 업데이트 (1-lane PLL)
      BER_DD+2pRef: 2개의 p_ref + data를 섞어서 φ 업데이트
"""

import argparse
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(
        description="CoPBit Q16b – 3-lane (2 p_ref + 1 data) M8, common phase-noise + AWGN v0"
    )
    p.add_argument("--n_sym", type=int, default=200000,
                   help="심볼 수 (기본 200000)")
    p.add_argument(
        "--ebn0_list", type=str, default="12,14,16",
        help='Eb/N0(dB) 리스트, 예: "12,14,16"'
    )
    p.add_argument(
        "--theta_std_deg", type=float, default=3.0,
        help="위상 노이즈 스텝 표준편차 (deg, Wiener process step σ)"
    )
    p.add_argument(
        "--mu_phase", type=float, default=0.05,
        help="위상 추적 스텝 크기 (PLL/Kuramoto 쪽 μ)"
    )
    p.add_argument(
        "--alpha_ref", type=float, default=0.3,
        help="total_err = (1-α)*err_ref + α*err_data 에서 α (0→ref-only, 1→data-only)"
    )
    p.add_argument("--seed", type=int, default=1,
                   help="난수 시드")
    return p.parse_args()


def gen_m8_constellation():
    """Unit-circle 8-PSK (M8) 컨스텔레이션 생성"""
    M = 8
    k = np.arange(M)
    const = np.exp(1j * 2 * np.pi * k / M)
    return const  # shape=(8,)


def bits_table_m8():
    """
    심볼 index(0~7)를 3bit로 매핑하는 테이블.
    간단히 binary 표현 그대로 사용 (Gray 안 써도 상대 비교에는 문제 없음).
    """
    tbl = np.zeros((8, 3), dtype=int)
    for i in range(8):
        b2 = (i >> 2) & 1
        b1 = (i >> 1) & 1
        b0 = i & 1
        tbl[i] = [b2, b1, b0]
    return tbl  # shape=(8,3)


def add_awgn(x, ebn0_db, bits_per_sym=3):
    """
    복소 baseband x에 AWGN 추가.
    - 평균 심볼 에너지를 1로 보고, Eb/N0와 bits_per_sym으로 노이즈 variance 계산.
    """
    # 심볼 에너지 정규화
    Es = np.mean(np.abs(x) ** 2)
    if Es == 0:
        Es = 1.0
    # Eb/N0(dB) -> 선형
    ebn0_lin = 10 ** (ebn0_db / 10.0)
    # Es/N0 = Eb/N0 * (bits_per_sym)
    esn0_lin = ebn0_lin * bits_per_sym
    # complex noise: variance per complex sample = Es / esn0_lin
    noise_var = Es / esn0_lin
    noise_sigma = np.sqrt(noise_var / 2.0)  # per real/imag component
    n = noise_sigma * (np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape))
    return x + n


def slicer_m8(z, const):
    """
    M8 slicer: z를 가장 가까운 컨스텔레이션 index로 매핑.
    z: scalar complex
    const: shape=(8,)
    return: int index(0~7)
    """
    # |z - const|^2가 최소인 index
    d2 = np.abs(z - const) ** 2
    return int(np.argmin(d2))


def ber_from_syms(gt_sym, dec_sym, bits_tbl):
    """
    심볼 index 시퀀스(0~7) 기반 BER 계산.
    gt_sym, dec_sym: shape=(N,)
    bits_tbl: shape=(8,3)  (index -> 3bit)
    """
    gt_bits = bits_tbl[gt_sym]   # (N,3)
    dec_bits = bits_tbl[dec_sym] # (N,3)
    bit_err = np.sum(gt_bits != dec_bits)
    total_bits = gt_sym.size * 3
    return bit_err / total_bits


def run_q16b(n_sym, ebn0_list, theta_std_deg, mu_phase, alpha_ref, seed):
    np.random.seed(seed)

    # M8 컨스텔 + bit table
    const_m8 = gen_m8_constellation()
    const_conj = np.conjugate(const_m8)
    bits_tbl = bits_table_m8()

    # lane 구성
    # Lane0, Lane1: p_ref (고정 심볼 index)
    # Lane2       : data (랜덤 심볼 index)
    k_ref_const = 0  # ref lane은 심볼 0으로 고정 (1+0j)
    s_ref = const_m8[k_ref_const]

    # 데이터 심볼/비트 (3bit/sym)
    gt_sym = np.random.randint(0, 8, size=n_sym)  # 0~7

    print("=== CoPBit Q16b – 3-lane (2 p_ref + 1 data) M8, common phase-noise + AWGN v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_std_deg  = {theta_std_deg}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] alpha_ref      = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] seed           = {seed}")
    print(f"[Param] bits/symbol    = 3")
    print()
    print("[INFO] 채널: no-ISI (h=[1]), 3-lane (2 p_ref + 1 data), 공통 위상 노이즈 + AWGN")
    print()

    print("===============================================================")
    print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+2pRef    ")
    print("---------------------------------------------------------------")

    # 공통 위상 노이즈 (Wiener process)
    sigma_step = np.deg2rad(theta_std_deg)  # step std (rad)
    dphi = np.random.normal(loc=0.0, scale=sigma_step, size=n_sym)
    phi_noise = np.cumsum(dphi)  # 공통 phase drift

    # 정규화 channel: no-ISI => h=[1]
    for eb in ebn0_list:
        # === TX + 채널 + AWGN (모든 lane 동일 phi_noise 사용) ===
        # Lane0, Lane1: p_ref (고정 심볼)
        x_ref0 = s_ref * np.exp(1j * phi_noise)
        x_ref1 = s_ref * np.exp(1j * phi_noise)
        # Lane2: data
        x_data = const_m8[gt_sym] * np.exp(1j * phi_noise)

        # AWGN 추가
        y_ref0 = add_awgn(x_ref0, ebn0_db=eb, bits_per_sym=3)
        y_ref1 = add_awgn(x_ref1, ebn0_db=eb, bits_per_sym=3)
        y_data = add_awgn(x_data, ebn0_db=eb, bits_per_sym=3)

        # === 1) No PLL ===
        dec_sym_no = np.empty_like(gt_sym)
        for i in range(n_sym):
            z = y_data[i]  # 위상 보상 없이 그대로
            k_hat = slicer_m8(z, const_m8)
            dec_sym_no[i] = k_hat
        ber_no = ber_from_syms(gt_sym, dec_sym_no, bits_tbl)

        # === 2) Data-DD only PLL ===
        phi_hat_dd = 0.0
        dec_sym_dd = np.empty_like(gt_sym)
        for i in range(n_sym):
            # 현재 추정 위상 보상
            z_corr = y_data[i] * np.exp(-1j * phi_hat_dd)
            k_hat = slicer_m8(z_corr, const_m8)
            dec_sym_dd[i] = k_hat

            # decision-directed 에러: imag(z_corr * conj(s_hat))
            err_data = np.imag(z_corr * const_conj[k_hat])
            phi_hat_dd += mu_phase * err_data
        ber_dd = ber_from_syms(gt_sym, dec_sym_dd, bits_tbl)

        # === 3) Data + 2 p_ref lane PLL ===
        phi_hat_mix = 0.0
        dec_sym_mix = np.empty_like(gt_sym)
        for i in range(n_sym):
            # data lane
            z_data_corr = y_data[i] * np.exp(-1j * phi_hat_mix)
            k_hat = slicer_m8(z_data_corr, const_m8)
            dec_sym_mix[i] = k_hat
            err_data = np.imag(z_data_corr * const_conj[k_hat])

            # 두 개 p_ref lane
            z_ref0_corr = y_ref0[i] * np.exp(-1j * phi_hat_mix)
            z_ref1_corr = y_ref1[i] * np.exp(-1j * phi_hat_mix)
            err_ref0 = np.imag(z_ref0_corr * np.conjugate(s_ref))
            err_ref1 = np.imag(z_ref1_corr * np.conjugate(s_ref))
            err_ref = 0.5 * (err_ref0 + err_ref1)

            total_err = (1.0 - alpha_ref) * err_ref + alpha_ref * err_data
            phi_hat_mix += mu_phase * total_err

        ber_mix = ber_from_syms(gt_sym, dec_sym_mix, bits_tbl)

        print(
            f"{eb:10.1f} | "
            f"  {ber_no:10.6f} | "
            f"  {ber_dd:10.6f} | "
            f"  {ber_mix:10.6f}"
        )

    print("---------------------------------------------------------------")
    print()
    print("※ 주석")
    print(" - Lane0, Lane1: p_ref lane – 동일한 8-PSK index(k_ref_const)로 고정.")
    print(" - Lane2      : data lane – 3bit/sym 랜덤 데이터.")
    print(" - 공통 위상 노이즈: Δφ ~ N(0, σ^2), σ=theta_std_deg[deg]를 rad로 변환 후 누적 (Wiener).")
    print(" - No PLL       : data lane에 slicer만 적용.")
    print(" - Data-DD only : data lane만 보고 φ 업데이트 (1-lane PLL 근사).")
    print(" - Data+2pRef   : 2개의 p_ref lane 에러 + data lane 에러를 섞어서 φ 업데이트.")
    print("   · total_err = (1-α)*err_ref + α*err_data (α=alpha_ref).")
    print("   · α→0 이면 p_ref 축에 더 강하게 락, α→1 이면 data-only PLL에 가까워짐.")
    print(" - 이 Q16b 3-lane 실험은 2-lane(Q16) 대비 p_ref 레인 수를 2개로 늘렸을 때,")
    print("   θ_std_deg가 같은 조건에서 BER이 어떻게 바뀌는지 보는 테스트.")
    print("   (추후 64-lane Kuramoto 모델과의 스케일링 법칙 연결용).")


def main():
    args = parse_args()
    ebn0_list = [float(x) for x in args.ebn0_list.split(",") if x.strip()]
    run_q16b(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        theta_std_deg=args.theta_std_deg,
        mu_phase=args.mu_phase,
        alpha_ref=args.alpha_ref,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()