#!/usr/bin/env python3
"""
CoPBit Q4 – Kuramoto Cluster Demo v0.1

목적:
- CoPBit 16포인트(4클러스터 × 4포인트) 위상 스킴에서
  Kuramoto 스타일 위상 결맞음을 이용해
  각 클러스터 중심 위상(phi_c)이 시간에 따라 어떻게 안정화되는지 시각화.

기능:
- Q1에서 정의한 16포인트 위상/클러스터 맵을 그대로 사용
- 초기 위상에 노이즈(jitter)를 주고 Kuramoto 업데이트 반복
- 시간에 따른 4개 클러스터 평균 위상을 기록
- 결과를 PNG 두 장으로 저장:
  - CoPBit_Q4_kuramoto_cluster_means.png
  - CoPBit_Q4_kuramoto_final_phases_polar.png
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt


def make_constellation():
    """
    16포인트 CoPBit 위상 스킴 + 클러스터 인덱스 정의.

    k: 0..15
    theta_deg[k] = 22.5 * k
    cluster_idx: [0,0,0,0, 1,1,1,1, 2,2,2,2, 3,3,3,3]
    """
    k = np.arange(16, dtype=int)
    theta_deg = 22.5 * k
    theta_rad = np.deg2rad(theta_deg)

    # 4포인트씩 4클러스터
    cluster_idx = np.repeat(np.arange(4, dtype=int), 4)
    return theta_rad, cluster_idx


def compute_cluster_means(theta_rad, cluster_idx):
    """
    각 클러스터별 평균 위상(phi_c)을 계산.
    theta_rad: (N,) [rad]
    cluster_idx: (N,) int in [0, n_clusters-1]
    return: (n_clusters,) [rad, 0~2π]
    """
    n_clusters = int(cluster_idx.max()) + 1
    means = np.zeros(n_clusters, dtype=float)

    for c in range(n_clusters):
        idx = np.where(cluster_idx == c)[0]
        if len(idx) == 0:
            continue
        z = np.exp(1j * theta_rad[idx])
        mean_angle = np.angle(np.mean(z))
        # -π~π 범위를 0~2π로 변환
        if mean_angle < 0:
            mean_angle += 2.0 * np.pi
        means[c] = mean_angle

    return means


def run_kuramoto_cluster_demo(
    theta0_rad,
    cluster_idx,
    n_steps=200,
    dt=0.05,
    k_intra=1.5,
    noise_std_deg=3.0,
    seed=1,
):
    """
    16개 위상(각각 4개 포인트 × 4클러스터)에 대해
    단순 Kuramoto 스타일 intra-cluster 결맞음 + 랜덤 위상 노이즈를 적용.

    - theta0_rad: 초기 위상 (N,)
    - cluster_idx: 각 위상이 속한 클러스터 인덱스 (N,)
    - n_steps: 시뮬레이션 스텝 수
    - dt: time step
    - k_intra: 같은 클러스터 내에서의 결맞음 강도
    - noise_std_deg: 스텝당 추가되는 위상 잡음 표준편차 [deg]
    - seed: RNG 시드
    """
    rng = np.random.default_rng(seed)
    theta = theta0_rad.copy()
    n_sym = theta.shape[0]
    n_clusters = int(cluster_idx.max()) + 1

    # 기록용
    theta_hist = np.zeros((n_steps + 1, n_sym), dtype=float)
    cluster_hist = np.zeros((n_steps + 1, n_clusters), dtype=float)

    theta_hist[0] = theta
    cluster_hist[0] = compute_cluster_means(theta, cluster_idx)

    noise_std_rad = np.deg2rad(noise_std_deg)

    for t in range(1, n_steps + 1):
        dtheta = np.zeros_like(theta)

        # 클러스터별로 Kuramoto intra-coupling
        for c in range(n_clusters):
            idx = np.where(cluster_idx == c)[0]
            if len(idx) == 0:
                continue

            theta_c = theta[idx]  # 해당 클러스터 위상들
            # 각 포인트별 업데이트
            for i_local, i in enumerate(idx):
                # 같은 클러스터 내 이웃과의 상호작용
                dtheta_i = (k_intra / len(idx)) * np.sum(
                    np.sin(theta_c - theta[i])
                )
                dtheta[i] = dtheta_i

        # 랜덤 위상 노이즈 추가 (화이트 노이즈)
        noise = noise_std_rad * np.sqrt(dt) * rng.standard_normal(size=n_sym)

        theta = theta + dt * dtheta + noise
        theta = np.mod(theta, 2.0 * np.pi)  # 0~2π 범위로 wrap

        theta_hist[t] = theta
        cluster_hist[t] = compute_cluster_means(theta, cluster_idx)

    return theta_hist, cluster_hist


def plot_cluster_means(cluster_hist, dt, out_path="CoPBit_Q4_kuramoto_cluster_means.png"):
    """
    시간에 따른 클러스터 평균 위상(phi_c(t))의 변화를 플로팅.
    """
    n_steps_plus_1, n_clusters = cluster_hist.shape
    t_axis = np.arange(n_steps_plus_1) * dt

    # 위상 언랩해서 선이 튀지 않게 처리
    cluster_unwrap = np.unwrap(cluster_hist, axis=0)
    cluster_deg = np.rad2deg(cluster_unwrap)

    fig = plt.figure(figsize=(8, 4))
    ax = fig.add_subplot(1, 1, 1)
    for c in range(n_clusters):
        ax.plot(t_axis, cluster_deg[:, c], label=f"cluster {c}")

    ax.set_xlabel("time [arb. unit]")
    ax.set_ylabel("cluster mean phase [deg, unwrapped]")
    ax.set_title("CoPBit Q4 – Kuramoto Cluster Mean Phase vs Time")
    ax.legend()
    ax.grid(True)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[SAVE] cluster mean figure -> {out_path}")


def plot_final_phases_polar(
    theta_final,
    cluster_idx,
    out_path="CoPBit_Q4_kuramoto_final_phases_polar.png",
):
    """
    마지막 스텝에서의 16개 포인트 위치와 클러스터 평균을 polar plot으로 저장.
    """
    n_clusters = int(cluster_idx.max()) + 1
    cluster_means = compute_cluster_means(theta_final, cluster_idx)

    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1, projection="polar")

    # 각 포인트는 반지름 1.0, 클러스터 평균은 반지름 1.2에 찍는다.
    r_points = np.ones_like(theta_final)
    r_means = np.ones_like(cluster_means) * 1.2

    # 개별 포인트
    ax.scatter(theta_final, r_points, s=40, alpha=0.8)
    # 클러스터 평균
    ax.scatter(cluster_means, r_means, s=80, marker="x")

    ax.set_title("CoPBit Q4 – Final Phases and Cluster Means (Polar)")
    ax.set_rlim(0, 1.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[SAVE] final polar figure -> {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q4 – Kuramoto Cluster Demo v0.1"
    )
    parser.add_argument(
        "--n_steps",
        type=int,
        default=200,
        help="Kuramoto 시뮬레이션 스텝 수 (default: 200)",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.05,
        help="time step (default: 0.05)",
    )
    parser.add_argument(
        "--k_intra",
        type=float,
        default=1.5,
        help="클러스터 내부 결맞음 강도 K (default: 1.5)",
    )
    parser.add_argument(
        "--noise_std_deg",
        type=float,
        default=3.0,
        help="스텝당 위상 노이즈 표준편차 [deg] (default: 3.0)",
    )
    parser.add_argument(
        "--init_jitter_deg",
        type=float,
        default=10.0,
        help="초기 위상에 주는 jitter 표준편차 [deg] (default: 10.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="랜덤 시드 (default: 1)",
    )

    args = parser.parse_args()

    print("=== CoPBit Q4 – Kuramoto Cluster Demo v0.1 ===")
    print(f"[Param] n_steps        = {args.n_steps}")
    print(f"[Param] dt             = {args.dt}")
    print(f"[Param] k_intra        = {args.k_intra}")
    print(f"[Param] noise_std_deg  = {args.noise_std_deg}")
    print(f"[Param] init_jitter_deg= {args.init_jitter_deg}")
    print(f"[Param] seed           = {args.seed}")
    print("------------------------------------------------")

    # 16포인트 위상 + 클러스터 인덱스 생성
    theta_base_rad, cluster_idx = make_constellation()
    rng = np.random.default_rng(args.seed)

    # 초기 위상에 jitter 추가
    init_jitter_rad = np.deg2rad(args.init_jitter_deg)
    theta0_rad = theta_base_rad + init_jitter_rad * rng.standard_normal(
        size=theta_base_rad.shape
    )
    theta0_rad = np.mod(theta0_rad, 2.0 * np.pi)

    init_means = compute_cluster_means(theta0_rad, cluster_idx)
    print("[Init] cluster mean phases (deg):")
    print("       ", np.round(np.rad2deg(init_means), 3))

    # Kuramoto 시뮬레이션 실행
    theta_hist, cluster_hist = run_kuramoto_cluster_demo(
        theta0_rad=theta0_rad,
        cluster_idx=cluster_idx,
        n_steps=args.n_steps,
        dt=args.dt,
        k_intra=args.k_intra,
        noise_std_deg=args.noise_std_deg,
        seed=args.seed,
    )

    final_theta = theta_hist[-1]
    final_means = cluster_hist[-1]
    print("[Final] cluster mean phases (deg):")
    print("        ", np.round(np.rad2deg(final_means), 3))

    # 클러스터별 order parameter(결맞음 정도)도 한번 찍어본다.
    n_clusters = int(cluster_idx.max()) + 1
    R_list = []
    for c in range(n_clusters):
        idx = np.where(cluster_idx == c)[0]
        if len(idx) == 0:
            R_list.append(0.0)
            continue
        z = np.exp(1j * final_theta[idx])
        R = np.abs(np.mean(z))
        R_list.append(R)
    print("[Final] cluster-wise order parameter R (0~1):")
    print("        ", np.round(np.array(R_list), 4))

    # 그림 저장
    plot_cluster_means(cluster_hist, dt=args.dt)
    plot_final_phases_polar(final_theta, cluster_idx)

    print("=== Done: CoPBit Q4 Kuramoto cluster demo completed. ===")


if __name__ == "__main__":
    main()