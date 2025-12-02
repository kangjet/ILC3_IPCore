#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q5 – 1-lane 4bit Phase BER with AWGN + ISI + Kuramoto-style cluster aid (v0.1)

- 4bit / 16-point CoPBit 위상 맵핑 사용 (Q1/Q3와 동일 기본 맵핑)
- 채널: 심볼레이트 기준 복소수 채널
    y[n] = s[n] + alpha * s[n-1] + w[n]
  여기서 w[n]은 Es/N0 기반 복소 AWGN
- 디코더:
  (1) Baseline: 단순 최근접 위상 디코더
  (2) Kuramoto-aided: 클러스터 평균 위상(circular mean) 보정 후 다시 디코딩
- FEC 가정:
  - 실제 FEC를 돌리지는 않고, pre-FEC BER가 1e-2 이하이면
    "강한 FEC로 충분히 커버 가능"하다고 보는 임계값 기반 평가.

사용 예시:
    python copbit_q5_kuramoto_ber_v0.py
    python copbit_q5_kuramoto_ber_v0.py --n_sym 200000 --snr_list 10,12,14,16,18 --isi_alpha 0.3
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


def bits_to_indices(bit_stream):
    """4bit 단위로 잘라 0~15 인덱스로 변환"""
    bit_stream = np.asarray(bit_stream).astype(int)
    assert bit_stream.size % 4 == 0
    bits_reshaped = bit_stream.reshape(-1, 4)
    k = (
        (bits_reshaped[:, 0] << 3)
        | (bits_reshaped[:, 1] << 2)
        | (bits_reshaped[:, 2] << 1)
        | (bits_reshaped[:, 3] << 0)
    )
    return k


def indices_to_bits(k):
    k = np.asarray(k, dtype=np.int64)
    bits = ((k[:, None] & (8, 4, 2, 1)) > 0).astype(int)
    return bits


# -----------------------------
# Kuramoto-style 클러스터 보정
# -----------------------------

def get_cluster_index_from_k(k):
    """
    16포인트를 4개 클러스터(각 4포인트)로 나누는 인덱스.
    k = 0~3   -> cluster 0
        4~7   -> cluster 1
        8~11  -> cluster 2
        12~15 -> cluster 3
    """
    return k // 4


def kuramoto_cluster_refine(theta_rx, k_hat_initial):
    """
    Kuramoto 동기화의 '집단 위상' 효과를
    간단한 cluster-wise circular mean 보정으로 근사.

    입력:
        theta_rx       : 수신 위상 (rad), 길이 N
        k_hat_initial  : 초기 하드 결정 결과(0~15, baseline NN 결과)

    출력:
        k_hat_refined  : 클러스터 평균 보정 후 재디코딩한 인덱스(0~15)
    """
    theta_rx = np.asarray(theta_rx)
    k_hat_initial = np.asarray(k_hat_initial)
    N = len(theta_rx)

    # 이상적인 16포인트 위상
    _, theta_ref, _ = get_copbit_constellation()

    # 클러스터 ID
    c_idx = get_cluster_index_from_k(k_hat_initial)

    # 클러스터별 circular mean 계산
    cluster_means = np.zeros(4, dtype=np.float64)
    for c in range(4):
        mask = (c_idx == c)
        if not np.any(mask):
            # 해당 클러스터에 심볼이 없으면 이상적인 중심값(참값 평균) 사용
            theta_c = theta_ref[c * 4:(c + 1) * 4]
            # 4포인트 평균
            z = np.mean(np.exp(1j * theta_c))
        else:
            z = np.mean(np.exp(1j * theta_rx[mask]))
        cluster_means[c] = np.angle(z)

    # 각 심볼에 대해, 같은 클러스터의 mean을 빼고 재디코딩
    theta_rx_corr = np.empty_like(theta_rx)
    for n in range(N):
        c = c_idx[n]
        theta_rx_corr[n] = wrap_angle(theta_rx[n] - cluster_means[c])

    # 각 클러스터에서 "상대 위상" 기준 4포인트(0,22.5,45,67.5deg)로 최근접 결정
    rel_theta_ref = theta_ref[:4]  # 0~3번 포인트의 위상(상대 기준)
    k_hat_refined = np.empty_like(k_hat_initial)
    for n in range(N):
        c = c_idx[n]
        # cluster c의 ideal phases는 theta_ref[c*4 + (0..3)]이지만,
        # mean을 뺀 상태에서는 0~3번 포인트와 동일 패턴.
        # 따라서 theta_rx_corr[n]을 rel_theta_ref에 매칭한 후
        # 전역 인덱스로 복원.
        diff = np.abs(wrap_angle(theta_rx_corr[n] - rel_theta_ref))
        p_hat = np.argmin(diff)  # 0..3
        k_hat_refined[n] = c * 4 + p_hat

    return k_hat_refined


# -----------------------------
# 채널 + 디코딩 시뮬레이션
# -----------------------------

