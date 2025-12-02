#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q3-1 – 4bit 비트 매핑 규칙 데모 v0.1

- 16포인트 (Q1 위성)에 대해
  상위 2비트 = 클러스터 index (c)
  하위 2비트 = 클러스터 내부 index (p)
  매핑이 잘 되는지 확인하는 스크립트.
"""

import math
import numpy as np


def make_constellation_q1(phi_step=math.pi / 16.0):
    """
    Q1에서 사용한 16포인트 위성 정의를 그대로 재사용.
    (theta0, cluster_idx, phi_c) 반환.
    """
    N = 16
    theta0 = np.zeros(N, dtype=float)
    cluster_idx = np.zeros(N, dtype=int)

    for k in range(N):
        theta0[k] = 2.0 * math.pi * k / N
        c = k // 4  # 0..3
        cluster_idx[k] = c

    num_clusters = 4
    phi_c = np.array([c * phi_step for c in range(num_clusters)], dtype=float)
    return theta0, cluster_idx, phi_c


def encode_bits(c, p):
    """
    상위 2비트 = c (0..3), 하위 2비트 = p (0..3)
    → 4bit 값 B(0..15)로 인코딩.
    """
    assert 0 <= c < 4
    assert 0 <= p < 4
    return (c << 2) | p


def decode_bits(B):
    """
    4bit 값 B(0..15)를 (c,p)로 역변환.
    c = 상위 2비트, p = 하위 2비트.
    """
    assert 0 <= B < 16
    c = (B >> 2) & 0b11
    p = B & 0b11
    return c, p


def main():
    theta0, cluster_idx, phi_c = make_constellation_q1()

    print("=== CoPBit Q3-1 Bit Mapping Demo v0.1 ===\n")
    print("k  bits  c  p   theta[deg]")
    print("-------------------------------------")

    for k in range(16):
        # k 자체를 4bit 값으로 사용
        B = k
        c_enc, p_enc = decode_bits(B)
        # 이론상 c_enc = k//4, p_enc = k%4 여야 함
        c_true = cluster_idx[k]
        p_true = k % 4
        theta_deg = theta0[k] * 180.0 / math.pi

        print(f"{k:2d}  {B:04b}  {c_enc:1d}  {p_enc:1d}   {theta_deg:7.2f}")

        if c_enc != c_true or p_enc != p_true:
            print("  [WARN] mapping mismatch at k =", k)

    print("\n[Check] (c,p) -> B -> (c,p) 왕복 테스트")
    ok = True
    for c in range(4):
        for p in range(4):
            B = encode_bits(c, p)
            c2, p2 = decode_bits(B)
            if c != c2 or p != p2:
                ok = False
                print(f"  FAIL: c={c}, p={p} -> B={B:04b} -> (c,p)=({c2},{p2})")
    if ok:
        print("  OK: 모든 (c,p)쌍이 정확히 왕복 인코딩/디코딩 됩니다.")


if __name__ == "__main__":
    main()