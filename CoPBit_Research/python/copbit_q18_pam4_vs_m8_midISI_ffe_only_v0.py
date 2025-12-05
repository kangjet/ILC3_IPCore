#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q18 – PAM4 vs M8, mid-ISI + FFE only, BER vs Eb/N0 v0

- 채널: mid-ISI (Channel-b 스타일 5-tap, 심볼율 ISI)
- EQ   : 공통 FFE(LMS/NLMS), 위상 추적/CoPBit/Kuramoto 없음
- 비교 : PAM4 vs M8 단일 레인 기준 BER vs Eb/N0

주의:
- 이 스크립트는 "FFE-only baseline" 용도.
- 위상 잡음이나 p_ref, Kuramoto coupling 은 포함하지 않는다.
- apply_symbol_rate_channel(...) 에서 이미 지연을 중앙에 맞춰 잘라서
  Tx 심볼 인덱스와 채널 출력 인덱스가 1:1 대응이라고 가정한다.
- FFE에서도 추가 delay 를 두지 않고, n번째 FFE 출력 z[n]을
  n번째 Tx 심볼에 대응시켜 학습/검출한다.
"""

import argparse
import numpy as np


# -----------------------------
# 공통 유틸 함수들
# -----------------------------

def ints_to_bits(ints: np.ndarray, k: int) -> np.ndarray:
    """
    정수 배열(0..2^k-1)을 k비트 비트열로 변환.
    MSB-first.
    """
    ints = np.asarray(ints, dtype=int)
    n = ints.size
    bits = np.zeros(n * k, dtype=np.int8)
    for i, v in enumerate(ints):
        for b in range(k):
            shift = k - 1 - b
            bits[i * k + b] = (v >> shift) & 1
    return bits


def add_awgn(y: np.ndarray, ebn0_db: float, bits_per_sym: int) -> np.ndarray:
    """
    mid-ISI 채널 출력 y 에 대해 Eb/N0 기준 AWGN 추가.
    - Es는 현재 신호 y 의 평균 에너지로 근사.
    - Eb = Es / bits_per_sym
    - N0 = Eb / (10^(Eb/N0/10))
    - complex AWGN: N0/2 per dimension
    """
    y = np.asarray(y, dtype=np.complex128)
    # 현재 신호 에너지 기준으로 SNR 정의
    Es = np.mean(np.abs(y) ** 2)
    Eb = Es / bits_per_sym
    ebn0_linear = 10.0 ** (ebn0_db / 10.0)
    N0 = Eb / ebn0_linear
    noise_var = N0 / 2.0

    noise = np.sqrt(noise_var) * (
        np.random.standard_normal(y.shape) +
        1j * np.random.standard_normal(y.shape)
    )
    return y + noise


def apply_symbol_rate_channel(s: np.ndarray, h: np.ndarray) -> np.ndarray:
    """
    심볼율 mid-ISI 채널 적용.
    - h는 odd-length (예: 5-tap) 심볼율 채널
    - 'same' 모드 컨볼루션으로 중앙 지연을 맞춘다.
    """
    s = np.asarray(s, dtype=np.complex128)
    h = np.asarray(h, dtype=np.complex128)
    y = np.convolve(s, h, mode="same")
    return y


# -----------------------------
# 변조/슬라이서 정의 (PAM4, M8)
# -----------------------------

def map_pam4_from_ints(k_int: np.ndarray) -> np.ndarray:
    """
    PAM4 매핑: {0,1,2,3} → {-3, -1, +1, +3}
    (에너지 정규화는 여기서는 수행하지 않고, SNR은 add_awgn에서
     현재 신호 에너지 기준으로 정의한다.)
    """
    k_int = np.asarray(k_int, dtype=int)
    levels = np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)
    return levels[k_int]


def slicer_pam4(y: np.ndarray) -> np.ndarray:
    """
    PAM4 slicer: 실수축에서 {-3, -1, +1, +3} 중 가장 가까운 심볼 선택.
    """
    y = np.asarray(y, dtype=np.complex128)
    x = y.real
    levels = np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)
    idx = np.argmin(np.abs(x[:, None] - levels[None, :]), axis=1)
    return idx.astype(int)


def map_m8_from_ints(k_int: np.ndarray) -> np.ndarray:
    """
    M8 = 8-PSK 매핑: k → exp(j * 2πk/8)
    """
    k_int = np.asarray(k_int, dtype=int)
    M = 8
    angles = 2.0 * np.pi * k_int / M
    return np.exp(1j * angles)


def slicer_m8(y: np.ndarray) -> np.ndarray:
    """
    8-PSK slicer: 복소수 y에 대해 가장 가까운 8-PSK 포인트 인덱스 선택.
    """
    y = np.asarray(y, dtype=np.complex128)
    angles = np.angle(y)
    angles[angles < 0] += 2 * np.pi
    M = 8
    k_hat = np.round(angles / (2.0 * np.pi / M)) % M
    return k_hat.astype(int)


# -----------------------------
# FFE + LMS (NLMS) 본체
# -----------------------------

def run_ffe_lms(
    tx_sym_idx,
    bits_per_sym: int,
    map_func_sym,   # ints → constellation
    slicer_func,    # samples → ints
    ebn0_db_list,
    h_midISI,
    ffe_len: int,
    mu_ffe: float,
    train_frac: float,
    rng: np.random.Generator,
):
    """
    하나의 변조 방식(PAM4 또는 M8)에 대해
    mid-ISI + FFE-only 시스템의 BER vs Eb/N0 계산.

    중요 포인트:
      - apply_symbol_rate_channel(...)에서 이미 채널 지연을 중앙에 맞춰 잘라서
        Tx 심볼 인덱스와 채널 출력 인덱스가 1:1 대응이라고 가정한다.
      - 따라서 FFE에서 별도의 total_delay를 두지 않고, n번째 FFE 출력 z[n]을
        그대로 n번째 Tx 심볼에 대응시켜 학습/검출한다.
      - 업데이트는 Normalized LMS(NLMS)를 사용해 발산을 방지한다.
    """

    # Tx 심볼 인덱스 및 심볼 시퀀스
    tx_ints = np.array(tx_sym_idx, dtype=int)      # (n_sym,)
    s_tx = map_func_sym(tx_ints)                   # (n_sym,)
    n_sym = s_tx.shape[0]

    # mid-ISI 채널 통과 (노이즈 없는 기준)
    y_ch = apply_symbol_rate_channel(s_tx, h_midISI)   # (n_sym,)

    # 트레이닝 길이
    train_len = int(n_sym * train_frac)
    if train_len < ffe_len:
        train_len = ffe_len

    ber_list = []

    for ebn0_db in ebn0_db_list:
        # 각 Eb/N0마다 새 노이즈 생성
        # (현재 신호 y_ch 에너지 기준 Eb/N0)
        y_noisy = add_awgn(y_ch, ebn0_db, bits_per_sym=bits_per_sym)

        # FFE 초기화 (complex)
        w = np.zeros(ffe_len, dtype=np.complex128)
        w[ffe_len // 2] = 1.0 + 0j  # 중앙 탭 1로 시작

        r = y_noisy

        # 검출 결과 저장
        k_hat_all = np.zeros(n_sym, dtype=int)

        for n in range(n_sym):
            # 입력 벡터 u (최근 ffe_len 샘플, [r[n], r[n-1], ...])
            u = np.zeros(ffe_len, dtype=np.complex128)
            for l in range(ffe_len):
                idx = n - l
                if idx >= 0:
                    u[l] = r[idx]

            # FFE 출력
            z = np.vdot(w, u)   # w^H u

            # 트레이닝 or 디시전-디렉티드
            if n < train_len:
                # 트레이닝 단계: n번째 Tx 심볼을 정답으로 사용
                d_idx = tx_ints[n]
            else:
                # DD 단계: 이전 단계 결정 사용
                d_idx = slicer_func(np.array([z]))[0]

            d_sym = map_func_sym(np.array([d_idx]))[0]

            # 에러
            e = d_sym - z

            # Normalized LMS (NLMS) 업데이트
            norm_u2 = (u * np.conjugate(u)).real.sum() + 1e-12
            mu_eff = mu_ffe / norm_u2
            w = w + mu_eff * e * np.conjugate(u)

            # 발산 체크 (NaN/inf 방지)
            if not np.isfinite(w).all():
                print(f"[WARN] FFE coeff exploded at Eb/N0={ebn0_db}dB, stop updates for this SNR.")
                break

            # 최종 검출 (BER 계산용)
            k_det = slicer_func(np.array([z]))[0]
            k_hat_all[n] = k_det

        # BER 계산: 전체 구간 사용
        bits_tx = ints_to_bits(tx_ints, k=bits_per_sym)
        bits_hat = ints_to_bits(k_hat_all, k=bits_per_sym)
        ber = np.mean(bits_tx != bits_hat)
        ber_list.append(ber)

    return ber_list


# -----------------------------
# 메인 루틴 (CLI)
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q18 – PAM4 vs M8, mid-ISI + FFE-only BER vs Eb/N0 v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000)
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="10,12,14,16,18,20,22,24,26",
        help="comma-separated list, e.g. '10,12,14,16'"
    )
    parser.add_argument("--ffe_len", type=int, default=11)
    parser.add_argument("--train_frac", type=float, default=0.5)
    parser.add_argument("--mu_ffe", type=float, default=0.003)
    parser.add_argument("--seed", type=int, default=1)

    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_list = [float(x) for x in args.ebn0_list.split(",") if x.strip()]
    ffe_len = args.ffe_len
    train_frac = args.train_frac
    mu_ffe = args.mu_ffe
    seed = args.seed

    rng = np.random.default_rng(seed)

    # mid-ISI 채널 (Channel-b 스타일, 5-tap, 정규화)
    h_raw = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=np.float64)
    h_midISI = h_raw / np.sum(h_raw)

    print("=== CoPBit Q18 – PAM4 vs M8 (Channel-b mid-ISI, FFE only) BER vs Eb/N0 v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] ffe_len        = {ffe_len}")
    print(f"[Param] train_frac     = {train_frac}")
    print(f"[Param] mu_ffe         = {mu_ffe}")
    print(f"[Param] seed           = {seed}")
    print()
    print(f"[Chan ] h_midISI (norm) = {h_midISI.tolist()}")
    print("[Info ] FFE-only baseline (PAM4 vs M8, single-lane)")
    print()

    # Tx 심볼 생성
    tx_idx_pam4 = rng.integers(0, 4, size=n_sym, dtype=int)
    tx_idx_m8 = rng.integers(0, 8, size=n_sym, dtype=int)

    # PAM4 FFE
    ber_pam4 = run_ffe_lms(
        tx_sym_idx=tx_idx_pam4,
        bits_per_sym=2,
        map_func_sym=map_pam4_from_ints,
        slicer_func=slicer_pam4,
        ebn0_db_list=ebn0_list,
        h_midISI=h_midISI,
        ffe_len=ffe_len,
        mu_ffe=mu_ffe,
        train_frac=train_frac,
        rng=rng,
    )

    # M8 FFE
    ber_m8 = run_ffe_lms(
        tx_sym_idx=tx_idx_m8,
        bits_per_sym=3,
        map_func_sym=map_m8_from_ints,
        slicer_func=slicer_m8,
        ebn0_db_list=ebn0_list,
        h_midISI=h_midISI,
        ffe_len=ffe_len,
        mu_ffe=mu_ffe,
        train_frac=train_frac,
        rng=rng,
    )

    # 결과 출력
    print("===============================================================")
    print(" Eb/N0_dB |  BER_PAM4_FFE  |  BER_M8_FFE  ")
    print("---------------------------------------------------------------")
    for snr_db, ber_p, ber_m in zip(ebn0_list, ber_pam4, ber_m8):
        print(f"{snr_db:10.1f} | {ber_p:13.9f} | {ber_m:11.9f}")
    print("---------------------------------------------------------------")


if __name__ == "__main__":
    main()