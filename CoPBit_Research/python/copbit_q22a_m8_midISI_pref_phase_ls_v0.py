#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q22a – M8 mid-ISI (Channel-b) + FFE(LS) + common phase-noise + p_ref PLL v0

- 채널: Channel-b mid-ISI (5-tap, ILC3/CoPBit 공통 mid-ISI 채널과 동일 계수)
- Equalizer: 단일 공통 FFE, LS(least-squares) 기반 고정 계수
- 레인 구조: 2-lane (Lane0 = p_ref, Lane1 = data), 둘 다 동일 채널 + 동일 FFE 공유
- 위상 노이즈: 공통 위상 노이즈 (Wiener process), θ_std_deg 로 per-symbol 증분 표준편차 지정
- PLL 모드:
    · No PLL      : 위상 추적 없이 slicer만
    · Data-DD only: data lane 에러만으로 φ 추적
    · Data+p_ref  : p_ref + data 에러를 alpha_ref 비율로 섞어서 φ 추적

이 스크립트는 Q16_midISI / Q16d 에서 사용한 2-lane(p_ref + data) 위상 잠금 구조를
Q21a/Q21b의 mid-ISI + FFE(LS) 환경 위에 올린 "메모리/버스용 CoPBit" 테스트 코드이다.
"""

import argparse
import numpy as np
from typing import Tuple, List


# ---------------------------------------------------------------------------
# 기본 유틸: 8-PSK 맵, 비트 변환, slicer
# ---------------------------------------------------------------------------

M = 8
BITS_PER_SYM = 3


def gen_constellation_m8() -> np.ndarray:
    """단위 반지름 8-PSK 컨스텔레이션 (k=0..7)."""
    k = np.arange(M)
    return np.exp(1j * 2.0 * np.pi * k / M)


CONST_M8 = gen_constellation_m8()


def bits_from_indices(k: np.ndarray) -> np.ndarray:
    """심볼 인덱스(0..7)에서 3비트(binary)로 변환 (shape: [N, 3])."""
    k = k.astype(np.int64)
    return np.stack([
        (k >> 2) & 1,
        (k >> 1) & 1,
        (k >> 0) & 1,
    ], axis=-1).astype(np.int8)


def slicer_8psk(y: np.ndarray) -> np.ndarray:
    """8-PSK slicer: 각 샘플을 가장 가까운 8-PSK 포인트 인덱스(0..7)로 맵핑."""
    ang = np.angle(y)
    ang[ang < 0] += 2.0 * np.pi
    sector = 2.0 * np.pi / M
    # 중심기준 라운딩 후 모듈러
    k_hat = np.floor((ang + sector / 2.0) / sector).astype(np.int64) % M
    return k_hat


# ---------------------------------------------------------------------------
# 채널 / 잡음 / FFE(LS)
# ---------------------------------------------------------------------------


def make_mid_isi_channel() -> np.ndarray:
    """ILC3/CoPBit에서 사용하는 mid-ISI 5-tap 채널 계수."""
    h = np.array([0.1, 0.4, 1.0, 0.4, 0.1], dtype=np.float64)
    h = h / np.sum(h)
    return h.astype(np.complex128)


H_MID_ISI = make_mid_isi_channel()


def apply_channel_mid_isi(s: np.ndarray, h: np.ndarray) -> np.ndarray:
    """중간 ISI 채널 통과 (convolution, same-length)."""
    y = np.convolve(s, h, mode="same")
    return y


def add_awgn(x: np.ndarray, ebn0_db: float, bits_per_sym: int, rng: np.random.RandomState) -> np.ndarray:
    """Eb/N0[dB] 기준 AWGN 추가.

    - x: baseband 심볼 시퀀스
    - bits_per_sym: 심볼당 비트 수 (M8 → 3)
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    Es = np.mean(np.abs(x) ** 2)
    # Eb/N0 = Es / (k * N0)  →  N0 = Es / (k * Eb/N0)
    N0 = Es / (bits_per_sym * ebn0_lin)
    sigma2 = N0  # complex baseband에서 E|n|^2 = N0
    noise = (rng.randn(*x.shape) + 1j * rng.randn(*x.shape)) * np.sqrt(sigma2 / 2.0)
    return x + noise


def ls_ffe_train(r: np.ndarray, d: np.ndarray, L: int, train_frac: float, ridge: float = 1e-6) -> np.ndarray:
    """단일 레인 기준 LS FFE 학습.

    r: 채널 + 노이즈가 섞인 수신 신호 (complex, len = N)
    d: 타겟 심볼 (complex, len = N) – 여기서는 data lane 심볼
    L: FFE 길이
    train_frac: 학습에 사용할 심볼 비율 (0~1)
    ridge: R 행렬 정규화용 작은 값 (수치적 안정성 개선)
    """
    N = len(r)
    n_train = int(N * train_frac)
    n_train = max(L, min(n_train, N - L))  # 최소/최대 범위 제한

    U = np.zeros((n_train, L), dtype=np.complex128)
    d_vec = np.zeros((n_train,), dtype=np.complex128)

    center = L // 2

    for n in range(n_train):
        # r[n .. n+L-1]
        U[n, :] = r[n : n + L]
        d_vec[n] = d[n + center]

    # R = U^H U, p = U^H d
    R = U.conj().T @ U
    p = U.conj().T @ d_vec

    R += ridge * np.eye(L, dtype=np.complex128)

    w = np.linalg.solve(R, p)
    return w


