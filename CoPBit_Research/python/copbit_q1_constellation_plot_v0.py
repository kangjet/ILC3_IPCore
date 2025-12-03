#!/usr/bin/env python3
"""
CoPBit Q1 – 1-lane 3D Constellation v0.1

- 16포인트(4bit) 위성 구조를 (r, theta, phi) -> (x, y, z)로 변환해서 플롯
- Q1 md에 정의한 매핑 규칙을 그대로 코드로 옮긴 버전
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  # 3D 등록용


def bits4(k: int) -> str:
    """0 <= k < 16 -> '0000' ~ '1111'"""
    return format(k, "04b")


def main():
    # ---- 파라미터 (Q2에서 튜닝 예정) ----
    r = 1.0
    phi_step = np.pi / 16.0  # 예시: 클러스터 간 보조각

    ks = np.arange(16)

    xs, ys, zs = [], [], []
    labels = []
    meta = []

    for k in ks:
        b = bits4(k)
        c = k // 4          # 클러스터 인덱스
        i = k % 4           # 클러스터 내 인덱스
        theta = 2.0 * np.pi * k / 16.0
        phi = c * phi_step

        # 구면좌표 -> 직교좌표 변환
        # r: 반지름, theta: xy 평면 위상, phi: z축에 대한 보조각
        x = r * np.cos(theta) * np.cos(phi)
        y = r * np.sin(theta) * np.cos(phi)
        z = r * np.sin(phi)

        xs.append(x)
        ys.append(y)
        zs.append(z)
        labels.append(b)
        meta.append((k, b, c, i, theta, phi))

    # ---- 콘솔에도 매핑 정보 한 번 출력 ----
    print("=== CoPBit Q1 Constellation (v0.1) ===")
    print("k  bits  c  i   theta[deg]   phi[deg]")
    for k, b, c, i, theta, phi in meta:
        print(
            f"{k:2d}  {b}  {c}  {i}   "
            f"{np.degrees(theta):8.2f}   {np.degrees(phi):8.2f}"
        )

    # ---- 3D 플롯 ----
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    ax.scatter(xs, ys, zs, s=40)

    # 각 포인트에 bit 라벨 표시
    for x, y, z, lab in zip(xs, ys, zs, labels):
        ax.text(x, y, z, lab, fontsize=8)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("CoPBit Q1 3D Constellation (16 points, v0.1)")

    # 보기 좋게 축 범위 동일하게 맞추기
    all_vals = np.array(xs + ys + zs)
    lim = float(np.max(np.abs(all_vals))) * 1.1 if all_vals.size > 0 else 1.0
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-lim, lim)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()