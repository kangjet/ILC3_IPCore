#!/usr/bin/env python3
"""
plot_q13d_drift_lane_scaling_v0.py

CoPBit Q13d – Drift 허용 범위 & Lane 스케일링 (Channel-b, M8, FFE=7) 시각화 스크립트.

그리는 그림:
1) Eb/N0 vs BER 곡선 (drift_std_deg = 0.25°, n_lanes = 64, FFE=7)
2) drift_std_deg vs BER (Eb/N0 = 22 dB, n_lanes = 64, FFE=7)
3) lane 수 vs BER (Eb/N0 = 20 dB, drift_std_deg = 0.25°, FFE=7)

현재는 실험 로그에서 읽은 값을 코드 안에 직접 하드코딩해 둔 버전.
필요하면 나중에 CSV/JSON에서 읽어오는 방식으로 확장하면 된다.
"""

import math
import matplotlib.pyplot as plt


def plot_ebn0_vs_ber():
    # Q13d: ffe_len = 7, drift_std_deg = 0.25, n_lanes = 64
    # n_sym=500k 기준 로그에서 읽은 값
    ebn0_db = [18, 19, 20, 21, 22]
    ber_kura = [2.486e-2, 1.594e-2, 9.790e-3, 5.744e-3, 3.284e-3]

    plt.figure()
    plt.semilogy(ebn0_db, ber_kura, marker="o")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.xlabel("Eb/N0 (dB)")
    plt.ylabel("BER (Kuramoto, log scale)")
    plt.title("Q13d – Eb/N0 vs BER (drift=0.25°, L=64, FFE=7)")
    # 1e-2 threshold 라인
    plt.axhline(1e-2, linestyle=":", linewidth=0.8)
    plt.text(ebn0_db[0] + 0.1, 1.1e-2, "1e-2 threshold", fontsize=9)
    plt.tight_layout()
    plt.savefig("Q13d_EbN0_vs_BER_drift0p25_L64_FFE7.png", dpi=200)


def plot_drift_vs_ber():
    # Q13d: Eb/N0 = 22 dB, ffe_len = 7, n_lanes = 64
    drift_deg = [0.25, 0.5, 1.0, 2.0, 3.0]
    ber_kura = [3.279e-3, 3.517e-3, 4.563e-3, 4.393e-1, 4.872e-1]

    plt.figure()
    plt.semilogy(drift_deg, ber_kura, marker="o")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.xlabel("Drift std (deg)")
    plt.ylabel("BER (Kuramoto, log scale)")
    plt.title("Q13d – Drift tolerance at 22 dB (L=64, FFE=7)")
    # 대략적인 안정 영역/붕괴 영역 표시
    plt.axvline(1.0, linestyle=":", linewidth=0.8)
    plt.text(1.02, 1e-2, "≈ stable up to ~1°", fontsize=9)
    plt.tight_layout()
    plt.savefig("Q13d_DriftStd_vs_BER_EbN0_22dB_L64_FFE7.png", dpi=200)


def plot_lanes_vs_ber():
    # Q13d: Eb/N0 = 20 dB, drift_std_deg = 0.25, ffe_len = 7
    lanes = [16, 64, 256]
    ber_kura = [9.871e-3, 9.753e-3, 9.729e-3]

    plt.figure()
    plt.semilogy(lanes, ber_kura, marker="o")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.xlabel("Number of lanes")
    plt.ylabel("BER (Kuramoto, log scale)")
    plt.title("Q13d – Lane scaling at 20 dB (drift=0.25°, FFE=7)")
    # 16 lanes 이상에서 포화된다는 메시지를 위해 살짝 주석 위치 표시
    plt.text(18, 1.1e-2, "16 lanes 이상에서 BER 거의 동일", fontsize=9)
    plt.xticks(lanes)
    plt.tight_layout()
    plt.savefig("Q13d_Lanes_vs_BER_EbN0_20dB_drift0p25_FFE7.png", dpi=200)


def main():
    plot_ebn0_vs_ber()
    plot_drift_vs_ber()
    plot_lanes_vs_ber()
    print("Saved:")
    print(" - Q13d_EbN0_vs_BER_drift0p25_L64_FFE7.png")
    print(" - Q13d_DriftStd_vs_BER_EbN0_22dB_L64_FFE7.png")
    print(" - Q13d_Lanes_vs_BER_EbN0_20dB_drift0p25_FFE7.png")


if __name__ == "__main__":
    main()