#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q25a – PPU 3D-MAC truthcheck (no channel / no phase / no noise) v0

- 목적:
  - Q24b에서 검증한 3D-ADD ((a+b) mod M)를 여러 번 체인으로 연결했을 때
    (a0 + a1 + ... + a_{K-1}) mod M 형태의 3D-MAC이
    논리적 ground truth와 100% 일치하는지 확인.
  - 채널/위상/노이즈/PLL/FFE/DFE 전부 OFF.
  - PPU 코어의 순수 디지털 연산 primitive 검증.
"""

import argparse
import numpy as np
from typing import Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CoPBit Q25a – PPU 3D-MAC truthcheck (no channel / no phase / no noise) v0"
    )
    p.add_argument(
        "--mode",
        type=str,
        default="random",
        choices=["full", "random"],
        help="full: 모든 입력 조합 전수 검사 (M^K), random: 랜덤 샘플 기반 검사",
    )
    p.add_argument(
        "--M",
        type=int,
        default=8,
        help="modulo M (기본 8 = M8)",
    )
    p.add_argument(
        "--mac_len",
        type=int,
        default=4,
        help="MAC 길이 K (a0 + ... + a_{K-1})",
    )
    p.add_argument(
        "--n_samples",
        type=int,
        default=100000,
        help="random 모드에서 사용할 샘플 수",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=1,
        help="랜덤 시드",
    )
    p.add_argument(
        "--show_confmat",
        action="store_true",
        help="truth_idx vs impl_idx confusion matrix 출력",
    )
    return p.parse_args()


# ===== 3D-ADD / 3D-MAC 정의 =====

def add3d_truth(a_idx: int, b_idx: int, M: int) -> int:
    """논리 ground truth: (a + b) mod M"""
    return (a_idx + b_idx) % M


def add3d_impl(a_idx: int, b_idx: int, M: int) -> int:
    """구현: 현재는 truth와 동일한 디지털 정의 (옵션 A)"""
    return (a_idx + b_idx) % M


def mac3d_truth(a_vec: np.ndarray, M: int) -> int:
    """3D-MAC truth: (a0 + a1 + ... + a_{K-1}) mod M"""
    return int(np.sum(a_vec) % M)


def mac3d_impl(a_vec: np.ndarray, M: int) -> int:
    """
    3D-MAC 구현:
    - 3D-ADD primitive를 체인 형태로 반복 적용
    - (((a0 + a1) mod M) + a2) mod M ... 형태
    """
    acc = int(a_vec[0])
    for k in range(1, len(a_vec)):
        acc = add3d_impl(acc, int(a_vec[k]), M)
    return acc % M


# ===== 평가 루틴 =====

def eval_full(M: int, mac_len: int) -> Tuple[float, np.ndarray]:
    """
    모든 입력 조합 전수 검사 (mode = full)
    - 입력: (a0, ..., a_{K-1}) ∈ {0..M-1}^K (총 M^K 조합)
    - 출력: (op_error, confmat[M,M])
    """
    # M^K 조합이 너무 크지 않은지 체크 (안전장치)
    total_comb = M ** mac_len
    if total_comb > 1_000_000:
        raise ValueError(
            f"full 모드 조합 수가 너무 큼: M^K = {M}^{mac_len} = {total_comb} > 1e6"
        )

    # 모든 조합 생성: (total_comb, mac_len)
    grid = np.indices((M,) * mac_len).reshape(mac_len, -1).T  # shape: (M^K, K)

    confmat = np.zeros((M, M), dtype=np.int64)
    n_err = 0

    for vec in grid:
        y_t = mac3d_truth(vec, M)
        y_i = mac3d_impl(vec, M)
        confmat[y_t, y_i] += 1
        if y_t != y_i:
            n_err += 1

    op_error = n_err / float(grid.shape[0])
    return op_error, confmat


def eval_random(M: int, mac_len: int, n_samples: int, seed: int) -> Tuple[float, np.ndarray]:
    """
    랜덤 입력 기반 검사 (mode = random)
    - 입력: n_samples 개의 (mac_len,) 벡터를 랜덤 생성
    - 출력: (op_error, confmat[M,M])
    """
    rng = np.random.default_rng(seed)
    a = rng.integers(low=0, high=M, size=(n_samples, mac_len), endpoint=False)

    confmat = np.zeros((M, M), dtype=np.int64)
    n_err = 0

    for i in range(n_samples):
        vec = a[i]
        y_t = mac3d_truth(vec, M)
        y_i = mac3d_impl(vec, M)
        confmat[y_t, y_i] += 1
        if y_t != y_i:
            n_err += 1

    op_error = n_err / float(n_samples)
    return op_error, confmat


def print_confmat(confmat: np.ndarray) -> None:
    M = confmat.shape[0]
    print("\n[Confusion Matrix] rows = truth_idx(0..M-1), cols = impl_idx(0..M-1)")
    for r in range(M):
        row_str = " ".join(f"{confmat[r, c]:6d}" for c in range(M))
        print(f"{r} | {row_str}")


def main():
    args = parse_args()

    print("=== CoPBit Q25a – PPU 3D-MAC truthcheck (no channel / no phase / no noise) v0 ===")
    print(f"[Param] mode      = {args.mode}")
    print(f"[Param] M         = {args.M}")
    print(f"[Param] mac_len   = {args.mac_len}")
    if args.mode == "random":
        print(f"[Param] n_samples = {args.n_samples}")
        print(f"[Param] seed      = {args.seed}")
    print()

    if args.mode == "full":
        op_error, confmat = eval_full(args.M, args.mac_len)
    else:
        op_error, confmat = eval_random(args.M, args.mac_len, args.n_samples, args.seed)

    print("==============================================================")
    print("  Metric             |  Value")
    print("--------------------------------------------------------------")
    print(f"  op_error_3d_mac    |  {op_error:.6f}")
    print("--------------------------------------------------------------")

    if args.show_confmat:
        print_confmat(confmat)


if __name__ == "__main__":
    main()