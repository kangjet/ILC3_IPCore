#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q2 – Kuramoto 위상 커플링 데모 v0.1

- Q1에서 정의한 16포인트 (4bit/심볼) 위성을 Kuramoto 모델 위에 올려서
  클러스터별 위상 동기화/비동기화 경향을 보는 간단 데모 스크립트.

사용:
    python copbit_q2_kuramoto_demo_v0.py

(필요시 matplotlib 설치: pip install matplotlib)
"""

import math
import numpy as np

try:
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    HAS_PLOT = False


def make_constellation_q1(phi_step=math.pi/16.0):
    """
    Q1에서 정의한 16포인트 위성을 기반으로
    θ_k, 클러스터 인덱스 c_i, φ_c 를 생성한다.

    반환:
        theta0: shape (16,), 초기 위상 (rad)
        cluster_idx: shape (16,), 각 포인트의 클러스터 c_i
        phi_c: shape (4,), 각 클러스터별 φ_c
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


def make_coupling_matrix(cluster_idx, k_intra=1.0, k_inter=0.1):
    """
    클러스터 인덱스에 따라 K_{ij} 커플링 행렬 생성.
    같은 클러스터: k_intra, 다른 클러스터: k_inter
    (i == j 인 경우 0)
    """
    N = len(cluster_idx)
    K = np.zeros((N, N), dtype=float)

    for i in range(N):
        for j in range(N):
            if i == j:
                K[i, j] = 0.0
            else:
                if cluster_idx[i] == cluster_idx[j]:
                    K[i, j] = k_intra
                else:
                    K[i, j] = k_inter
    return K


def simulate_kuramoto(theta0, K, omega=None, dt=0.05, t_total=50.0):
    """
    이산 시간 Kuramoto 시뮬레이션 (오일러 방식)

    theta0: shape (N,), 초기 위상 (rad)
    K: shape (N,N), 커플링 행렬
    omega: shape (N,), 자연 주파수 (None이면 모두 0)
    dt: 시간 스텝
    t_total: 전체 시뮬레이션 시간

    반환:
        t_vec: shape (T,), 시간 축
        theta_hist: shape (T,N), 각 시점 위상 값
    """
    N = len(theta0)
    if omega is None:
        omega = np.zeros(N, dtype=float)

    num_steps = int(t_total / dt)
    theta = theta0.copy()
    theta_hist = np.zeros((num_steps, N), dtype=float)
    t_vec = np.arange(num_steps) * dt

    for t_idx in range(num_steps):
        theta_hist[t_idx, :] = theta

        # Kuramoto 갱신식
        # dθ_i/dt = ω_i + (1/N) * Σ_j K_ij * sin(θ_j - θ_i)
        dtheta = np.zeros(N, dtype=float)
        for i in range(N):
            coupling_sum = 0.0
            for j in range(N):
                if i == j:
                    continue
                coupling_sum += K[i, j] * math.sin(theta[j] - theta[i])
            dtheta[i] = omega[i] + (1.0 / N) * coupling_sum

        theta = theta + dt * dtheta

        # 2π wrapping (보기 좋게)
        theta = (theta + 2.0 * math.pi) % (2.0 * math.pi)

    return t_vec, theta_hist


def compute_cluster_mean_phase(theta_hist, cluster_idx, num_clusters=4):
    """
    각 시간 스텝마다 클러스터별 평균 위상 계산.
    단순 평균이 아니라, 복소수 평균을 사용해 위상 wrap-around 문제 완화.

    반환:
        mean_phase: shape (T, num_clusters)
    """
    T, N = theta_hist.shape
    mean_phase = np.zeros((T, num_clusters), dtype=float)

    for t_idx in range(T):
        theta_t = theta_hist[t_idx, :]
        for c in range(num_clusters):
            mask = (cluster_idx == c)
            if not np.any(mask):
                continue
            # 복소 평균
            z = np.exp(1j * theta_t[mask])
            z_mean = np.mean(z)
            mean_phase[t_idx, c] = math.atan2(z_mean.imag, z_mean.real)

    return mean_phase


def main():
    # 1) Q1 위성 가져오기
    theta0, cluster_idx, phi_c = make_constellation_q1(phi_step=math.pi / 16.0)
    print("=== CoPBit Q2 Kuramoto Demo v0.1 ===")
    print("Initial theta0 (deg):", np.round(theta0 * 180.0 / math.pi, 2))
    print("Cluster idx:", cluster_idx)
    print("phi_c (deg):", np.round(phi_c * 180.0 / math.pi, 2))

    # 2) 커플링 행렬 (실험 1: intra 강, inter 약)
    K_intra = 1.0
    K_inter = 0.1
    K = make_coupling_matrix(cluster_idx, k_intra=K_intra, k_inter=K_inter)

    # 3) 시뮬레이션 실행
    dt = 0.05
    t_total = 50.0
    t_vec, theta_hist = simulate_kuramoto(theta0, K, omega=None, dt=dt, t_total=t_total)

    # 4) 클러스터별 평균 위상 계산
    mean_phase = compute_cluster_mean_phase(theta_hist, cluster_idx, num_clusters=4)

    # 5) 텍스트 요약 출력 (마지막 시점)
    final_deg = np.round(theta_hist[-1, :] * 180.0 / math.pi, 2)
    print("\n[Result] final theta (deg):", final_deg)
    print("[Result] final cluster mean (deg):",
          np.round(mean_phase[-1, :] * 180.0 / math.pi, 2))

    if HAS_PLOT:
        # 전체 16포인트 위상 궤적 (옵션)
        plt.figure()
        for i in range(theta_hist.shape[1]):
            plt.plot(t_vec, theta_hist[:, i] * 180.0 / math.pi, alpha=0.4)
        plt.xlabel("time")
        plt.ylabel("theta (deg)")
        plt.title("Kuramoto phases (all 16 points)")
        plt.grid(True)

        # 클러스터별 평균 위상 궤적
        plt.figure()
        for c in range(mean_phase.shape[1]):
            plt.plot(t_vec, mean_phase[:, c] * 180.0 / math.pi, label=f"cluster {c}")
        plt.xlabel("time")
        plt.ylabel("mean phase (deg)")
        plt.title("Cluster mean phases")
        plt.legend()
        plt.grid(True)

        plt.show()
    else:
        print("\n[INFO] matplotlib이 없어 플롯은 생략되었습니다.")


if __name__ == "__main__":
    main()