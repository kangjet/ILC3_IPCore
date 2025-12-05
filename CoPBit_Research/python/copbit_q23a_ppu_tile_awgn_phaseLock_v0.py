#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q23a – PPU 1024-lane 타일 (AWGN) + PhaseLock_std 검증 v0

- 8-PSK (M8) 기반 1024-lane 타일
- lane 0: p_ref (고정 심볼)
- lane 1..N-1: data lanes (random M8)
- 채널: AWGN + 공통 위상 노이즈 (theta_std)
- 모드:
  - noPLL    : 위상 추적 없음
  - DDonly   : data lanes만 이용한 위상 추적
  - DD+pRef  : p_ref + data lanes 혼합 위상 추적 (PhaseLock_std)

핵심 목표:
- Q16/Q22에서 확인한 PhaseLock_std 구조가
  1024-lane PPU 타일에서도 θ_std ≤ 1° 조건에서 안정적으로 동작하는지 확인.
"""

import argparse
import numpy as np


# -------------------------------------------------------------------
# 유틸: M8 맵핑 / 디코딩
# -------------------------------------------------------------------

def m8_constellation():
    """
    단위 원 위 8-PSK 심볼 집합 생성.
    index k = 0..7 -> exp(j * 2πk/8)
    """
    k = np.arange(8)
    return np.exp(1j * 2.0 * np.pi * k / 8.0)


CONST_M8 = m8_constellation()


def m8_map_indices_to_symbols(idx):
    """
    idx: (...,) int array in [0, 7]
    return: complex array same shape
    """
    return CONST_M8[idx]


def m8_hard_decode_indices(z):
    """
    8-PSK 심볼을 각도 기반으로 디코딩하여 index (0..7) 반환.

    z: complex array (...,)

    규칙:
    - angle in [0, 2π)로 변환
    - 각 섹터 너비 = π/4
    - 중심 기준으로 floor((angle + π/8)/(π/4)) mod 8
    """
    angles = np.angle(z)  # [-pi, pi]
    angles = np.mod(angles + 2.0 * np.pi, 2.0 * np.pi)  # [0, 2π)
    sector = np.floor((angles + (np.pi / 8.0)) / (np.pi / 4.0)).astype(np.int32)
    return np.mod(sector, 8)


# -------------------------------------------------------------------
# 유틸: Eb/N0 -> noise sigma
# -------------------------------------------------------------------

def ebn0_to_noise_sigma(ebn0_db, bits_per_sym=3, es=1.0):
    """
    Eb/N0(dB) -> complex AWGN sigma 계산.

    - Es = 1.0 (심볼 에너지)
    - bits_per_sym = log2(M) = 3 (M8)
    - Es/N0(dB) = Eb/N0(dB) + 10*log10(bits_per_sym)
    - N0 = Es / (10^(EsN0/10))
    - complex noise: Re, Im ~ N(0, N0/2)
      => sigma = sqrt(N0/2)
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * bits_per_sym
    n0 = es / esn0_lin
    sigma2 = n0 / 2.0
    return np.sqrt(sigma2)


# -------------------------------------------------------------------
# 시뮬레이션 코어
# -------------------------------------------------------------------

def generate_ppu_tile_symbols(n_sym, n_lanes, rng):
    """
    1024-lane PPU 타일용 심볼 시퀀스 생성.

    - lane 0: p_ref lane (고정 index 0)
    - lane 1..N-1: data lanes (random 0..7)

    return:
      idx  : (n_sym, n_lanes) int32
      x    : (n_sym, n_lanes) complex64
    """
    idx = rng.integers(low=0, high=8, size=(n_sym, n_lanes), dtype=np.int32)
    # p_ref lane은 항상 index 0으로 고정
    idx[:, 0] = 0
    x = m8_map_indices_to_symbols(idx)
    return idx, x


def add_awgn_and_phase_noise(x, ebn0_db, theta_std_deg, rng):
    """
    x: (n_sym, n_lanes) complex
    ebn0_db: float
    theta_std_deg: float (공통 위상 노이즈의 표준편차, degrees)
    """
    n_sym, n_lanes = x.shape
    sigma = ebn0_to_noise_sigma(ebn0_db, bits_per_sym=3, es=1.0)

    # AWGN
    noise = sigma * (rng.normal(size=(n_sym, n_lanes)) +
                     1j * rng.normal(size=(n_sym, n_lanes)))
    y = x + noise

    # 공통 위상 노이즈 (심볼마다 동일, 레인 전체 공유)
    theta_std_rad = np.deg2rad(theta_std_deg)
    if theta_std_rad > 0.0:
        phi_noise = rng.normal(loc=0.0, scale=theta_std_rad, size=(n_sym,))
        y *= np.exp(1j * phi_noise)[:, None]

    return y


def ber_from_symbol_errors(sym_err):
    """
    심볼 에러율을 "BER"로 간주 (3bit/sym이지만 여기서는 상대 비교용).
    sym_err: bool array
    """
    return np.mean(sym_err.astype(np.float64))


def simulate_no_pll(idx_true, x, y):
    """
    PhaseLock 없이(φ_hat = 0) 직접 디코딩하여 BER 계산.
    """
    # data lanes만 BER 계산 (lane 1..N-1)
    y_data = y[:, 1:]
    idx_true_data = idx_true[:, 1:]

    idx_hat_data = m8_hard_decode_indices(y_data)
    sym_err = (idx_hat_data != idx_true_data)
    ber = ber_from_symbol_errors(sym_err)
    return ber