def simulate_once(
    n_sym: int,
    snr_db: float,
    isi_alpha: float,
    seed: int = 0,
):
    """
    - n_sym: 심볼 수 (4bit 심볼)
    - snr_db: Es/N0 [dB] (심볼 에너지 기준)
    - isi_alpha: ISI 계수 (0이면 ISI 없음, 0.3~0.5 정도가 moderate)
    """
    rng = np.random.default_rng(seed)
    bits_ref, theta_ref, const = get_copbit_constellation()

    # 1) 랜덤 4bit 심볼 생성
    bit_stream = rng.integers(0, 2, size=n_sym * 4)
    k_tx = bits_to_indices(bit_stream)  # 0..15
    s_tx = const[k_tx]                 # unit circle complex

    # 2) ISI + AWGN 채널
    # y[n] = s[n] + alpha*s[n-1] + w[n]
    y = s_tx.astype(np.complex128).copy()
    if isi_alpha != 0.0:
        y[1:] += isi_alpha * s_tx[:-1]

    # 평균 심볼 에너지
    Es = np.mean(np.abs(s_tx) ** 2)
    snr_lin = db2lin(snr_db)
    N0 = Es / snr_lin
    # 복소 잡음: variance = N0 per complex symbol (즉, 각각 Re/Im var=N0/2)
    noise = np.sqrt(N0 / 2.0) * (rng.standard_normal(n_sym) + 1j * rng.standard_normal(n_sym))
    y += noise

    # 3) 수신 위상
    theta_rx = np.angle(y)

    # 4) Baseline 최근접 위상 디코더
    #    각 수신 위상을 16개 이상적인 위상에 매칭
    #    (방법: |e^{jθ_rx} - const_k|^2 최소 or angle 차 최소)
    exp_rx = np.exp(1j * theta_rx)  # unit circle project
    # 거리^2 = |a-b|^2 = |a|^2 + |b|^2 - 2Re(a b*)
    # 여기서는 |a|=|b|=1이므로 -> 2 - 2 Re(a b*)
    corr = exp_rx[:, None] * np.conj(const[None, :])  # shape (N,16)
    # Re가 최대인 k가 거리 최소인 k
    k_hat_baseline = np.argmax(np.real(corr), axis=1)

    # 5) Kuramoto-style cluster mean 보정 후 재디코딩
    k_hat_kura = kuramoto_cluster_refine(theta_rx, k_hat_baseline)

    # 6) BER 계산
    bits_tx = indices_to_bits(k_tx)
    bits_hat_baseline = indices_to_bits(k_hat_baseline)
    bits_hat_kura = indices_to_bits(k_hat_kura)

    bit_err_baseline = np.sum(bits_tx != bits_hat_baseline)
    bit_err_kura = np.sum(bits_tx != bits_hat_kura)

    ber_baseline = bit_err_baseline / (n_sym * 4.0)
    ber_kura = bit_err_kura / (n_sym * 4.0)

    return ber_baseline, ber_kura


# -----------------------------
# 메인: SNR 스윕 + FEC 임계 표시
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="CoPBit Q5 – Kuramoto-aided BER with AWGN+ISI (v0.1)")
    parser.add_argument(
        "--n_sym",
        type=int,
        default=100000,
        help="심볼 개수 (기본: 100000, 4bit 심볼이므로 비트는 4*n_sym)",
    )
    parser.add_argument(
        "--snr_list",
        type=str,
        default="10,12,14,16,18",
        help="시뮬할 SNR[dB] 리스트 (쉼표 구분, 예: 10,12,14,16,18)",
    )
    parser.add_argument(
        "--isi_alpha",
        type=float,
        default=0.3,
        help="1-탭 ISI 계수 alpha (0이면 ISI 없음, 기본: 0.3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드",
    )
    parser.add_argument(
        "--fec_threshold",
        type=float,
        default=1e-2,
        help="FEC 설계용 pre-FEC BER 임계값 (기본: 1e-2)",
    )

    args = parser.parse_args()

    snr_list = [float(s) for s in args.snr_list.split(",") if s.strip() != ""]

    print("=== CoPBit Q5 – 1-lane 4bit Phase BER with AWGN+ISI+Kuramoto (v0.1) ===")
    print(f"[Param] n_sym        = {args.n_sym}")
    print(f"[Param] snr_list[dB] = {snr_list}")
    print(f"[Param] isi_alpha    = {args.isi_alpha}")
    print(f"[Param] seed         = {args.seed}")
    print(f"[Param] FEC threshold (pre-FEC BER) = {args.fec_threshold:.1e}")
    print("------------------------------------------------------------")
    print("SNR_dB |  BER_base   |  BER_kura   | FEC_OK_base | FEC_OK_kura")
    print("------------------------------------------------------------")

    for i, snr_db in enumerate(snr_list):
        ber_b, ber_k = simulate_once(
            n_sym=args.n_sym,
            snr_db=snr_db,
            isi_alpha=args.isi_alpha,
            seed=args.seed + i,
        )
        fec_ok_b = ber_b <= args.fec_threshold
        fec_ok_k = ber_k <= args.fec_threshold

        print(
            f"{snr_db:6.1f} | "
            f"{ber_b:10.3e} | "
            f"{ber_k:10.3e} | "
            f"{str(fec_ok_b):>11s} | "
            f"{str(fec_ok_k):>11s}"
        )

    print("------------------------------------------------------------")
    print("※ 주석")
    print(" - BER_base  : Kuramoto 보정 없는 순수 최근접 위상 디코더 결과")
    print(" - BER_kura  : 클러스터별 circular mean 보정 후 재디코딩 결과")
    print(" - FEC_OK_*  : pre-FEC BER가 threshold 이하인지 여부")
    print(" - 실제 FEC(예: BCH/LDPC) 대신, pre-FEC BER 임계 기반의 '커버 가능 영역'만 표시한 베이스라인.")


if __name__ == "__main__":
    main()