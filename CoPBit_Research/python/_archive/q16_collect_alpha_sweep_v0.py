#!/usr/bin/env python3
"""
Q16 alpha_ref sweep log collector v0

대상 파일:
  ../note/Q16_theta3p0_alpha*.log

역할:
  - 각 로그에서 Eb/N0_dB 행을 파싱
  - alpha_ref 값과 함께 MD 테이블로 정리해서 stdout에 출력
"""

import glob
import os
import re
from typing import Dict, Tuple, List


def parse_line(line: str):
    """
    '   12.0 |   0.502891667 |   0.502435000 |   0.038020000'
    이런 형태에서 (eb, ber_no, ber_dd, ber_kur) 튜플로 파싱
    """
    if "|" not in line:
        return None
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 4:
        return None
    try:
        eb = float(parts[0])
        ber_no_pll = float(parts[1])
        ber_ddonly = float(parts[2])
        ber_kur = float(parts[3])
    except ValueError:
        return None
    return eb, ber_no_pll, ber_ddonly, ber_kur


def collect_logs(pattern: str = "../note/Q16_theta3p0_alpha*.log"):
    """
    pattern에 매칭되는 모든 로그에서 데이터 수집
    반환:
      data[alpha_ref][eb] = (ber_no_pll, ber_ddonly, ber_kur)
    """
    data: Dict[float, Dict[float, Tuple[float, float, float]]] = {}

    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[WARN] No log files matched pattern: {pattern}")
        return data

    alpha_re = re.compile(r"alpha([0-9.]+)\.log$")

    for fpath in files:
        fname = os.path.basename(fpath)
        m = alpha_re.search(fname)
        if not m:
            print(f"[WARN] Skip (alpha parse fail): {fname}")
            continue
        alpha_str = m.group(1)
        alpha = float(alpha_str)

        with open(fpath, "r") as f:
            for line in f:
                line = line.strip()
                # 데이터 라인만 파싱
                parsed = parse_line(line)
                if parsed is None:
                    continue
                eb, ber_no, ber_dd, ber_kur = parsed

                data.setdefault(alpha, {})
                data[alpha][eb] = (ber_no, ber_dd, ber_kur)

    return data


def print_md_table(data: Dict[float, Dict[float, Tuple[float, float, float]]]):
    """
    data를 MD 테이블로 출력.
    형식:
      | alpha_ref | Eb/N0_dB | BER_noPLL | BER_DDonly | BER_DD+pRef |
    """
    if not data:
        print("[INFO] No data to print.")
        return

    # 정렬된 alpha / Eb 리스트
    alpha_list: List[float] = sorted(data.keys())
    # Eb 리스트는 첫 alpha에서 가져온 후 정렬
    sample_alpha = alpha_list[0]
    eb_list: List[float] = sorted(data[sample_alpha].keys())

    print("# Q16 – θ_std_deg = 3°에서 alpha_ref 스윕 결과")
    print()
    print("| alpha_ref | Eb/N0_dB | BER_noPLL | BER_DDonly | BER_DD+pRef |")
    print("|-----------|----------|-----------|------------|-------------|")

    for alpha in alpha_list:
        for eb in eb_list:
            if eb not in data[alpha]:
                continue
            ber_no, ber_dd, ber_kur = data[alpha][eb]
            print(
                f"| {alpha:7.3f} | {eb:8.1f} | "
                f"{ber_no:9.6f} | {ber_dd:10.6f} | {ber_kur:11.6f} |"
            )

    print()


def main():
    data = collect_logs("../note/Q16_theta3p0_alpha*.log")
    print_md_table(data)


if __name__ == "__main__":
    main()