def simulate_pll(idx_true, x, y, mu_phase, alpha_ref, mode="DD+pRef"):
    """
    단일 global PLL (PhaseLock_std) 시뮬레이션.

    mode:
      - "DDonly" : data lanes만 사용
      - "DD+pRef": p_ref + data lanes 혼합 (alpha_ref 비율)
    """
    n_sym, n_lanes = x.shape
    n_data = n_lanes - 1

    phi_hat = 0.0
    sym_err = np.zeros((n_sym, n_data), dtype=bool)

    for n in range(n_sym):
        # 현재 φ_hat 보정
        y_rot = y[n, :] * np.exp(-1j * phi_hat)

        # data 디코딩
        y_data = y_rot[1:]
        idx_hat_data = m8_hard_decode_indices(y_data)
        x_hat_data = m8_map_indices_to_symbols(idx_hat_data)

        # PLL 에러 계산
        # data 쪽 위상 에러 평균
        e_data = np.angle(y_data * np.conj(x_hat_data))
        e_data_mean = np.mean(e_data).real

        if mode == "DDonly":
            e = e_data_mean
        elif mode == "DD+pRef":
            # p_ref lane (lane 0): true 심볼과 관측값 비교
            x_ref = x[n, 0]
            y_ref = y_rot[0]
            e_ref = np.angle(y_ref * np.conj(x_ref))
            e = alpha_ref * e_ref + (1.0 - alpha_ref) * e_data_mean
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # φ_hat 업데이트 (간단한 1차 루프, 래핑은 생략)
        phi_hat += mu_phase * e

        # BER 계산용 sym error 저장
        idx_true_data = idx_true[n, 1:]
        sym_err[n, :] = (idx_hat_data != idx_true_data)

    return ber_from_symbol_errors(sym_err)


def run_q23a(n_sym, ebn0_list, theta_std_list, n_lanes, mu_phase, alpha_ref, seed):
    rng = np.random.default_rng(seed)

    print("=== CoPBit Q23a – 1024-lane PPU 타일 (AWGN) + PhaseLock_std v0 ===")
    print(f"[Param] n_sym        = {n_sym}")
    print(f"[Param] Eb/N0_list   = {ebn0_list}")
    print(f"[Param] theta_std(deg)= {theta_std_list}")
    print(f"[Param] n_lanes      = {n_lanes}")
    print(f"[Param] mu_phase     = {mu_phase}")
    print(f"[Param] alpha_ref    = {alpha_ref}")
    print(f"[Param] seed         = {seed}")
    print("")

    for theta_std_deg in theta_std_list:
        print(f"=== Q23a (theta_std_deg = {theta_std_deg:.3f}) ===")
        print("===============================================================")
        print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef   ")
        print("---------------------------------------------------------------")

        for eb in ebn0_list:
            # 심볼/노이즈 생성
            idx_true, x = generate_ppu_tile_symbols(n_sym, n_lanes, rng)
            y = add_awgn_and_phase_noise(x, eb, theta_std_deg, rng)

            # noPLL
            ber_no = simulate_no_pll(idx_true, x, y)

            # DDonly
            ber_dd = simulate_pll(idx_true, x, y,
                                  mu_phase=mu_phase,
                                  alpha_ref=alpha_ref,
                                  mode="DDonly")

            # DD+pRef
            ber_mix = simulate_pll(idx_true, x, y,
                                   mu_phase=mu_phase,
                                   alpha_ref=alpha_ref,
                                   mode="DD+pRef")

            print(f"  {eb:8.1f} |   {ber_no:10.6f} |   {ber_dd:10.6f} |   {ber_mix:10.6f}")

        print("---------------------------------------------------------------")
        print("")


# -------------------------------------------------------------------
# main
# -------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="CoPBit Q23a – 1024-lane PPU Tile + AWGN + PhaseLock_std 테스트"
    )
    p.add_argument("--n_sym", type=int, default=50000,
                   help="심볼 수 (default: 50000)")
    p.add_argument("--ebn0_list", type=str, default="12,14,16",
                   help="Eb/N0 dB 리스트, 콤마 구분 (default: '12,14,16')")
    p.add_argument("--theta_std_list", type=str, default="0.0,0.5,1.0,2.0",
                   help="위상 노이즈 표준편차(deg) 리스트, 콤마 구분")
    p.add_argument("--n_lanes", type=int, default=1024,
                   help="PPU 타일 레인 수 (default: 1024)")
    p.add_argument("--mu_phase", type=float, default=0.05,
                   help="위상 루프 스텝 사이즈 (default: 0.05)")
    p.add_argument("--alpha_ref", type=float, default=0.3,
                   help="p_ref 가중치 (0→ref-only, 1→data-only, default: 0.3)")
    p.add_argument("--seed", type=int, default=1,
                   help="난수 시드 (default: 1)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    ebn0_list = [float(x) for x in args.ebn0_list.split(",") if x.strip() != ""]
    theta_std_list = [float(x) for x in args.theta_std_list.split(",") if x.strip() != ""]

    run_q23a(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        theta_std_list=theta_std_list,
        n_lanes=args.n_lanes,
        mu_phase=args.mu_phase,
        alpha_ref=args.alpha_ref,
        seed=args.seed,
    )