#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q7 – 2bit + Guard Mode vs 4bit Mode BER Sweep (v0.1)

- 16-point phase constellation(Q1) 기반
- 모드1: 4bit/심볼 (기존 16-PSK 스타일, "copbit4")
- 모드2: 2bit/심볼 + guard (클러스터 축을 가드로 쓰고, p축에만 비트 매핑, "copbit2_guard")

비교:
- 같은 Es/N0 (심볼 에너지 기준 SNR)에서
  - 4bit 모드 BER
  - 2bit+guard 모드 BER
를 동시에 출력.

사용 예:
  python copbit_q7_guard_mode_ber_v0.py
  python copbit_q7_guard_mode_ber_v0.py --n_sym 200000 --snr_list 10,12,14,16,18,20
"""

import argparse
import numpy as np


def build_constellation_16():
    """Q1에서 사용한 16-point 위상 배치 재구성.
    index k = 0..15 에 대해:
      c = k // 4   (cluster index 0..3)
      p = k % 4    (intra index 0..3)
    θ_k = 2π * k / 16  (단순 16-PSK 스타일)
    """
    k = np.arange(16)
    theta = 2.0 * np.pi * k / 16.0
    sym = np.exp(1j * theta)  # unit circle
    c = k // 4
    p = k % 4
    return sym, theta, c, p


def awgn_complex(x, snr_db, rng):
    """Es/N0 = snr_db (dB) 기준 AWGN 채널.
    x: complex symbols, 평균 에너지를 Es로 맞춰서 노이즈 추가.
    """
    es = np.mean(np.abs(x) ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    n0 = es / snr_lin
    sigma = np.sqrt(n0 / 2.0)
    w = sigma * (rng.standard_normal(size=x.shape) + 1j * rng.standard_normal(size=x.shape))
    return x + w


def tx_copbit4_bits_to_symbols(bits, sym, c_lut, p_lut, rng):
    """4bit/심볼 모드 (기존 16-PSK 스타일).

    bits: shape (N*4,) 의 0/1
    sym : 16 complex points
    c_lut, p_lut: (0..15)에 대한 c, p 맵 (여기서는 단순 참고용)

    매핑:
      - 4bit → 정수 idx (0..15) (단순 binary → idx)
      - idx → sym[idx]
    """
    n_sym = bits.size // 4
    bits = bits.reshape(n_sym, 4)
    idx = bits[:, 0] * 8 + bits[:, 1] * 4 + bits[:, 2] * 2 + bits[:, 3]
    x = sym[idx]
    return x, idx


def rx_copbit4_symbols_to_bits(y, theta):
    """4bit/심볼 모드 디코딩:
    - 최근접 16 포인트 인덱스 찾고
    - 그 인덱스를 다시 4bit로 변환.

    반환:
      bits_hat: shape (N*4,)
    """
    angles = np.angle(y)
    angles = np.mod(angles, 2.0 * np.pi)  # [0, 2π)
    # 각 수신 심볼에 대해 16개 θ 중 가장 가까운 것 선택
    diff = angles[:, None] - theta[None, :]
    diff = np.angle(np.exp(1j * diff))  # wrap to (-π, π]
    idx_hat = np.argmin(np.abs(diff), axis=1)

    b0 = (idx_hat >> 3) & 1
    b1 = (idx_hat >> 2) & 1
    b2 = (idx_hat >> 1) & 1
    b3 = idx_hat & 1
    bits_hat = np.stack([b0, b1, b2, b3], axis=1).reshape(-1)
    return bits_hat


def tx_copbit2_guard_bits_to_symbols(bits, sym, c_lut, p_lut, rng):
    """2bit + guard 모드.

    설계:
      - payload bits: 2bit (b1 b0) -> p = 0..3
      - cluster c: 0..3을 '가드/중복' 축으로 사용.
        여기서는 단순히 c를 0..3 중 랜덤하게 선택해 줌.

    매핑 규칙:
      - p = payload (0~3)
      - c = rng.randint(0, 4)  (guard 차원, redundancy)
      - idx = 4*c + p
      - x = sym[idx]
    """
    n_sym = bits.size // 2
    bits = bits.reshape(n_sym, 2)
    payload = bits[:, 0] * 2 + bits[:, 1]  # 0..3
    # guard용 클러스터 인덱스 랜덤 선택
    c_guard = rng.integers(0, 4, size=n_sym)
    idx = 4 * c_guard + payload
    x = sym[idx]
    return x, idx, payload


def rx_copbit2_guard_symbols_to_bits(y, theta, p_lut):
    """2bit + guard 모드 디코딩.

    절차:
      - y를 가장 가까운 16포인트 θ_k에 매칭 → idx_hat
      - idx_hat 에서 p_hat = idx_hat % 4
      - p_hat을 2bit로 복원.

    여기서 c (=idx_hat//4)는 '가드' 차원이므로 무시.
    """
    angles = np.angle(y)
    angles = np.mod(angles, 2.0 * np.pi)
    diff = angles[:, None] - theta[None, :]
    diff = np.angle(np.exp(1j * diff))
    idx_hat = np.argmin(np.abs(diff), axis=1)

    p_hat = idx_hat % 4  # 0..3
    b1 = (p_hat >> 1) & 1
    b0 = p_hat & 1
    bits_hat = np.stack([b1, b0], axis=1).reshape(-1)
    return bits_hat


def ber_bits(b_true, b_hat):
    assert b_true.shape == b_hat.shape
    return np.mean(b_true != b_hat)


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q7 – 2bit+Guard vs 4bit BER Sweep (v0.1)"
    )
    parser.add_argument("--n_sym", type=int, default=100000,
                        help="심볼 수 (default: 100000)")
    parser.add_argument("--snr_list", type=str, default="10,12,14,16,18,20",
                        help="SNR(dB) 리스트, 콤마로 구분 (default: '10,12,14,16,18,20')")
    parser.add_argument("--seed", type=int, default=1,
                        help="난수 시드 (default: 1)")
    args = parser.parse_args()

    snr_list = [float(s) for s in args.snr_list.split(",")]
    n_sym = args.n_sym
    rng = np.random.default_rng(args.seed)

    # 16-point constellation
    sym, theta, c_lut, p_lut = build_constellation_16()

    print("=== CoPBit Q7 – 2bit+Guard vs 4bit BER Sweep (v0.1) ===")
    print(f"[Param] n_sym        = {n_sym}")
    print(f"[Param] snr_list[dB] = {snr_list}")
    print(f"[Param] seed         = {args.seed}")
    print("------------------------------------------------------------")
    print("SNR_dB | BER_copbit4 | BER_copbit2_guard")
    print("------------------------------------------------------------")

    for snr_db in snr_list:
        # 4bit 모드
        bits4 = rng.integers(0, 2, size=n_sym * 4, dtype=np.int64)
        x4, idx4 = tx_copbit4_bits_to_symbols(bits4, sym, c_lut, p_lut, rng)
        y4 = awgn_complex(x4, snr_db, rng)
        bits4_hat = rx_copbit4_symbols_to_bits(y4, theta)
        ber4 = ber_bits(bits4, bits4_hat)

        # 2bit + guard 모드
        bits2 = rng.integers(0, 2, size=n_sym * 2, dtype=np.int64)
        x2, idx2, payload = tx_copbit2_guard_bits_to_symbols(bits2, sym, c_lut, p_lut, rng)
        y2 = awgn_complex(x2, snr_db, rng)
        bits2_hat = rx_copbit2_guard_symbols_to_bits(y2, theta, p_lut)
        ber2 = ber_bits(bits2, bits2_hat)

        print(f"{snr_db:6.1f} |  {ber4:9.3e} |  {ber2:15.3e}")

    print("------------------------------------------------------------")
    print("※ 주석")
    print(" - BER_copbit4        : 4bit/심볼 16-PSK 스타일 (기존 CoPBit4 베이스라인)")
    print(" - BER_copbit2_guard  : 2bit payload + 2bit guard (클러스터 축을 가드/중복으로 사용)")
    print(" - 두 모드 모두 동일 Es/N0 조건에서 비교됨.")
    print(" - 예상: 고 SNR 영역에서 2bit+guard 모드 BER이 4bit 모드보다 유리하게 나오는지 확인하는 용도.")


if __name__ == "__main__":
    main()