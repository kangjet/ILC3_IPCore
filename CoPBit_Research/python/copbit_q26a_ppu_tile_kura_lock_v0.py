#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q26a – PPU tile-level Kuramoto lock test (no channel / no AWGN) v0

목표:
- 여러 PPU 타일(각 타일 = 내부 PhaseLock_std + PPU 연산이 끝난 상태라고 가정)의
  "대표 위상"들 사이에 Kuramoto-style coupling을 걸었을 때,
  global phase lock 이 형성되는지 확인.
- lane-level 이 아니라 tile-level oscillator network 로 단순화.
- 결과를 CSV 맵(n_tiles, K, drift_std_deg, theta_std_deg → steady_sigma_deg, lock_step, lock_frac, lock_success)으로 저장.

기본 모델:
- 타일 수: n_tiles
- 각 타일의 위상: φ_i[n], i = 0..n_tiles-1
- 업데이트:
    φ_i[n+1] = φ_i[n]
              + ω_i                 (타일별 고정 drift, rad/심볼)
              + η_i[n]              (white phase jitter, rad)
              + (K / n_tiles) * Σ_j sin(φ_j[n] - φ_i[n])   (Kuramoto coupling)
- ω_i ~ N(0, drift_std_rad)
- η_i[n] ~ N(0, theta_std_rad)

