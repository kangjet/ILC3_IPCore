#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q5 – 1-lane 4bit Phase BER with AWGN + ISI + Kuramoto-style cluster aid (v0.2)

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
# Kuramoto-style 시간축 위상 트래킹 디코더
# -----------------------------

def kuramoto_time_tracking_decode(
    y,
    const,
    theta_ref,
    isi_alpha: float,
    mu_phase: float = 0.05,
    use_preisi: bool = False,
):
    """
    Kuramoto 스타일의 '시간 축 위상 트래킹'을 반영한 디코더.

    - 입력:
      y         : 채널 출력 (complex, shape (N,))
      const     : 16포인트 CoPBit 컨스텔레이션 (complex, shape (16,))
      theta_ref : 16포인트 이상적 위상(rad), shape (16,)
      isi_alpha : 1-탭 ISI 계수 (0이면 ISI 없음)
      mu_phase  : 클러스터 위상 추적용 step size (0<mu<=1)
      use_preisi: True이면 Kuramoto 경로에서 간단한 1-탭 프리보상 적용

    - 출력:
      k_hat_kura: Kuramoto 기반 시간 트래킹 후의 하드 결정 인덱스(0..15), shape (N,)
    """
    y = np.asarray(y, dtype=np.complex128)
    N = y.shape[0]

    # 16포인트를 4개 클러스터(각 4포인트)로 나누는 인덱스
    def cluster_of_k(k):
        return k // 4

    # 이상적인 클러스터 중심(theta_center_ref[c])과
    # 클러스터 내 4포인트의 상대 오프셋(theta_offset[p])을 미리 계산
    theta_ref = np.asarray(theta_ref)
    cluster_centers_ref = np.zeros(4, dtype=np.float64)
    for c in range(4):
        theta_c = theta_ref[c * 4:(c + 1) * 4]
        z_c = np.mean(np.exp(1j * theta_c))
        cluster_centers_ref[c] = np.angle(z_c)

    # 클러스터 0의 중심 기준 상대 오프셋 패턴을 공용으로 사용
    theta_c0 = theta_ref[0:4]
    z_c0 = np.mean(np.exp(1j * theta_c0))
    center0 = np.angle(z_c0)
    theta_offset = wrap_angle(theta_c0 - center0)  # p=0..3

    # 클러스터 위상 추적 초기값: 이상적인 중심값으로 시작
    theta_center_hat = cluster_centers_ref.copy()

    k_hat_kura = np.zeros(N, dtype=np.int64)
    # ISI 프리보상을 위한 이전 심볼 결정값
    s_prev_hat = 0 + 0j

    for n in range(N):
        # 1) 필요시 간단한 1-탭 ISI 프리보상
        if use_preisi and isi_alpha != 0.0 and n > 0:
            y_eff = y[n] - isi_alpha * s_prev_hat
        else:
            y_eff = y[n]

        theta_rx = np.angle(y_eff)

        # 2) 현재 추정된 클러스터 중심(theta_center_hat)을 기준으로
        #    모든 k(0..15)에 대해 이상적 위상 후보를 구성하고 최근접 결정
        best_k = 0
        best_metric = 1e9
        for c in range(4):
            center_c = theta_center_hat[c]
            for p in range(4):
                k = c * 4 + p
                theta_k = center_c + theta_offset[p]
                diff = wrap_angle(theta_rx - theta_k)
                metric = diff * diff
                if metric < best_metric:
                    best_metric = metric
                    best_k = k

        k_hat_kura[n] = best_k
        c_hat = cluster_of_k(best_k)

        # 3) 해당 클러스터 중심을 EMA 형태로 업데이트 (Kuramoto-style)
        #    theta_center_hat[c] <- arg( (1-mu)*e^{j theta_old} + mu * e^{j theta_rx} )
        z_old = np.exp(1j * theta_center_hat[c_hat])
        z_new = (1.0 - mu_phase) * z_old + mu_phase * np.exp(1j * theta_rx)
        theta_center_hat[c_hat] = np.angle(z_new)

        # 4) ISI 프리보상을 위한 이전 심볼 갱신
        s_prev_hat = const[best_k]

    return k_hat_kura


# -----------------------------
# 채널 + 디코딩 시뮬레이션
# -----------------------------

def simulate_once(
    n_sym: int,
    snr_db: float,
    isi_alpha: float,
    seed: int = 0,
    mu_phase: float = 0.05,
    use_preisi: bool = False,
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

    # 5) Kuramoto-style 시간축 위상 트래킹 + (옵션) 1-탭 ISI 프리보상 기반 재디코딩
    k_hat_kura = kuramoto_time_tracking_decode(
        y=y,
        const=const,
        theta_ref=theta_ref,
        isi_alpha=isi_alpha,
        mu_phase=mu_phase,
        use_preisi=use_preisi,
    )

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
    parser = argparse.ArgumentParser(description="CoPBit Q5 – Kuramoto-aided BER with AWGN+ISI (v0.2)")
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
        "--mu_phase",
        type=float,
        default=0.05,
        help="Kuramoto-style 클러스터 위상 추적용 step size (0<mu<=1, 기본: 0.05)",
    )
    parser.add_argument(
        "--use_preisi",
        action="store_true",
        help="Kuramoto 경로에서 1-탭 ISI 프리보상(y[n]-alpha*s_hat[n-1])을 사용",
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

    print("=== CoPBit Q5 – 1-lane 4bit Phase BER with AWGN+ISI+Kuramoto (v0.2) ===")
    print(f"[Param] n_sym        = {args.n_sym}")
    print(f"[Param] snr_list[dB] = {snr_list}")
    print(f"[Param] isi_alpha    = {args.isi_alpha}")
    print(f"[Param] mu_phase     = {args.mu_phase}")
    print(f"[Param] use_preisi   = {args.use_preisi}")
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
            mu_phase=args.mu_phase,
            use_preisi=args.use_preisi,
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