def apply_ffe(r: np.ndarray, w: np.ndarray) -> np.ndarray:
    """FFE 적용 (convolution, same-length)."""
    y_eq = np.convolve(r, w, mode="same")
    return y_eq


# ---------------------------------------------------------------------------
# 위상 노이즈 + PLL (2-lane: p_ref + data)
# ---------------------------------------------------------------------------


def gen_phase_noise(theta_std_deg: float, N: int, rng: np.random.RandomState) -> np.ndarray:
    """Wiener 공정 기반 공통 위상 노이즈 시퀀스 φ[n].

    theta_std_deg: per-symbol 증분 표준편차(도)
    N: 길이
    """
    if theta_std_deg <= 0.0:
        return np.zeros(N, dtype=np.float64)

    theta_std_rad = theta_std_deg * np.pi / 180.0
    dphi = rng.randn(N) * theta_std_rad
    phi = np.cumsum(dphi)
    return phi


def pll_detect_data_lane(
    z_ref: np.ndarray,
    z_data: np.ndarray,
    mu_phase: float,
    alpha_ref: float,
    use_pref: bool,
    k_ref_const: int = 0,
) -> np.ndarray:
    """2-lane(p_ref + data) 공통 PLL을 돌려 data lane 비트 검출.

    z_ref, z_data: FFE 이후 + 공통 위상 노이즈가 걸린 레인별 시퀀스
    mu_phase: PLL 스텝 크기
    alpha_ref: total_err = (1-α)*e_ref + α*e_data 의 α
    use_pref: True → p_ref + data 혼합, False → data-only PLL
    k_ref_const: p_ref lane의 고정 인덱스 (기본 0)

    반환: data lane 검출 비트 배열 (shape: [N, 3])
    """
    N = len(z_data)
    bits_hat = np.zeros((N, BITS_PER_SYM), dtype=np.int8)

    s_ref_const = CONST_M8[k_ref_const]
    phi_hat = 0.0

    for n in range(N):
        rot = np.exp(-1j * phi_hat)
        y_ref = z_ref[n] * rot
        y_data = z_data[n] * rot

        # data lane 심볼 결정
        k_data_hat = int(slicer_8psk(np.array([y_data]))[0])
        s_data_hat = CONST_M8[k_data_hat]

        bits_hat[n, :] = bits_from_indices(np.array([k_data_hat]))[0]

        # phase error
        e_data = np.angle(y_data * np.conj(s_data_hat))

        if use_pref:
            e_ref = np.angle(y_ref * np.conj(s_ref_const))
            e_total = (1.0 - alpha_ref) * e_ref + alpha_ref * e_data
        else:
            e_total = e_data

        phi_hat += mu_phase * e_total

    return bits_hat


# ---------------------------------------------------------------------------
# 메인 시뮬레이션 루프
# ---------------------------------------------------------------------------


