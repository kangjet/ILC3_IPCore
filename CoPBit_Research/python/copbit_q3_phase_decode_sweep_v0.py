#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q3 – 4bit 위상 디코딩 BER 스윕 데모 v0.1

- Q1에서 정의한 16포인트(4bit) 위상 위성에 대해
- Kuramoto 동기화 없이, 단순 위상 AWGN + 최근접 위상 디코더만 포함한
  베이스라인 BER 곡선을 σ(phase_noise_std_deg) 스윕으로 측정하는 스크립트.

사용 예시:
    cd /Users/kangjet/ILC-4_CoPBit/CoPBit_Research/python

    # 기본 설정 (n_sym=10000, σ = 3,4,5,6,8 deg, seed=1)
    python copbit_q3_phase_decode_sweep_v0.py

    # σ 리스트를 바꾸고 싶은 경우
    python copbit_q3_phase_decode_sweep_v0.py --sigma_list 2,3,4,5,6 --n_sym 20000
"""

import numpy as np
import argparse


def wrap_phase(x: np.ndarray) -> np.ndarray:
    """[-pi, pi) 범위로 위상 래핑."""
    return (x + np.pi) % (2 * np.pi) - np.pi


def simulate_phase_decode(
    n_sym: int,
    phase_noise_std_deg: float,
    seed: int = 1,
) -> tuple[float, float]:
    """
    16포인트 위상 위성(4bit) + AWGN 위상 노이즈 + 최근접 위상 디코더에 대한
    심볼 정확도 / 비트 BER을 계산한다.

    - 맵핑: k = 0..15 → theta = 2πk/16
    - 디코딩: 수신 위상에 대해 |wrap(θ_rx−θ_k)|가 최소인 k_hat 선택
    """
    rng = np.random.default_rng(seed)

    # 16포인트 등간격 위상 테이블 (deg / rad)
    theta_table_deg = np.arange(16) * (360.0 / 16.0)
    theta_table = np.deg2rad(theta_table_deg)

    # 랜덤 4bit 심볼(k) 생성
    k_tx = rng.integers(0, 16, size=n_sym)

    # 송신 위상
    theta_tx = theta_table[k_tx]

    # AWGN 위상 노이즈 추가 (deg → rad)
    noise_deg = rng.normal(loc=0.0, scale=phase_noise_std_deg, size=n_sym)
    noise_rad = np.deg2rad(noise_deg)
    theta_rx = wrap_phase(theta_tx + noise_rad)

    # 최근접 위상 디코딩
    diff = wrap_phase(theta_rx[:, None] - theta_table[None, :])
    k_hat = np.argmin(np.abs(diff), axis=1)

    # 심볼 정확도
    sym_acc = float(np.mean(k_hat == k_tx))

    # 비트 BER 계산 (4bit/심볼)
    bits_tx = ((k_tx[:, None] >> np.arange(4)[::-1]) & 1)
    bits_hat = ((k_hat[:, None] >> np.arange(4)[::-1]) & 1)
    bit_err = np.mean(bits_tx != bits_hat)

    return sym_acc, float(bit_err)


def parse_sigma_list(s: str) -> list[float]:
    """쉼표로 구분된 σ 리스트 문자열을 float 리스트로 파싱."""
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q3 – 4bit 위상 디코딩 BER 스윕 데모 v0.1"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=10000,
        help="심볼 수 (default: 10000)",
    )
    parser.add_argument(
        "--sigma_list",
        type=str,
        default="3,4,5,6,8",
        help="위상 노이즈 표준편차(deg) 리스트, 콤마로 구분 (default: '3,4,5,6,8')",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드 (default: 1)",
    )
    args = parser.parse_args()

    sigma_values = parse_sigma_list(args.sigma_list)

    print("=== CoPBit Q3 – 4bit Phase Decode BER Sweep v0.1 ===")
    print(f"[Param] n_sym = {args.n_sym}")
    print(f"[Param] sigma_list (deg) = {sigma_values}")
    print(f"[Param] seed = {args.seed}")
    print("-" * 60)

    # 헤더 출력 (Q3 노트와 바로 대응되도록 포맷 통일)
    print(f"{'phase_noise_std_deg (°)':>23} | {'Symbol Accuracy':>15} | {'Bit BER':>12}")
    print("-" * 60)

    for sigma in sigma_values:
        sym_acc, ber = simulate_phase_decode(
            n_sym=args.n_sym,
            phase_noise_std_deg=sigma,
            seed=args.seed,
        )
        print(f"{sigma:23.1f} | {sym_acc:15.4f} | {ber:12.6e}")

    print("\n※ 주석")
    print(" - Q3-2 단일 실행을 σ 스윕 형태로 일반화한 베이스라인 스크립트.")
    print(" - Kuramoto 동기화 / 위상 트래킹이 없는 순수 위상 + 최근접 디코더 결과.")
    print(" - Q4에서 동일 σ 범위에 대해 Kuramoto-aided 디코딩과 비교 예정.")


if __name__ == "__main__":
    main()