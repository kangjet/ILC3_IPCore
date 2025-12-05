#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q24b – PPU 3D-ADD truthcheck (no channel / no phase / no noise) v0

목적
------
- Q24a에서 설계한 "3D ADD" 연산이 우리가 의도한 규칙과 실제로 일치하는지,
  채널/위상/노이즈를 전부 끄고 **순수 인덱스 레벨**에서 검증한다.
- 여기서는 기본값으로 "이론적 규칙 = (a + b) mod M" 으로 두었고,
  실제 구현(add3d_impl)은 처음에는 truth와 동일하게 둔다.
- 이후 Q24a에서 사용한 3D 매핑/연산 코드를 여기에 복붙해서
  add3d_impl 쪽을 교체하면, op_error_3d_add 값을 통해
  설계 vs 구현 불일치 여부를 바로 확인할 수 있다.

사용 예시
---------
# 전체 truth table(8x8) 전수 검사
python copbit_q24b_ppu_3d_add_truthcheck_v0.py --mode full

# 랜덤 샘플 기반 검사
python copbit_q24b_ppu_3d_add_truthcheck_v0.py --mode random --n_samples 100000 --seed 1

"""

import argparse
import numpy as np

# M8 기준 (index: 0..7)
M = 8


# -------------------------------------------------------------
# 1. 인덱스 <-> 비트 / 3D 표현 매핑 (기본 템플릿)
# -------------------------------------------------------------

def idx_to_bits(k: int, n_bits: int = 3):
    """정수 인덱스를 n_bits 비트 배열(MSB-first)로 변환."""
    bits = [(k >> i) & 1 for i in reversed(range(n_bits))]
    return np.array(bits, dtype=int)


def bits_to_idx(bits: np.ndarray) -> int:
    """비트 배열(MSB-first)을 정수 인덱스로 변환."""
    out = 0
    for b in bits:
        out = (out << 1) | int(b & 1)
    return int(out)


def idx_to_3d(k: int) -> np.ndarray:
    """
    인덱스를 3D 벡터로 매핑.
    - 여기서는 단순히 (b2, b1, b0)를 3D 좌표로 해석하는 기본 템플릿.
    - Q24a에서 사용한 실제 3D 매핑 규칙이 있다면, 이 함수를 그 규칙으로 교체하면 된다.
    """
    bits = idx_to_bits(k, n_bits=3)  # [b2, b1, b0]
    # 예: {0,1} -> {-1,+1} 로 매핑해서 진짜 3D 벡터로 만들 수도 있음.
    # 여기서는 일단 0/1 그대로 사용.
    return bits.astype(float)


def vec3d_to_idx(v: np.ndarray) -> int:
    """
    3D 벡터를 인덱스로 역매핑.
    - 실제 PPU 설계에서는 벡터를 threshold / 양자화해서 다시 3비트로 만드는 규칙이 필요하다.
    - 여기서는 단순히 0.5 기준으로 0/1 양자화 후 bits_to_idx 로 변환.
    - Q24a에서의 실제 규칙이 있다면, 이 부분을 그 규칙으로 교체.
    """
    bits = (v >= 0.5).astype(int)
    bits = bits[:3]  # safety
    return bits_to_idx(bits)


# -------------------------------------------------------------
# 2. "이론적" 3D ADD 규칙 (truth) 정의
# -------------------------------------------------------------

def add3d_truth(a_idx: int, b_idx: int) -> int:
    """
    우리가 '정답'이라고 생각하는 3D ADD 규칙.
    - 기본값: 단순히 인덱스 공간에서 (a + b) mod M.
    - 필요하다면 여기서 다른 규칙(예: 벡터합 후 최근접 M8 포인트)으로 정의 가능.
    """
    return (a_idx + b_idx) % M


# -------------------------------------------------------------
# 3. "구현" 3D ADD (PPU 파이프라인과 동일하게 진짜 구현)
# -------------------------------------------------------------

def add3d_impl(a_idx: int, b_idx: int) -> int:
    """
    옵션 A: PPU 3D-ADD를 '디지털 진리' (a + b) mod M 과 완전히 동일하게 맞춘 버전.
    - 여기서는 채널 / 위상 / 노이즈가 없는 이상적인 PPU 코어를 가정한다.
    - Q24a, Q25... 에서 채널이나 위상을 올려서 BER을 보는 것은
      이 '이상적인 진리'를 기준으로 성능을 측정하는 구조가 된다.
    """
    return (a_idx + b_idx) % M


# -------------------------------------------------------------
# 4. Truth vs Impl 비교 루틴
# -------------------------------------------------------------

def check_full_table():
    """
    전수 검사: 모든 (a,b) ∈ {0..M-1}^2 에 대해 truth vs impl 비교.
    """
    total = 0
    diff = 0
    confmat = np.zeros((M, M), dtype=int)  # rows: truth, cols: impl

    for a in range(M):
        for b in range(M):
            total += 1
            y_true = add3d_truth(a, b)
            y_hat = add3d_impl(a, b)

            if y_true != y_hat:
                diff += 1
            confmat[y_true, y_hat] += 1

    op_err = diff / total
    return op_err, confmat


def check_random(n_samples: int, seed: int = 1):
    """
    랜덤 샘플 기반 truth vs impl 비교.
    """
    rng = np.random.default_rng(seed)
    a = rng.integers(0, M, size=n_samples, endpoint=False)
    b = rng.integers(0, M, size=n_samples, endpoint=False)

    total = n_samples
    diff = 0
    confmat = np.zeros((M, M), dtype=int)

    for ai, bi in zip(a, b):
        y_true = add3d_truth(int(ai), int(bi))
        y_hat = add3d_impl(int(ai), int(bi))
        if y_true != y_hat:
            diff += 1
        confmat[y_true, y_hat] += 1

    op_err = diff / total
    return op_err, confmat


# -------------------------------------------------------------
# 5. CLI 및 메인
# -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q24b – PPU 3D-ADD truthcheck (no channel / no phase / no noise) v0"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "random"],
        help="검증 모드: full(8x8 전수) 또는 random(랜덤 샘플)"
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=100000,
        help="mode=random 일 때 사용할 샘플 수"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="random 모드에서 사용할 seed"
    )
    parser.add_argument(
        "--show_confmat",
        action="store_true",
        help="truth vs impl confusion matrix 출력 여부"
    )

    args = parser.parse_args()

    print("=== CoPBit Q24b – PPU 3D-ADD truthcheck (no channel / no phase / no noise) v0 ===")
    print(f"[Param] mode      = {args.mode}")
    print(f"[Param] n_samples = {args.n_samples}")
    print(f"[Param] seed      = {args.seed}")
    print(f"[Param] M         = {M}")
    print()

    if args.mode == "full":
        op_err, confmat = check_full_table()
    else:
        op_err, confmat = check_random(args.n_samples, args.seed)

    print("==============================================================")
    print("  Metric            |  Value")
    print("--------------------------------------------------------------")
    print(f"  op_error_3d_add   |  {op_err:.6f}")
    print("--------------------------------------------------------------")

    if args.show_confmat:
        print("\n[Confusion Matrix] rows = truth_idx(0..M-1), cols = impl_idx(0..M-1)")
        for i in range(M):
            row = " ".join(f"{confmat[i, j]:5d}" for j in range(M))
            print(f"{i} | {row}")


if __name__ == "__main__":
    main()