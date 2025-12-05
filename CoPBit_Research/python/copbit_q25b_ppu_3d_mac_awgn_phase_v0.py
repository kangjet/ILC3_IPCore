#!/usr/bin/env python3
"""CoPBit Q25b – 3D-MAC PPU tile under AWGN + PhaseLock_std (M8)

역할
-----
- Q23a : 1024-lane PPU 타일에서 위상 잡는 기본 BER 맵 (심볼 기준)
- Q24a : 3D-ADD 연산 에러율 (AWGN + PhaseLock_std)
- Q25a : 3D-MAC 디지털 truthcheck (채널/위상/노이즈 없음)
- Q25b : 3D-MAC 연산 에러율 맵 (AWGN + 위상 노이즈 + PhaseLock_std)

여기서는:
- M8 (8-PSK) 기반 CoPBit 3D 값들을 사용
- 1024-lane PPU 타일에서 일부 lane은 p_ref, 나머지는 data lane
- 각 타임스텝마다 data lane들 중 mac_len개를 뽑아서 3D-MAC 수행
  truth  : (원래 M8 인덱스들의 합 mod M)
  impl   : (복조된 인덱스들의 합 mod M)
- op_error_3d_mac = truth != impl 비율

출력
-----
- 터미널: θ_std 별로 Eb/N0 vs op_error_3d_mac 테이블 출력
- CSV  : --csv_out 경로에
    EbN0_dB,theta_std_deg,mac_len,op_error_3d_mac
  형식으로 저장 (append, 파일 없으면 헤더 포함 생성)
"""

import argparse
import math
import os
from typing import List, Tuple, Optional

import numpy as np


# ---------------------------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------------------------

def parse_float_list(s: str) -> List[float]:
    if not s:
        return []
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def db2lin(db: float) -> float:
    return 10.0 ** (db / 10.0)


def mpsk_constellation(M: int) -> np.ndarray:
    """정규화된 M-PSK (M8) 컨스텔레이션: k -> exp(j*2πk/M)."""
    k = np.arange(M, dtype=float)
    return np.exp(1j * 2.0 * np.pi * k / M)


def pam3_symbol_energy() -> float:
    """(미사용) 참고용: PAM3 점들의 평균 에너지."""
    levels = np.array([-1.0, 0.0, 1.0])
    return float(np.mean(levels**2))


# ---------------------------------------------------------------------------
# 3D-ADD / 3D-MAC 연산 정의 (디지털 영역)
# ---------------------------------------------------------------------------

def add3d_truth(a: int, b: int, M: int) -> int:
    """3D-ADD 이상적 정의: 단순 모듈로 덧셈.

    a, b : [0, M-1] 정수 인덱스
    반환 : (a + b) mod M
    """
    return (a + b) % M


def mac3d_truth(vec: np.ndarray, M: int) -> int:
    """3D-MAC 이상적 정의: vec 원소들의 합을 모듈로 연산.

    vec : shape (K,), 값은 [0, M-1] 정수 인덱스
    반환 : (sum(vec) mod M)
    """
    return int(np.sum(vec) % M)


# ---------------------------------------------------------------------------
# PhaseLock_std: 다중 레인 공통 위상 PLL (p_ref + data 혼합)
# ---------------------------------------------------------------------------

def phase_lock_step(
    y: np.ndarray,
    constel: np.ndarray,
    phi_hat: float,
    pref_mask: np.ndarray,
    mu_phase: float,
    alpha_ref: float,
) -> Tuple[np.ndarray, float]:
    """한 타임스텝에 대해 공통 위상 추정 및 심볼 결정 수행.

    파라미터
    ---------
    y : (n_lanes,) 복소수 수신 심볼 (현재 샘플, 공통 φ 포함)
    constel : (M,) M-PSK 컨스텔레이션
    phi_hat : 직전까지의 공통 위상 추정값 (라디안)
    pref_mask : (n_lanes,) bool, True= p_ref lane
    mu_phase : 위상 PLL 스텝 크기
    alpha_ref : [0..1], 0→참조만, 1→데이터만 사용

    반환
    -----
    dec_idx : (n_lanes,) 결정된 M 인덱스
    phi_hat_new : 업데이트된 위상 추정값
    """

    # 현재 추정 위상 제거
    rot = np.exp(-1j * phi_hat)
    y_rot = y * rot

    # M-PSK 최근접 결정 (브루트포스, M=8이라 가볍게 처리)
    # constel: (M,), y_rot: (L,) → diff: (M, L)
    diff = y_rot[None, :] - constel[:, None]
    d2 = (diff.real ** 2) + (diff.imag ** 2)
    dec_idx = np.argmin(d2, axis=0)  # (n_lanes,)

    # 위상 에러 추정: y_rot * conj(dec_sym) → 각도
    dec_sym = constel[dec_idx]
    z = y_rot * np.conj(dec_sym)
    phase_err = np.angle(z)  # (n_lanes,)

    # p_ref / data 분리 후 평균
    if np.any(pref_mask):
        err_ref = float(np.mean(phase_err[pref_mask]))
    else:
        err_ref = 0.0

    if np.any(~pref_mask):
        err_data = float(np.mean(phase_err[~pref_mask]))
    else:
        err_data = 0.0

    err_total = (1.0 - alpha_ref) * err_ref + alpha_ref * err_data
    phi_hat_new = phi_hat + mu_phase * err_total

    return dec_idx, phi_hat_new