락 판정:
- 각 스텝에서 circular mean μ[n]를 기준으로 한 RMS spread σ_φ[n] (deg) 계산
- burn-in 구간 (처음 burn_in_frac * n_sym)은 버리고 이후 평균 RMS spread → steady_sigma_deg
- lock_thr_deg 이하로 떨어진 시점부터 끝까지 계속 유지되면 "락 성공"으로 간주
- 그 시점 인덱스를 lock_step, 전체 심볼 수 대비 lock_frac = lock_step / n_sym 로 정의
"""

import argparse
import csv
import math
from typing import List, Tuple

import numpy as np


def str2float_list(s: str) -> List[float]:
    """문자열 "a,b,c" → [float(a), float(b), float(c)]"""
    return [float(x.strip()) for x in s.split(",") if x.strip() != ""]


def simulate_tile_kura_lock(
    n_sym: int,
    n_tiles: int,
    K: float,
    drift_std_deg: float,
    theta_std_deg: float,
    burn_in_frac: float,
    lock_thr_deg: float,
    seed: int,
) -> Tuple[float, int, float, int]:
    """
    타일 레벨 Kuramoto 네트워크 1회 시뮬레이션.

    반환:
        steady_sigma_deg : burn-in 이후 RMS phase spread (deg) 평균
        lock_step        : 락이 형성된 최초 step index (0-based, 없으면 -1)
        lock_frac        : lock_step / n_sym (없으면 -1.0)
        lock_success     : 1 (락 성공) / 0 (락 실패)
    """
    rng = np.random.default_rng(seed)

    # rad 단위로 변환
    drift_std_rad = math.radians(drift_std_deg)
    theta_std_rad = math.radians(theta_std_deg)

    # 타일별 고정 drift (rad/심볼), Gaussian
    if drift_std_rad > 0.0:
        drift_per_tile = rng.normal(loc=0.0, scale=drift_std_rad, size=n_tiles)
    else:
        drift_per_tile = np.zeros(n_tiles, dtype=np.float64)

    # 초기 위상: [0, 2π) 균등 분포
    phases = rng.uniform(low=0.0, high=2.0 * math.pi, size=n_tiles)

    # RMS phase spread 기록
    sigma_deg_hist = np.zeros(n_sym, dtype=np.float64)

    for n in range(n_sym):
        # Kuramoto coupling term
        # 전체 평균 위상 대신 full coupling: (K / n_tiles) * Σ_j sin(φ_j - φ_i)
        # matrix 방식으로 구현
        if K != 0.0:
            # Δ_ij = φ_j - φ_i
            # trick: outer subtraction
            diff = phases[None, :] - phases[:, None]  # shape: (n_tiles, n_tiles)
            coupling = (K / float(n_tiles)) * np.sum(np.sin(diff), axis=1)
        else:
            coupling = 0.0

        # 랜덤 phase jitter
        if theta_std_rad > 0.0:
            noise = rng.normal(loc=0.0, scale=theta_std_rad, size=n_tiles)
        else:
            noise = 0.0

        # 업데이트
        phases = phases + drift_per_tile + coupling + noise
        # [-π, π) 또는 [0, 2π) 로 정규화 (여기선 [-π, π) 기준)
        phases = np.angle(np.exp(1j * phases))

        # circular mean
        mean_vec = np.mean(np.exp(1j * phases))
        mean_angle = np.angle(mean_vec)

        # 평균 기준으로 랩핑된 차이
        delta = np.angle(np.exp(1j * (phases - mean_angle)))
        sigma_rad = float(np.sqrt(np.mean(delta ** 2)))
        sigma_deg = math.degrees(sigma_rad)
        sigma_deg_hist[n] = sigma_deg

    # steady 구간 (burn-in 이후)
    burn_idx = int(burn_in_frac * n_sym)
    if burn_idx < 0:
        burn_idx = 0
    if burn_idx >= n_sym:
        burn_idx = n_sym - 1

    steady_sigma_deg = float(np.mean(sigma_deg_hist[burn_idx:]))

    # 락 판단: lock_thr_deg 이하로 떨어진 후 끝까지 유지되는 최초 스텝
    thr = lock_thr_deg
    mask = sigma_deg_hist <= thr

    # suffix AND
    N = n_sym
    suffix_ok = np.zeros(N, dtype=bool)
    acc = True
    for i in range(N - 1, -1, -1):
        acc = acc and bool(mask[i])
        suffix_ok[i] = acc

    if np.any(suffix_ok):
        lock_step = int(np.argmax(suffix_ok))
        lock_frac = float(lock_step) / float(n_sym)
        lock_success = 1
    else:
        lock_step = -1
        lock_frac = -1.0
        lock_success = 0

    return steady_sigma_deg, lock_step, lock_frac, lock_success


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q26a – PPU tile-level Kuramoto lock test (no channel / no AWGN) v0"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=50000,
        help="시뮬레이션 심볼 수 (기본: 50000)",
    )
    parser.add_argument(
        "--n_tiles",
        type=int,
        default=16,
        help="타일 개수 (기본: 16)",
    )
    parser.add_argument(
        "--kappa_list",
        type=str,
        default="0.0,0.05,0.1,0.2,0.3",
        help='Kuramoto coupling 강도 리스트 (예: "0.0,0.05,0.1,0.2,0.3")',
    )
    parser.add_argument(
        "--drift_std_list_deg",
        type=str,
        default="0.01,0.05,0.1",
        help='타일별 고정 drift 표준편차 리스트[deg] (예: "0.01,0.05,0.1")',
    )
    parser.add_argument(
        "--theta_std_list_deg",
        type=str,
        default="0.1,0.3,0.5",
        help='타일별 랜덤 phase jitter 표준편차 리스트[deg] (예: "0.1,0.3,0.5")',
    )
    parser.add_argument(
        "--burn_in_frac",
        type=float,
        default=0.5,
        help="steady sigma 계산 시 버릴 초기 구간 비율 (기본: 0.5 = 앞 50%% 버림)",
    )
    parser.add_argument(
        "--lock_thr_deg",
        type=float,
        default=1.0,
        help="global lock 판정용 RMS phase spread 임계값[deg] (기본: 1.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="랜덤 시드 (기본: 1)",
    )
    parser.add_argument(
        "--csv_out",
        type=str,
        default=None,
        help="결과를 저장할 CSV 경로 (기본: None, 파일 저장 안함)",
    )

    args = parser.parse_args()

    n_sym = args.n_sym
    n_tiles = args.n_tiles
    kappa_list = str2float_list(args.kappa_list)
    drift_list = str2float_list(args.drift_std_list_deg)
    theta_list = str2float_list(args.theta_std_list_deg)
    burn_in_frac = args.burn_in_frac
    lock_thr_deg = args.lock_thr_deg
    seed = args.seed
    csv_out = args.csv_out

    print("=== CoPBit Q26a – PPU tile-level Kuramoto lock test (no channel / no AWGN) v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] n_tiles        = {n_tiles}")
    print(f"[Param] kappa_list     = {kappa_list}")
    print(f"[Param] drift_std_deg  = {drift_list}")
    print(f"[Param] theta_std_deg  = {theta_list}")
    print(f"[Param] burn_in_frac   = {burn_in_frac}")
    print(f"[Param] lock_thr_deg   = {lock_thr_deg}")
    print(f"[Param] seed           = {seed}")
    print("")

    # 결과 저장용 리스트
    rows = []
    header = [
        "n_tiles",
        "K",
        "drift_std_deg",
        "theta_std_deg",
        "steady_sigma_deg",
        "lock_step",
        "lock_frac",
        "lock_success",
    ]

    print("==============================================================")
    print("  n_tiles |    K   | drift_std | theta_std | steady_sigma | lock_frac | success")
    print("--------------------------------------------------------------")

    # 파라미터 조합 sweep
    for K in kappa_list:
        for drift_std_deg in drift_list:
            for theta_std_deg in theta_list:
                steady_sigma_deg, lock_step, lock_frac, lock_success = simulate_tile_kura_lock(
                    n_sym=n_sym,
                    n_tiles=n_tiles,
                    K=K,
                    drift_std_deg=drift_std_deg,
                    theta_std_deg=theta_std_deg,
                    burn_in_frac=burn_in_frac,
                    lock_thr_deg=lock_thr_deg,
                    seed=seed,
                )

                rows.append(
                    [
                        n_tiles,
                        K,
                        drift_std_deg,
                        theta_std_deg,
                        steady_sigma_deg,
                        lock_step,
                        lock_frac,
                        lock_success,
                    ]
                )

                print(
                    f"{n_tiles:8d} | "
                    f"{K:5.3f} | "
                    f"{drift_std_deg:9.3f} | "
                    f"{theta_std_deg:9.3f} | "
                    f"{steady_sigma_deg:12.3f} | "
                    f"{lock_frac:9.3f} | "
                    f"{lock_success:7d}"
                )

    print("--------------------------------------------------------------")

    # CSV 저장
    if csv_out is not None and csv_out != "":
        with open(csv_out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        print(f"[Info ] CSV 결과 저장 완료: {csv_out}")


if __name__ == "__main__":
    main()