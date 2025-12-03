#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q8 – x16 lanes 4bit Phase BER with global phase drift + Kuramoto-style tracking (v0.1)

목표:
- 4bit / 16-point CoPBit 위상 맵핑 (Q1/Q3와 동일)
- 채널: x16 lane, 공통 글로벌 위상 드리프트 + AWGN
    y[n, l] = e^{j * phi[n]} * s[n, l] + w[n, l]
  여기서 phi[n]은 느리게 변하는 랜덤 워크(phase drift),
       w[n,l]은 Es/N0 기반 복소 AWGN
- 디코더:
  (1) Baseline:
      - 드리프트를 모르는 상태에서 각 lane 별로 단순 최근접 위상 디코딩
      - 글로벌 드리프트가 커지면 BER이 급격히 나빠지는 baseline
  (2) Kuramoto-style multi-lane tracking:
      - 모든 lane의 관측을 이용해 phi[n]을 추적 (decision-directed)
      - y[n,l] * conj(s_hat[n,l]) 를 lane 평균해서 공통 위상 추정
      - phi_hat[n]으로 보정 후 다시 디코딩
- 기대:
  - 동일 drift 조건에서 x16 Kuramoto tracking이 baseline 대비 BER를 크게 낮춰 줌
"""

import argparse
import numpy as np


# -----------------------------
# 공용 유틸
# -----------------------------

def db2lin(x_db: float) -> float:
    return 10.0 ** (x_db / 10.0)


def wrap_angle(theta):
    """[-pi, pi) 범위로 래핑"""
    return (theta + np.pi) % (2 * np.pi) - np.pi


# -----------------------------
# CoPBit 4bit 맵핑 (Q1/Q3와 동일)
# -----------------------------

def get_copbit_constellation():
    """
    4bit → 16포인트 위상 맵핑
    - theta_k: 0, 22.5, 45, ..., 337.5 [deg]
    - bits 순서는 k의 4비트 binary 표현 (0000~1111)
    """
    k = np.arange(16)
    bits = ((k[:, None] & (8, 4, 2, 1)) > 0).astype(int)
    theta_deg = 360.0 * k / 16.0
    theta = np.deg2rad(theta_deg)
    const = np.exp(1j * theta)  # unit circle
    return bits, theta, const  # bits[k,4], theta[k], const[k]


def indices_to_bits(k):
    k = np.asarray(k, dtype=np.int64)
    bits = ((k[:, None] & (8, 4, 2, 1)) > 0).astype(int)
    return bits


# -----------------------------
# x16 채널 + 디코딩 시뮬레이션
# -----------------------------

def simulate_x16_once(
    n_sym: int,
    snr_db: float,
    n_lanes: int,
    drift_std_deg: float,
    mu_phase: float,
    seed: int = 0,
):
    """
    - n_sym        : 심볼 수 (각 lane에 대해 4bit 심볼)
    - snr_db       : Es/N0 [dB] (각 lane 심볼 에너지 기준)
    - n_lanes      : lane 수 (기본 16)
    - drift_std_deg: 심볼 간 글로벌 위상 랜덤 워크 표준편차 [deg] (단계당)
    - mu_phase     : global phase 추정용 step size (0<mu<=1)
    - seed         : 난수 시드
    """
    rng = np.random.default_rng(seed)
    bits_ref, theta_ref, const = get_copbit_constellation()

    # 1) 랜덤 4bit 심볼 (n_sym, n_lanes, 4)
    bits_tx = rng.integers(0, 2, size=(n_sym, n_lanes, 4), dtype=np.int64)
    k_tx = (
        (bits_tx[..., 0] << 3)
        | (bits_tx[..., 1] << 2)
        | (bits_tx[..., 2] << 1)
        | (bits_tx[..., 3] << 0)
    )  # (n_sym, n_lanes)
    s_tx = const[k_tx]  # (n_sym, n_lanes), unit circle

    # 2) 글로벌 위상 드리프트 phi[n] (랜덤 워크)
    drift_std = np.deg2rad(drift_std_deg)
    phi = np.zeros(n_sym, dtype=np.float64)
    if drift_std > 0.0:
        for n in range(1, n_sym):
            phi[n] = phi[n - 1] + drift_std * rng.standard_normal()
    # shape (n_sym, 1)
    phase_factor = np.exp(1j * phi)[:, None]

    # 3) 채널: 글로벌 드리프트 + AWGN
    y = s_tx * phase_factor  # (n_sym, n_lanes)

    Es = 1.0  # unit circle
    snr_lin = db2lin(snr_db)
    N0 = Es / snr_lin
    noise = np.sqrt(N0 / 2.0) * (
        rng.standard_normal(size=y.shape) + 1j * rng.standard_normal(size=y.shape)
    )
    y += noise

    # -------------------------
    # (1) Baseline 디코딩 (drift 모른다고 가정)
    # -------------------------
    # 각 샘플을 그대로 16포인트에 매칭
    exp_rx = y / np.abs(y)  # unit circle projection, (n_sym, n_lanes)
    corr = exp_rx[..., None] * np.conj(const[None, None, :])  # (n_sym, n_lanes, 16)
    k_hat_base = np.argmax(np.real(corr), axis=-1)  # (n_sym, n_lanes)

    bits_hat_base = indices_to_bits(k_hat_base.reshape(-1)).reshape(n_sym, n_lanes, 4)
    bit_err_base = np.sum(bits_tx != bits_hat_base)
    ber_base = bit_err_base / (n_sym * n_lanes * 4.0)

    # -------------------------
    # (2) Kuramoto-style global phase tracking + 재디코딩
    #     - decision-directed, multi-lane averaging
    # -------------------------
    k_hat_kura = np.zeros((n_sym, n_lanes), dtype=np.int64)
    phi_hat = 0.0  # 초기 global phase 추정값

    for n in range(n_sym):
        # 2-1) 이전 추정값으로 글로벌 보정
        y_corr = y[n, :] * np.exp(-1j * phi_hat)  # (n_lanes,)

        # 2-2) 현재 심볼들의 하드 결정 (lane별)
        exp_rx_n = y_corr / np.abs(y_corr)
        corr_n = exp_rx_n[:, None] * np.conj(const[None, :])  # (n_lanes, 16)
        k_hat_n = np.argmax(np.real(corr_n), axis=1)  # (n_lanes,)
        k_hat_kura[n, :] = k_hat_n

        # 2-3) 결정된 심볼 기준으로 phi 측정 (decision-directed)
        s_hat_n = const[k_hat_n]  # (n_lanes,)
        # y[n,l] ≈ e^{j phi[n]} * s[n,l] + noise
        # → y[n,l] * conj(s_hat[n,l]) ≈ e^{j phi[n]} + noise
        z = y[n, :] * np.conj(s_hat_n)  # (n_lanes,)
        z_mean = np.mean(z)  # multi-lane 평균
        phi_meas = np.angle(z_mean)

        # 2-4) Kuramoto-style 1D 위상 업데이트
        phi_hat = np.angle(
            (1.0 - mu_phase) * np.exp(1j * phi_hat)
            + mu_phase * np.exp(1j * phi_meas)
        )

    # 2-5) 최종 결정 비트 계산
    bits_hat_kura = indices_to_bits(k_hat_kura.reshape(-1)).reshape(n_sym, n_lanes, 4)
    bit_err_kura = np.sum(bits_tx != bits_hat_kura)
    ber_kura = bit_err_kura / (n_sym * n_lanes * 4.0)

    return ber_base, ber_kura


# -----------------------------
# 메인: SNR 스윕
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q8 – x16 lanes 4bit Phase BER with global phase drift + Kuramoto tracking (v0.1)"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=20000,
        help="심볼 개수 per lane (기본: 20000)",
    )
    parser.add_argument(
        "--n_lanes",
        type=int,
        default=16,
        help="lane 수 (기본: 16)",
    )
    parser.add_argument(
        "--snr_list",
        type=str,
        default="10,12,14,16,18,20",
        help="SNR[dB] 리스트 (쉼표 구분, 예: 10,12,14,16,18,20)",
    )
    parser.add_argument(
        "--drift_std_deg",
        type=float,
        default=2.0,
        help="심볼 간 글로벌 위상 랜덤 워크 표준편차 [deg] (기본: 2.0)",
    )
    parser.add_argument(
        "--mu_phase",
        type=float,
        default=0.05,
        help="Kuramoto-style global phase 추정 step size (기본: 0.05)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드",
    )

    args = parser.parse_args()
    snr_list = [float(s) for s in args.snr_list.split(",") if s.strip() != ""]

    print("=== CoPBit Q8 – x16 lanes Phase BER with global drift + Kuramoto (v0.1) ===")
    print(f"[Param] n_sym         = {args.n_sym}")
    print(f"[Param] n_lanes       = {args.n_lanes}")
    print(f"[Param] snr_list[dB]  = {snr_list}")
    print(f"[Param] drift_std_deg = {args.drift_std_deg}")
    print(f"[Param] mu_phase      = {args.mu_phase}")
    print(f"[Param] seed          = {args.seed}")
    print("------------------------------------------------------------")
    print("SNR_dB |  BER_base   |  BER_kura")
    print("------------------------------------------------------------")

    for i, snr_db in enumerate(snr_list):
        ber_b, ber_k = simulate_x16_once(
            n_sym=args.n_sym,
            snr_db=snr_db,
            n_lanes=args.n_lanes,
            drift_std_deg=args.drift_std_deg,
            mu_phase=args.mu_phase,
            seed=args.seed + i,
        )
        print(
            f"{snr_db:6.1f} | "
            f"{ber_b:10.3e} | "
            f"{ber_k:10.3e}"
        )

    print("------------------------------------------------------------")
    print("※ 주석")
    print(" - BER_base : 글로벌 위상 드리프트를 무시하고 각 lane을 독립 16-PSK처럼 디코딩한 결과")
    print(" - BER_kura : x16 lane 관측을 이용해 phi[n]을 decision-directed 방식으로 추적 후 디코딩한 결과")
    print(" - drift_std_deg를 키우면, baseline은 빠르게 망가지고,")
    print("   Kuramoto tracking은 어느 정도까지 BER을 억제하는지 확인하는 용도.")


if __name__ == "__main__":
    main()