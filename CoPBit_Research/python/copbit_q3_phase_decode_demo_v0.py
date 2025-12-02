#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q3-2 – 4bit 위상 디코딩 + 노이즈 BER 데모 v0.1

- Q1: 16포인트 위성(4bit) 정의
- Q3-1: (c,p) 비트 매핑 규칙 점검
- Q3-2: 랜덤 4bit → 위상 매핑 → 위상 노이즈 추가 → 최근접 포인트 디코딩 → BER 계산

※ 여기서는 Kuramoto 동기화 대신,
   단순 위상 AWGN + 최근접 위상 포인트 디코더만 사용.
   (Kuramoto-aided 디코딩은 Q4에서 별도 실험으로 확장 예정.)
"""

import math
import numpy as np


def make_constellation_q1():
    """
    Q1에서 사용한 16포인트 위성 정의를 그대로 사용.
    k = 0..15 에 대해:
      - theta0[k] = 2π * k / 16  (기본 위상)
      - c_true = k // 4         (클러스터 index: 0..3)
      - p_true = k % 4          (클러스터 내부 index: 0..3)
    """
    N = 16
    theta0 = np.zeros(N, dtype=float)
    cluster_idx = np.zeros(N, dtype=int)

    for k in range(N):
        theta0[k] = 2.0 * math.pi * k / N
        c = k // 4  # 0..3
        cluster_idx[k] = c

    return theta0, cluster_idx


def encode_bits(c, p):
    """
    상위 2비트 = c (0..3), 하위 2비트 = p (0..3)
    → 4bit 값 B(0..15)로 인코딩.
    """
    assert 0 <= c < 4
    assert 0 <= p < 4
    return (c << 2) | p


def decode_bits(B):
    """
    4bit 값 B(0..15)를 (c,p)로 역변환.
    c = 상위 2비트, p = 하위 2비트.
    """
    assert 0 <= B < 16
    c = (B >> 2) & 0b11
    p = B & 0b11
    return c, p


def wrap_angle(x):
    """
    실수 x(rad)를 [-π, π) 범위로 wrap.
    """
    return (x + math.pi) % (2.0 * math.pi) - math.pi


def nearest_constellation_point(theta_rx, theta_table):
    """
    수신 위상 theta_rx(rad)에 대해
    16포인트 위성(theta_table) 중 최근접 포인트 index(k_hat)를 반환.
    """
    # 원형 위상 거리 |wrap(θ_rx - θ_k)| 가 최소인 k 찾기
    diff = theta_rx - theta_table
    diff_wrapped = np.vectorize(wrap_angle)(diff)
    k_hat = int(np.argmin(np.abs(diff_wrapped)))
    return k_hat


def simulate_phase_ber(
    n_sym=10000,
    phase_noise_std_deg=5.0,
    seed=1,
):
    """
    Q3-2 메인 실험:
      - n_sym: 심볼 개수
      - phase_noise_std_deg: 위상 노이즈 표준편차(도 단위)
    리턴: (acc_sym, ber_bit)
    """
    rng = np.random.default_rng(seed)

    theta_table, _ = make_constellation_q1()

    # radian 단위 노이즈 표준편차
    sigma_rad = math.radians(phase_noise_std_deg)

    # 결과 집계
    sym_err = 0
    bit_err = 0

    for _ in range(n_sym):
        # 1) 랜덤 4bit 심볼 B_tx (0..15)
        B_tx = rng.integers(0, 16)
        c_tx, p_tx = decode_bits(B_tx)

        # 2) 위상 매핑: k = c*4 + p  → theta = 2π k / 16
        k_tx = (c_tx << 2) | p_tx
        theta_tx = theta_table[k_tx]

        # 3) 위상 노이즈 추가 (AWGN on phase)
        noise = rng.normal(loc=0.0, scale=sigma_rad)
        theta_rx = wrap_angle(theta_tx + noise)

        # 4) 디코딩: 최근접 위상 포인트 선택
        k_hat = nearest_constellation_point(theta_rx, theta_table)
        B_rx = k_hat  # k_hat은 0..15 → 그대로 4bit 코드로 사용

        # 5) 에러 계산
        if B_rx != B_tx:
            sym_err += 1
            # 심볼이 틀렸으면, 최소 1bit 이상 에러.
            # 정확한 bit 에러 카운트:
            diff_bits = B_tx ^ B_rx  # 서로 다른 비트 위치
            bit_err += bin(diff_bits).count("1")

    acc_sym = 1.0 - sym_err / float(n_sym)
    ber_bit = bit_err / float(n_sym * 4)  # 4bit 심볼

    return acc_sym, ber_bit


def main():
    n_sym = 10000
    phase_noise_std_deg = 5.0
    seed = 1

    print("=== CoPBit Q3-2 Phase Decode Demo v0.1 ===")
    print(f"[Param] n_sym              = {n_sym}")
    print(f"[Param] phase_noise_std_deg = {phase_noise_std_deg:.3f} deg")
    print(f"[Param] seed                = {seed}")
    print("---------------------------------------------")

    acc_sym, ber_bit = simulate_phase_ber(
        n_sym=n_sym,
        phase_noise_std_deg=phase_noise_std_deg,
        seed=seed,
    )

    print(f"[Result] Symbol accuracy = {acc_sym:.6f}")
    print(f"[Result] Bit BER         = {ber_bit:.6e}")
    print()
    print("※ 주석:")
    print(" - 이 실험은 Kuramoto 동기화 없이,")
    print("   단순 위상 AWGN + 최근접 위상 포인트 디코더 구조만 포함한 베이스라인입니다.")
    print(" - Kuramoto 기반 위상 동기화 + 디코딩 개선 실험은 Q4에서 별도 스크립트로 확장 예정입니다.")


if __name__ == "__main__":
    main()