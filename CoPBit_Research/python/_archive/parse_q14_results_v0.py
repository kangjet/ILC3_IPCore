#!/usr/bin/env python3
"""
CoPBit Q14 – mu/phi/drift sweep log parser v0.1

역할:
- ../note/ 아래에 있는 Q14 로그들
    예) Q14_drift1p0_mu0.10_phi10.0_L64.log
  을 읽어서,
    drift_deg, mu_phase, phi_max_deg, lanes, EbN0_dB,
    BER_M8_base, BER_M8_kura
  를 한 방에 CSV로 모은다.

사용 예:
    python parse_q14_results_v0.py \
      --log_glob "../note/Q14_drift*_L64.log" \
      --csv_out "../note/CoPBit_Q14_mu_phi_drift_sweep_summary.csv"
"""

import argparse
import glob
import os
import re
import csv


def parse_filename(fname):
    """
    파일명에서 drift_deg, mu_phase, phi_max_deg, lanes 파싱.
    예: Q14_drift1p0_mu0.10_phi10.0_L64.log
    """
    base = os.path.basename(fname)

    # 정규식으로 각 파라미터 추출
    # drift1p0 → 1.0, mu0.10 → 0.10, phi10.0 → 10.0, L64 → 64
    m = re.search(
        r"Q14_drift(?P<drift>[0-9p\.]+)_mu(?P<mu>[0-9\.]+)_phi(?P<phi>[0-9\.]+)_L(?P<L>[0-9]+)\.log",
        base,
    )
    if not m:
        raise ValueError(f"파일명에서 파라미터를 파싱할 수 없음: {base}")

    def p_to_dot(x: str) -> float:
        # "1p0" 같은 형식도 대비
        return float(x.replace("p", "."))

    drift_deg = p_to_dot(m.group("drift"))
    mu_phase = float(m.group("mu"))
    phi_max_deg = float(m.group("phi"))
    lanes = int(m.group("L"))

    return drift_deg, mu_phase, phi_max_deg, lanes


def parse_single_log(path, rows_out):
    """
    단일 Q14 로그 파일을 파싱해서 rows_out(list of dict)에 append.
    로그 형식 예:

    ================= drift_std_deg = 1.00 deg =================
     n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
    ------------------------------------------------------
         64 |    18.0 |   5.133e-01 |   2.890e-02
         64 |    19.0 |   5.058e-01 |   1.897e-02
    ------------------------------------------------------
    """
    drift_deg_fn, mu_phase, phi_max_deg, lanes_fn = parse_filename(path)

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 로그 안에 drift_std_deg 라인도 있지만,
    # 일단 파일명 우선, 로그 안 값은 있으면 체크 정도만.
    drift_deg_log = None
    for line in lines:
        if "drift_std_deg" in line:
            # 예: "================ drift_std_deg = 1.00 deg ================="
            m = re.search(r"drift_std_deg\s*=\s*([0-9\.]+)", line)
            if m:
                drift_deg_log = float(m.group(1))

    if drift_deg_log is not None:
        # 양쪽이 너무 다르면 경고만 (실제 실행에서는 print 정도)
        if abs(drift_deg_log - drift_deg_fn) > 1e-3:
            print(
                f"[WARN] {os.path.basename(path)}: "
                f"filename drift={drift_deg_fn}, log drift={drift_deg_log}"
            )

    # BER 테이블 라인 파싱
    for line in lines:
        # 파이프(|)가 포함된 수치 라인만 타겟
        if "|" not in line:
            continue
        if "EbN0_dB" in line:
            continue
        if "n_lanes" in line:
            continue
        if "----" in line:
            continue

        # 예: "     64 |    18.0 |   5.133e-01 |   2.890e-02"
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue

        try:
            n_lanes = int(parts[0])
            ebn0_db = float(parts[1])
            ber_base = float(parts[2])
            ber_kura = float(parts[3])
        except ValueError:
            # 숫자 파싱 실패하면 스킵
            continue

        row = {
            "log_file": os.path.basename(path),
            "drift_deg": drift_deg_fn,
            "mu_phase": mu_phase,
            "phi_max_deg": phi_max_deg,
            "lanes": n_lanes,
            "EbN0_dB": ebn0_db,
            "BER_M8_base": ber_base,
            "BER_M8_kura": ber_kura,
        }
        rows_out.append(row)


def main():
    ap = argparse.ArgumentParser(
        description="Parse CoPBit Q14 drift/mu/phi sweep logs into a CSV summary."
    )
    ap.add_argument(
        "--log_glob",
        type=str,
        default="../note/Q14_drift*_L64.log",
        help="Q14 로그 파일 glob 패턴 [기본: '../note/Q14_drift*_L64.log']",
    )
    ap.add_argument(
        "--csv_out",
        type=str,
        default="../note/CoPBit_Q14_mu_phi_drift_sweep_summary.csv",
        help="요약 CSV 출력 경로 [기본: '../note/CoPBit_Q14_mu_phi_drift_sweep_summary.csv']",
    )
    args = ap.parse_args()

    paths = sorted(glob.glob(args.log_glob))
    if not paths:
        print(f"[WARN] log_glob '{args.log_glob}' 에 해당하는 파일이 없음.")
        return

    print(f"[INFO] 총 {len(paths)}개 Q14 로그 파싱 시작.")

    rows = []
    for path in paths:
        print(f"[INFO] parsing {os.path.basename(path)}")
        parse_single_log(path, rows)

    # CSV 저장
    fieldnames = [
        "log_file",
        "drift_deg",
        "mu_phase",
        "phi_max_deg",
        "lanes",
        "EbN0_dB",
        "BER_M8_base",
        "BER_M8_kura",
    ]

    os.makedirs(os.path.dirname(args.csv_out), exist_ok=True)
    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"[DONE] {len(rows)} rows → '{args.csv_out}'")


if __name__ == "__main__":
    main()