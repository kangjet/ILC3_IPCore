#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q6 – PAM4 / CoPBit 4bit Modem BER Compare (AWGN-only, v0.1)

- 공통 조건에서 PAM4, CoPBit 4bit phase-only 모뎀의 BER vs SNR을 비교하기 위한 베이스라인 스크립트.
- 현재 버전(v0.1)은 채널 a/b/c + FFE/EQ는 아직 포함하지 않고,
  AWGN-only 기준 비교를 먼저 정리한다.
- 추후 확장:
  - channel_type="isi_a"/"isi_b"/"isi_c" + FFE/EQ 추가
  - ILC3 스킴을 별도 scheme으로 추가하여 3-way 비교까지 확장
"""

import argparse
import numpy as np


# -----------------------------
# 공통 유틸
# -----------------------------
def parse_snr_list(s: str):
    return [float(x) for x in s.split(",") if x.strip() != ""]


def ber_from_bits(b_tx: np.ndarray, b_rx: np.ndarray) -> float:
    assert b_tx.shape == b_rx.shape
    diff = (b_tx != b_rx)
    return diff.sum() / float(b_tx.size)


# -----------------------------
# PAM4 모뎀 (2bit / 심볼)
# -----------------------------
# Gray mapping 예:
#  00 -> -3
#  01 -> -1
#  11 -> +1
#  10 -> +3
PAM4_BITS = np.array(
    [
        [0, 0],
        [0, 1],
        [1, 1],
        [1, 0],
    ],
    dtype=np.int8,
)
PAM4_LEVELS = np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)


def pam4_mod(bits: np.ndarray) -> np.ndarray:
    """2bit씩 잘라 PAM4 심볼(-3,-1,+1,+3)로 맵핑."""
    assert bits.ndim == 1
    assert bits.size % 2 == 0
    b_pairs = bits.reshape(-1, 2)
    # 각 pair를 4가지 행과 비교해서 index 찾기
    # (작은 N에서는 이렇게 해도 충분)
    idx = np.zeros(b_pairs.shape[0], dtype=np.int64)
    for i, bp in enumerate(b_pairs):
        # (bp == PAM4_BITS).all(axis=1) 중 True인 index
        eq = (PAM4_BITS == bp).all(axis=1)
        idx[i] = int(np.nonzero(eq)[0][0])
    symbols = PAM4_LEVELS[idx]
    return symbols


def pam4_demod(y: np.ndarray) -> np.ndarray:
    """최근접 PAM4 레벨로 디코딩 후 2bit로 역맵핑."""
    # 거리 계산
    # y.shape = (N,)
    # PAM4_LEVELS.shape = (4,)
    # => (N,4)
    diff = np.abs(y[:, None] - PAM4_LEVELS[None, :])
    idx_hat = diff.argmin(axis=1)
    bits_hat = PAM4_BITS[idx_hat].reshape(-1)
    return bits_hat


# -----------------------------
# CoPBit 4bit phase-only (16-point) 모뎀
# -----------------------------
# Q1에서 정의한 16-point 균일 위상 맵핑 사용
COPBIT16_BITS = np.array(
    [[int(b) for b in f"{k:04b}"] for k in range(16)],
    dtype=np.int8,
)
COPBIT16_PHASE_DEG = np.array(
    [22.5 * k for k in range(16)],
    dtype=np.float64,
)  # 0,22.5,...,337.5
COPBIT16_PHASE_RAD = np.deg2rad(COPBIT16_PHASE_DEG)


def copbit4_mod(bits: np.ndarray) -> np.ndarray:
    """4bit -> 16-point unit circle complex symbol."""
    assert bits.ndim == 1
    assert bits.size % 4 == 0
    b4 = bits.reshape(-1, 4)
    idx = np.zeros(b4.shape[0], dtype=np.int64)
    for i, bp in enumerate(b4):
        eq = (COPBIT16_BITS == bp).all(axis=1)
        idx[i] = int(np.nonzero(eq)[0][0])
    theta = COPBIT16_PHASE_RAD[idx]
    s = np.exp(1j * theta)  # unit circle
    return s


def copbit4_demod(y: np.ndarray) -> np.ndarray:
    """complex 수신 심볼 y에 대해 최근접 위상 포인트로 디코딩."""
    # 수신 위상 추출 ([-pi, pi] 범위)
    theta_rx = np.angle(y)
    # 기준 위상 (0~2π)
    theta_ref = COPBIT16_PHASE_RAD
    # 각 수신 심볼에 대해 16개 레퍼런스와의 각도 차이 최소인 index 찾기
    # 각도 차이는 wrap-around 고려
    # diff = angle_normalize(theta_rx - theta_ref[k])
    # 효율을 위해 broadcasting 사용
    # theta_rx: (N,), theta_ref: (16,) -> (N,16)
    diff = theta_rx[:, None] - theta_ref[None, :]
    # [-pi, pi]로 fold
    diff = (diff + np.pi) % (2 * np.pi) - np.pi
    idx_hat = np.abs(diff).argmin(axis=1)
    bits_hat = COPBIT16_BITS[idx_hat].reshape(-1)
    return bits_hat


# -----------------------------
# 채널 + AWGN
# -----------------------------
def add_awgn_real(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """실수 baseband AWGN 채널."""
    # Es = 평균 심볼 에너지
    Es = np.mean(x ** 2)
    snr_linear = 10.0 ** (snr_db / 10.0)
    # 실수 1차원: sigma^2 = Es / SNR
    sigma2 = Es / snr_linear
    sigma = np.sqrt(sigma2)
    noise = rng.normal(loc=0.0, scale=sigma, size=x.shape)
    return x + noise


def add_awgn_complex(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """복소 baseband AWGN 채널."""
    Es = np.mean(np.abs(x) ** 2)
    snr_linear = 10.0 ** (snr_db / 10.0)
    # complex: 각 성분(I/Q) 분산 = Es / (2*SNR)
    sigma2 = Es / (2.0 * snr_linear)
    sigma = np.sqrt(sigma2)
    noise_real = rng.normal(loc=0.0, scale=sigma, size=x.shape)
    noise_imag = rng.normal(loc=0.0, scale=sigma, size=x.shape)
    return x + (noise_real + 1j * noise_imag)


# -----------------------------
# 메인 시뮬레이션 루프
# -----------------------------
def run_pam4(n_sym: int, snr_list, seed: int):
    rng = np.random.default_rng(seed)
    n_bits = n_sym * 2
    bits_tx = rng.integers(0, 2, size=n_bits, dtype=np.int8)
    s = pam4_mod(bits_tx)

    results = []
    for snr_db in snr_list:
        y = add_awgn_real(s, snr_db, rng)
        bits_rx = pam4_demod(y)
        ber = ber_from_bits(bits_tx, bits_rx)
        results.append((snr_db, ber))
    return results


def run_copbit4(n_sym: int, snr_list, seed: int):
    rng = np.random.default_rng(seed + 100)  # scheme별 seed offset
    n_bits = n_sym * 4
    bits_tx = rng.integers(0, 2, size=n_bits, dtype=np.int8)
    s = copbit4_mod(bits_tx)

    results = []
    for snr_db in snr_list:
        y = add_awgn_complex(s, snr_db, rng)
        bits_rx = copbit4_demod(y)
        ber = ber_from_bits(bits_tx, bits_rx)
        results.append((snr_db, ber))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q6 – PAM4 / CoPBit4 AWGN BER Compare (v0.1)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=100000,
        help="심볼 수 (각 스킴별)",
    )
    parser.add_argument(
        "--snr_list",
        type=str,
        default="10,12,14,16,18,20",
        help="쉼표로 구분된 SNR(dB) 리스트, 예: '10,12,14,16,18,20'",
    )
    parser.add_argument(
        "--schemes",
        type=str,
        default="pam4,copbit4",
        help="비교할 스킴 리스트, 예: 'pam4,copbit4'",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드",
    )

    args = parser.parse_args()
    snr_list = parse_snr_list(args.snr_list)
    scheme_list = [s.strip().lower() for s in args.schemes.split(",") if s.strip() != ""]

    print("=== CoPBit Q6 – PAM4 / CoPBit4 AWGN BER Compare v0.1 ===")
    print(f"[Param] n_sym        = {args.n_sym}")
    print(f"[Param] snr_list[dB] = {snr_list}")
    print(f"[Param] schemes      = {scheme_list}")
    print(f"[Param] seed         = {args.seed}")
    print("------------------------------------------------------------")

    all_results = {}

    for scheme in scheme_list:
        if scheme == "pam4":
            res = run_pam4(args.n_sym, snr_list, args.seed)
        elif scheme == "copbit4":
            res = run_copbit4(args.n_sym, snr_list, args.seed)
        else:
            print(f"[WARN] scheme '{scheme}'는 아직 구현되지 않음 (skip).")
            continue
        all_results[scheme] = res

    # 결과 출력
    if not all_results:
        print("[INFO] 유효한 scheme 결과가 없습니다. 종료.")
        return

    # 헤더 출력
    header = "SNR_dB"
    for scheme in scheme_list:
        if scheme in all_results:
            header += f" |  BER_{scheme:8s}"
    print(header)
    print("-" * len(header))

    for snr_db in snr_list:
        line = f"{snr_db:6.1f}"
        for scheme in scheme_list:
            if scheme in all_results:
                # 해당 scheme 결과에서 snr_db에 대응하는 BER 찾기
                ber_val = None
                for snr_i, ber_i in all_results[scheme]:
                    if abs(snr_i - snr_db) < 1e-9:
                        ber_val = ber_i
                        break
                if ber_val is None:
                    line += " |   n/a     "
                else:
                    line += f" | {ber_val:10.3e}"
        print(line)

    print("------------------------------------------------------------")
    print("※ 주석")
    print(" - 현재 버전(v0.1)은 AWGN-only 기준 BER 비교용 베이스라인입니다.")
    print(" - 향후: 채널 a/b/c + FFE/EQ + ILC3 스킴을 추가하여 3-way 비교로 확장 예정입니다.")


if __name__ == "__main__":
    main()