def simulate_q22a(
    n_sym: int,
    ebn0_list: List[float],
    theta_std_list: List[float],
    ffe_len: int,
    train_frac: float,
    mu_phase: float,
    alpha_ref: float,
    seed: int,
) -> None:
    rng = np.random.RandomState(seed)

    print("=== CoPBit Q22a – M8 mid-ISI + FFE(LS) + common phase-noise + p_ref PLL v0 ===")
    print(f"[Param] n_sym       = {n_sym}")
    print(f"[Param] Eb/N0_list  = {ebn0_list}")
    print(f"[Param] theta_std   = {theta_std_list} (deg)")
    print(f"[Param] ffe_len     = {ffe_len}")
    print(f"[Param] train_frac  = {train_frac}")
    print(f"[Param] mu_phase    = {mu_phase}")
    print(f"[Param] alpha_ref   = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] seed        = {seed}")
    print()

    print(f"[Chan ] h_midISI (norm) = {H_MID_ISI}")
    print("[Info ] 수신 구조: mid-ISI + AWGN → 공통 FFE(M8, LS) → 공통 위상 노이즈 → 2-lane PLL")
    print("[Info ] 레인 구조:")
    print("        - Lane0: p_ref lane (고정 8-PSK index)")
    print("        - Lane1: data lane (3bit/sym 랜덤 데이터)")
    print("[Info ] PLL 모드:")
    print("        - No PLL      : data lane에 slicer만 적용")
    print("        - Data-DD only: data lane 에러만으로 공통 φ 추적")
    print("        - Data+p_ref  : p_ref + data 에러를 alpha_ref 비율로 섞어 φ 추적")
    print()

    # 결과 저장: dict[theta][ebn0] = (ber_noPLL, ber_dd, ber_pref)
    results = {theta: [] for theta in theta_std_list}

    for theta_std_deg in theta_std_list:
        print(f"=== Q22a (theta_std_deg = {theta_std_deg}) ===")
        print("===============================================================")
        print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef       ")
        print("---------------------------------------------------------------")

        for ebn0_db in ebn0_list:
            # 1) 데이터 생성 (data lane용)
            k_tx = rng.randint(0, M, size=n_sym)
            s_data = CONST_M8[k_tx]
            bits_tx = bits_from_indices(k_tx)

            # p_ref lane: 고정 인덱스 (0)
            k_ref_const = 0
            s_ref = np.full_like(s_data, CONST_M8[k_ref_const])

            # 2) mid-ISI 채널 통과
            r_data = apply_channel_mid_isi(s_data, H_MID_ISI)
            r_ref = apply_channel_mid_isi(s_ref, H_MID_ISI)

            # 3) AWGN 추가 (각 lane 독립 노이즈)
            r_data = add_awgn(r_data, ebn0_db, BITS_PER_SYM, rng)
            r_ref = add_awgn(r_ref, ebn0_db, BITS_PER_SYM, rng)

            # 4) 공통 FFE 계수 학습 (data lane 기준 LS)
            w_ffe = ls_ffe_train(r_data, s_data, ffe_len, train_frac, ridge=1e-6)

            # 5) FFE 적용
            z_data_base = apply_ffe(r_data, w_ffe)
            z_ref_base = apply_ffe(r_ref, w_ffe)

            # 6) 공통 위상 노이즈 생성 및 적용
            phi = gen_phase_noise(theta_std_deg, n_sym, rng)
            rot_noise = np.exp(1j * phi)
            z_data = z_data_base * rot_noise
            z_ref = z_ref_base * rot_noise

            # 7) No PLL: phase correction 없이 slicing만 수행
            k_hat_nopll = slicer_8psk(z_data)
            bits_hat_nopll = bits_from_indices(k_hat_nopll)
            ber_nopll = np.mean(bits_hat_nopll != bits_tx)

            # 8) Data-DD only PLL
            bits_hat_dd = pll_detect_data_lane(
                z_ref=z_ref,
                z_data=z_data,
                mu_phase=mu_phase,
                alpha_ref=alpha_ref,
                use_pref=False,
                k_ref_const=k_ref_const,
            )
            ber_dd = np.mean(bits_hat_dd != bits_tx)

            # 9) Data + p_ref PLL
            bits_hat_pref = pll_detect_data_lane(
                z_ref=z_ref,
                z_data=z_data,
                mu_phase=mu_phase,
                alpha_ref=alpha_ref,
                use_pref=True,
                k_ref_const=k_ref_const,
            )
            ber_pref = np.mean(bits_hat_pref != bits_tx)

            results[theta_std_deg].append((ebn0_db, ber_nopll, ber_dd, ber_pref))

            print(f"{ebn0_db:9.1f} | {ber_nopll:12.6f} | {ber_dd:12.6f} | {ber_pref:12.6f}")

        print("---------------------------------------------------------------")
        print()


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CoPBit Q22a – M8 mid-ISI + FFE(LS) + common phase-noise + p_ref PLL v0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--n_sym", type=int, default=200000, help="심볼 수")
    p.add_argument(
        "--ebn0_list",
        type=str,
        default="12,14,16",
        help="콤마로 구분된 Eb/N0[dB] 리스트 (예: '12,14,16')",
    )
    p.add_argument(
        "--theta_std_list",
        type=str,
        default="0,1,3,5",
        help="콤마로 구분된 theta_std_deg 리스트 (예: '0,1,3,5')",
    )
    p.add_argument("--ffe_len", type=int, default=11, help="FFE 길이")
    p.add_argument("--train_frac", type=float, default=0.5, help="FFE 학습 구간 비율")
    p.add_argument("--mu_phase", type=float, default=0.05, help="PLL 스텝 크기")
    p.add_argument(
        "--alpha_ref",
        type=float,
        default=0.3,
        help="PLL에서 p_ref vs data 에러 비율 (0→ref-only, 1→data-only)",
    )
    p.add_argument("--seed", type=int, default=1, help="난수 시드")

    args = p.parse_args()

    # 문자열 리스트 파싱
    args.ebn0_list = [float(x) for x in args.ebn0_list.split(",") if x.strip()]
    args.theta_std_list = [float(x) for x in args.theta_std_list.split(",") if x.strip()]

    return args


if __name__ == "__main__":
    args = parse_args()
    simulate_q22a(
        n_sym=args.n_sym,
        ebn0_list=args.ebn0_list,
        theta_std_list=args.theta_std_list,
        ffe_len=args.ffe_len,
        train_frac=args.train_frac,
        mu_phase=args.mu_phase,
        alpha_ref=args.alpha_ref,
        seed=args.seed,
    )