# ---------------------------------------------------------------------------
# 메인 시뮬레이션 루프
# ---------------------------------------------------------------------------

def run_q25b(
    n_sym: int,
    ebn0_list: List[float],
    theta_std_list: List[float],
    n_lanes: int,
    mac_len: int,
    mu_phase: float,
    alpha_ref: float,
    pref_stride: int,
    seed: int,
    csv_out: Optional[str],
) -> None:
    rng = np.random.default_rng(seed)

    M = 8
    constel = mpsk_constellation(M)

    lanes = np.arange(n_lanes)
    pref_mask = (lanes % pref_stride == 0)  # 규칙적으로 p_ref 분포
    n_pref = int(np.sum(pref_mask))
    n_data = n_lanes - n_pref

    if n_data <= 0:
        raise ValueError("pref_stride가 너무 작아서 data lane이 없습니다.")

    data_lanes = lanes[~pref_mask]

    print("=== CoPBit Q25b – 1024-lane PPU 3D-MAC (AWGN) + PhaseLock_std v0 ===")
    print(f"[Param] n_sym        = {n_sym}")
    print(f"[Param] Eb/N0_list   = {ebn0_list}")
    print(f"[Param] theta_std(deg)= {theta_std_list}")
    print(f"[Param] n_lanes      = {n_lanes}  (p_ref lanes = {n_pref}, data lanes = {n_data})")
    print(f"[Param] mac_len      = {mac_len}")
    print(f"[Param] mu_phase     = {mu_phase}")
    print(f"[Param] alpha_ref    = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] pref_stride  = {pref_stride}\n")

    # CSV 헤더 준비
    if csv_out is not None:
        need_header = not os.path.exists(csv_out)
        with open(csv_out, "a", encoding="utf-8") as f:
            if need_header:
                f.write("EbN0_dB,theta_std_deg,mac_len,op_error_3d_mac\n")

    # θ_std 루프
    for theta_deg in theta_std_list:
        sigma_rad = theta_deg * math.pi / 180.0
        print(f"=== Q25b (theta_std_deg = {theta_deg:.3f}) ===")
        print("===============================================================")
        print(" Eb/N0_dB |  op_error_3d_mac")
        print("---------------------------------------------------------------")

        for ebn0_db in ebn0_list:
            # ------------------------------------------------------------------
            # 1) 데이터 생성 (M8 인덱스) + p_ref 도핑
            # ------------------------------------------------------------------
            # 전체 타일에 대해 랜덤 데이터 생성
            sym_idx = rng.integers(low=0, high=M, size=(n_sym, n_lanes), dtype=np.int16)

            # p_ref lane은 고정 인덱스(예: 0)로 설정
            sym_idx[:, pref_mask] = 0

            # ------------------------------------------------------------------
            # 2) 채널: M-PSK 매핑 + 공통 위상 노이즈 + AWGN
            # ------------------------------------------------------------------
            s = constel[sym_idx]  # (n_sym, n_lanes)

            # 공통 위상 노이즈 (심볼마다 하나, 모든 lane에 공통)
            if sigma_rad > 0.0:
                phi_noise = rng.normal(loc=0.0, scale=sigma_rad, size=n_sym)
            else:
                phi_noise = np.zeros(n_sym, dtype=float)
            phasor = np.exp(1j * phi_noise)[:, None]  # (n_sym, 1)

            # AWGN 노이즈 (Es=1 기준, Eb/N0를 Es/N0와 동일하게 간주)
            snr_lin = db2lin(ebn0_db)
            noise_sigma = 1.0 / math.sqrt(2.0 * snr_lin)
            noise = noise_sigma * (
                rng.standard_normal(size=(n_sym, n_lanes))
                + 1j * rng.standard_normal(size=(n_sym, n_lanes))
            )

            r = s * phasor + noise

            # ------------------------------------------------------------------
            # 3) MAC 연산에 사용할 lane 인덱스 미리 샘플링 (data lane만 사용)
            # ------------------------------------------------------------------
            # data_lanes 중에서 mac_len개를 (중복 허용) 뽑는 인덱스 테이블
            data_idx_pool_size = len(data_lanes)
            mac_sel_idx = rng.integers(
                low=0,
                high=data_idx_pool_size,
                size=(n_sym, mac_len),
                dtype=np.int32,
            )  # 각 row: data_lanes 인덱스

            # ------------------------------------------------------------------
            # 4) 시퀀스 순회하며 PhaseLock_std + 3D-MAC 에러 카운트
            # ------------------------------------------------------------------
            phi_hat = 0.0
            op_total = 0
            op_err = 0

            for n in range(n_sym):
                y_n = r[n, :]  # (n_lanes,)

                # PhaseLock_std 1-step
                dec_idx_n, phi_hat = phase_lock_step(
                    y=y_n,
                    constel=constel,
                    phi_hat=phi_hat,
                    pref_mask=pref_mask,
                    mu_phase=mu_phase,
                    alpha_ref=alpha_ref,
                )

                # 3D-MAC 한 번 수행 (같은 타임스텝에서 여러 lane 사용)
                sel_data_idx = data_lanes[mac_sel_idx[n]]  # (mac_len,)

                truth_vec = sym_idx[n, sel_data_idx]
                impl_vec = dec_idx_n[sel_data_idx]

                truth_mac = mac3d_truth(truth_vec, M)
                impl_mac = mac3d_truth(impl_vec, M)

                op_total += 1
                if truth_mac != impl_mac:
                    op_err += 1

            op_error = op_err / op_total if op_total > 0 else 0.0

            print(f"     {ebn0_db:4.1f} |     {op_error:0.6f}")

            # CSV 저장
            if csv_out is not None:
                with open(csv_out, "a", encoding="utf-8") as f:
                    f.write(
                        f"{ebn0_db:.2f},{theta_deg:.3f},{mac_len:d},{op_error:.6e}\n"
                    )

        print("---------------------------------------------------------------\n")


