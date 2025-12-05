#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q22b – M8 mid-ISI + FFE(LS) + 공통 위상 노이즈 + p_ref PLL
theta_std–Eb/N0 맵 자동 생성 드라이버 v0

- 내부에서 copbit_q22a_m8_midISI_pref_phase_ls_v0.py 를 여러 번 호출
- 각 theta_std_deg 에 대해 Q22a 결과(stdout)를 파싱
- Eb/N0, theta_std_deg 별로 BER_noPLL / BER_DDonly / BER_DD+pRef 를 CSV로 저장
"""

import argparse
import csv
import subprocess
import sys
import re
from pathlib import Path


def parse_list_f(s):
    """문자열 '12,14,16' -> [12.0, 14.0, 16.0]"""
    return [float(x) for x in s.split(",") if x.strip() != ""]


ROW_RE = re.compile(
    r"^\s*([0-9.]+)\s*\|\s*([0-9.eE+-]+)\s*\|\s*([0-9.eE+-]+)\s*\|\s*([0-9.eE+-]+)"
)


def run_q22a_once(
    theta_std_deg,
    ebn0_list,
    n_sym,
    ffe_len,
    train_frac,
    mu_phase,
    alpha_ref,
    seed,
    script_name="copbit_q22a_m8_midISI_pref_phase_ls_v0.py",
):
    """
    theta_std_deg 하나에 대해 Q22a 스크립트를 실행하고,
    stdout에서 BER 표를 파싱하여 반환.

    반환 형식: list of dict
      [
        {
          "ebn0_db": 12.0,
          "theta_std_deg": 1.0,
          "ber_noPLL": ...,
          "ber_DDonly": ...,
          "ber_DD_pRef": ...
        },
        ...
      ]
    """
    # Eb/N0 리스트를 그대로 문자열로
    ebn0_str = ",".join(str(v) for v in ebn0_list)
    theta_str = f"{theta_std_deg}"

    cmd = [
        sys.executable,
        script_name,
        "--n_sym",
        str(n_sym),
        "--ebn0_list",
        ebn0_str,
        "--theta_std_list",
        theta_str,
        "--ffe_len",
        str(ffe_len),
        "--train_frac",
        str(train_frac),
        "--mu_phase",
        str(mu_phase),
        "--alpha_ref",
        str(alpha_ref),
        "--seed",
        str(seed),
    ]

    print(f"[Q22b] 실행: theta_std_deg={theta_std_deg}, cmd=")
    print("       " + " ".join(cmd))

    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("[Q22b][ERROR] Q22a 실행 실패")
        print(e.output.decode("utf-8", errors="ignore"))
        raise

    text = out.decode("utf-8", errors="ignore")

    # 표 부분 파싱
    results = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        ebn0_db = float(m.group(1))
        ber_no = float(m.group(2))
        ber_dd = float(m.group(3))
        ber_pr = float(m.group(4))
        results.append(
            {
                "ebn0_db": ebn0_db,
                "theta_std_deg": float(theta_std_deg),
                "ber_noPLL": ber_no,
                "ber_DDonly": ber_dd,
                "ber_DD_pRef": ber_pr,
            }
        )

    if not results:
        print("[Q22b][WARN] 파싱된 행이 없습니다. Q22a 출력 포맷을 확인하세요.")
    else:
        print(
            f"[Q22b] theta={theta_std_deg}° 에서 {len(results)}개 Eb/N0 포인트 파싱 완료."
        )

    return results


def main():
    parser = argparse.ArgumentParser(
        description=(
            "CoPBit Q22b – M8 mid-ISI + FFE(LS) + 공통 위상 노이즈 + p_ref PLL\n"
            "theta_std–Eb/N0 맵 자동 생성 드라이버 v0"
        )
    )
    parser.add_argument(
        "--n_sym", type=int, default=200000, help="심볼 수 (default: 200000)"
    )
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="12,14,16",
        help='Eb/N0 리스트 (dB), 예: "12,14,16"',
    )
    parser.add_argument(
        "--theta_std_list",
        type=str,
        default="0.0,0.5,0.8,1.0,1.2,1.5,2.0",
        help='theta_std_deg 리스트, 예: "0.0,0.5,0.8,1.0,1.2,1.5,2.0"',
    )
    parser.add_argument(
        "--ffe_len", type=int, default=11, help="FFE 탭 길이 (default: 11)"
    )
    parser.add_argument(
        "--train_frac",
        type=float,
        default=0.5,
        help="FFE LS 학습에 사용하는 심볼 비율 (0~1, default: 0.5)",
    )
    parser.add_argument(
        "--mu_phase",
        type=float,
        default=0.05,
        help="PLL 위상 업데이트 계수 mu_phase (default: 0.05)",
    )
    parser.add_argument(
        "--alpha_ref",
        type=float,
        default=0.3,
        help="(0→p_ref-only, 1→data-only) 혼합 비율 alpha_ref (default: 0.3)",
    )
    parser.add_argument(
        "--seed", type=int, default=1, help="난수 시드 (default: 1)"
    )
    parser.add_argument(
        "--q22a_script",
        type=str,
        default="copbit_q22a_m8_midISI_pref_phase_ls_v0.py",
        help="내부에서 호출할 Q22a 스크립트 이름 (default: copbit_q22a_m8_midISI_pref_phase_ls_v0.py)",
    )
    parser.add_argument(
        "--out_csv",
        type=str,
        default="Q22b_theta_ebn0_map.csv",
        help="출력 CSV 파일 이름 (default: Q22b_theta_ebn0_map.csv)",
    )

    args = parser.parse_args()

    ebn0_list = parse_list_f(args.ebn0_list)
    theta_list = parse_list_f(args.theta_std_list)

    print("=== CoPBit Q22b – theta_std–Eb/N0 맵 생성 시작 ===")
    print(f"[Param] n_sym       = {args.n_sym}")
    print(f"[Param] Eb/N0_list  = {ebn0_list}")
    print(f"[Param] theta_list  = {theta_list}")
    print(f"[Param] ffe_len     = {args.ffe_len}")
    print(f"[Param] train_frac  = {args.train_frac}")
    print(f"[Param] mu_phase    = {args.mu_phase}")
    print(f"[Param] alpha_ref   = {args.alpha_ref}")
    print(f"[Param] seed        = {args.seed}")
    print(f"[Param] q22a_script = {args.q22a_script}")
    print(f"[Param] out_csv     = {args.out_csv}")
    print("=================================================")

    all_rows = []

    for theta in theta_list:
        rows = run_q22a_once(
            theta_std_deg=theta,
            ebn0_list=ebn0_list,
            n_sym=args.n_sym,
            ffe_len=args.ffe_len,
            train_frac=args.train_frac,
            mu_phase=args.mu_phase,
            alpha_ref=args.alpha_ref,
            seed=args.seed,
            script_name=args.q22a_script,
        )
        all_rows.extend(rows)

    if not all_rows:
        print("[Q22b][ERROR] 수집된 데이터가 없습니다. 종료합니다.")
        sys.exit(1)

    # 정렬: Eb/N0 → theta 순
    all_rows.sort(key=lambda r: (r["ebn0_db"], r["theta_std_deg"]))

    out_path = Path(args.out_csv)
    print(f"[Q22b] CSV 저장: {out_path}")

    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ebn0_db",
                "theta_std_deg",
                "ber_noPLL",
                "ber_DDonly",
                "ber_DD_pRef",
            ]
        )
        for r in all_rows:
            writer.writerow(
                [
                    f"{r['ebn0_db']:.3f}",
                    f"{r['theta_std_deg']:.3f}",
                    f"{r['ber_noPLL']:.9f}",
                    f"{r['ber_DDonly']:.9f}",
                    f"{r['ber_DD_pRef']:.9f}",
                ]
            )

    print("[Q22b] 완료.")


if __name__ == "__main__":
    main()