#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
채널 b 에 대한 Q4 FFE 스윕 결과 분석 스크립트

- 입력: pam4_vs_ilc3_awgn_isi_ffe_sweep_q4_YYYY-MM-DD_HH-MM-SS.csv
- 기능:
  1) 채널 b 데이터만 필터링
  2) SNR별로 FFE_LEN × FFE_RIDGE 에 대한
     PAM4 / ILC3_0c_gp acc 테이블 요약
  3) 선택 SNR에 대해 히트맵(FFE_LEN vs FFE_RIDGE, acc 값) 출력
"""

import sys
import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def load_csv(path):
    path = Path(path)
    rows = []
    with path.open("r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split(",")
            if len(parts) != len(header):
                continue
            row = dict(zip(header, parts))
            rows.append(row)
    return rows


def filter_channel_b(rows):
    return [r for r in rows if r["chan"] == "b"]


def unique_sorted(values, conv=float):
    xs = sorted({conv(v) for v in values})
    return xs


def summarize_tables(rows_b):
    # 어떤 값들이 있는지 확인
    snrs = unique_sorted([r["snr_db"] for r in rows_b], float)
    ffe_lens = unique_sorted([r["FFE_LEN"] for r in rows_b], int)
    ridges = unique_sorted([r["FFE_RIDGE"] for r in rows_b], float)

    print("=== Channel b: available values ===")
    print("SNR_dB   :", snrs)
    print("FFE_LEN  :", ffe_lens)
    print("FFE_RIDGE:", ridges)
    print()

    # SNR별로 테이블 요약 (PAM4 / ILC3 각각)
    for snr in snrs:
        print(f"--- SNR = {snr:.2f} dB ---")
        print("PAM4 acc 테이블 (rows=FFE_LEN, cols=FFE_RIDGE):")
        print_table_for_scheme(rows_b, snr, scheme="PAM4",
                               ffe_lens=ffe_lens, ridges=ridges)
        print()
        print("ILC3_0c_gp acc 테이블 (rows=FFE_LEN, cols=FFE_RIDGE):")
        print_table_for_scheme(rows_b, snr, scheme="ILC3_0c_gp",
                               ffe_lens=ffe_lens, ridges=ridges)
        print()


def print_table_for_scheme(rows_b, snr_target, scheme, ffe_lens, ridges):
    # 행: FFE_LEN, 열: ridge, 값: acc
    acc_mat = np.full((len(ffe_lens), len(ridges)), np.nan, dtype=float)

    for r in rows_b:
        snr = float(r["snr_db"])
        if abs(snr - snr_target) > 1e-6:
            continue
        if r["scheme"] != scheme:
            continue
        L = int(r["FFE_LEN"])
        ridge = float(r["FFE_RIDGE"])
        acc = float(r["acc"])

        i = ffe_lens.index(L)
        j = ridges.index(ridge)
        acc_mat[i, j] = acc

    # 헤더
    header = "FFE_LEN \\ ridge"
    for ridge in ridges:
        header += f"\t{ridge:g}"
    print(header)
    for i, L in enumerate(ffe_lens):
        line = f"{L:>8d}"
        for j in range(len(ridges)):
            v = acc_mat[i, j]
            if math.isnan(v):
                line += "\t-"
            else:
                line += f"\t{v:.4f}"
        print(line)


def plot_heatmap(rows_b, snr_target=10.0, scheme="PAM4"):
    """
    선택한 SNR / scheme 에 대해
    FFE_LEN × FFE_RIDGE 히트맵(acc)을 그림.
    """
    ffe_lens = unique_sorted([r["FFE_LEN"] for r in rows_b], int)
    ridges = unique_sorted([r["FFE_RIDGE"] for r in rows_b], float)

    acc_mat = np.full((len(ffe_lens), len(ridges)), np.nan, dtype=float)
    for r in rows_b:
        snr = float(r["snr_db"])
        if abs(snr - snr_target) > 1e-6:
            continue
        if r["scheme"] != scheme:
            continue
        L = int(r["FFE_LEN"])
        ridge = float(r["FFE_RIDGE"])
        acc = float(r["acc"])

        i = ffe_lens.index(L)
        j = ridges.index(ridge)
        acc_mat[i, j] = acc

    fig, ax = plt.subplots()
    im = ax.imshow(acc_mat, origin="lower", aspect="auto")

    ax.set_xticks(range(len(ridges)))
    ax.set_yticks(range(len(ffe_lens)))
    ax.set_xticklabels([f"{r:g}" for r in ridges], rotation=45, ha="right")
    ax.set_yticklabels([str(L) for L in ffe_lens])

    ax.set_xlabel("FFE_RIDGE")
    ax.set_ylabel("FFE_LEN")
    ax.set_title(f"Channel b  acc heatmap  (scheme={scheme}, SNR={snr_target:.2f} dB)")

    fig.colorbar(im, ax=ax, label="acc")
    plt.tight_layout()
    plt.show()


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_q4_ffe_sweep_channel_b.py <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    rows = load_csv(csv_path)
    rows_b = filter_channel_b(rows)

    if not rows_b:
        print("No rows for channel b in the given CSV.")
        sys.exit(1)

    # 1) 텍스트 테이블 요약
    summarize_tables(rows_b)

    # 2) 히트맵 그리기 (원하면 SNR / scheme 바꿔서 여러 번 호출)
    # 예: SNR=10 dB, PAM4 / ILC3 각각 확인
    print("히트맵: SNR=10 dB, scheme='PAM4'")
    plot_heatmap(rows_b, snr_target=10.0, scheme="PAM4")

    print("히트맵: SNR=10 dB, scheme='ILC3_0c_gp'")
    plot_heatmap(rows_b, snr_target=10.0, scheme="ILC3_0c_gp")


if __name__ == "__main__":
    main()