# ---------------------------------------------------------------------------
# 엔트리 포인트
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "CoPBit Q25b – 1024-lane PPU 3D-MAC (M8) under AWGN + PhaseLock_std"
        )
    )

    parser.add_argument("--n_sym", type=int, default=50000, help="심볼 수 (time steps)")
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="12,14,16",
        help="콤마로 구분된 Eb/N0(dB) 리스트, 예: '12,14,16'",
    )
    parser.add_argument(
        "--theta_std_list",
        type=str,
        default="0.0,0.5,1.0,2.0",
        help="콤마로 구분된 θ_std(deg) 리스트, 예: '0.0,0.5,1.0,2.0'",
    )
    parser.add_argument(
        "--n_lanes", type=int, default=1024, help="PPU 타일 내 lane 수"
    )
    parser.add_argument(
        "--mac_len", type=int, default=4, help="3D-MAC 길이 (입력 벡터 길이)"
    )
    parser.add_argument(
        "--mu_phase", type=float, default=0.05, help="PhaseLock_std 스텝 크기"
    )
    parser.add_argument(
        "--alpha_ref",
        type=float,
        default=0.3,
        help="위상 에러 혼합 비율 (0→ref only, 1→data only)",
    )
    parser.add_argument(
        "--pref_stride",
        type=int,
        default=16,
        help="몇 개 lane마다 하나씩 p_ref lane으로 둘지 (lane index % stride == 0)",
    )
    parser.add_argument("--seed", type=int, default=1, help="난수 seed")
    parser.add_argument(
        "--csv_out",
        type=str,
        default=None,
        help="결과를 저장할 CSV 경로 (생략 시 파일 저장 안 함)",
    )

    args = parser.parse_args()

    ebn0_list = parse_float_list(args.ebn0_list)
    theta_std_list = parse_float_list(args.theta_std_list)

    if not ebn0_list:
        raise ValueError("Eb/N0 리스트가 비어 있습니다. --ebn0_list 를 확인하세요.")
    if not theta_std_list:
        raise ValueError("theta_std_list 가 비어 있습니다.")

    run_q25b(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        theta_std_list=theta_std_list,
        n_lanes=args.n_lanes,
        mac_len=args.mac_len,
        mu_phase=args.mu_phase,
        alpha_ref=args.alpha_ref,
        pref_stride=args.pref_stride,
        seed=args.seed,
        csv_out=args.csv_out,
    )


if __name__ == "__main__":
    main()
