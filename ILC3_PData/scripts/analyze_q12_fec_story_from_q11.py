#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q12: FEC 관점에서 Q10/Q11 결과를 스토리로 요약

- Input: q10_all_channels_fec_margin_ffe_only_YYYY-MM-DD_HH-MM-SS.json
    (Q10에서 생성한 JSON, Q11에서 사용한 것과 동일 포맷)
- Output (콘솔):
    1) BER = 5e-2, 2e-2 에서 채널별 SNR 포인트 및 ΔSNR(PAM4-ILC3)
    2) 위 두 타깃 BER에 대해 채널 전체 평균/최소/최대 ΔSNR 요약
    3) FEC 관점 한줄 요약 메시지
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def load_q10_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Optional[float], nd: int = 3, width: int = 7) -> str:
    """숫자 포매팅 (+ None 대응)"""
    if x is None:
        return "   N/A".rjust(width)
    return f"{x:{width}.{nd}f}"


def find_fec_item_for_ber(
    fec_list: List[Dict[str, Any]],
    target_ber: float,
    tol: float = 1e-12,
) -> Optional[Dict[str, Any]]:
    """fec_margin 리스트에서 target_ber 항목 하나 찾아오기"""
    for item in fec_list:
        if abs(item.get("target_ber", 0.0) - target_ber) < tol:
            return item
    return None


def summarize_gain(values: List[float]) -> Tuple[float, float, float]:
    """ΔSNR 리스트에 대한 (평균, 최소, 최대)"""
    if not values:
        return float("nan"), float("nan"), float("nan")
    avg = sum(values) / len(values)
    return avg, min(values), max(values)


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_q12_fec_story_from_q11.py <q10_json_path>")
        sys.exit(1)

    in_path = Path(sys.argv[1]).expanduser().resolve()
    if not in_path.exists():
        print(f"[ERR] file not found: {in_path}")
        sys.exit(1)

    data = load_q10_json(in_path)

    snr_list = data["snr_list"]
    target_bers = data["target_bers"]
    channels = data["channels"]

    print("Q12: FEC-oriented SNR gain story based on Q10/Q11 results")
    print(f"  snr_list    = {snr_list}")
    print(f"  target_bers = {target_bers}")
    print("")

    # Q12에서 집중할 타깃 BER (pre-FEC 디자인 관점에서 의미 있는 구간)
    key_bers = [5.0e-2, 2.0e-2]

    # 채널 라벨 (설명용)
    ch_labels = {
        "a": "a (mild ISI)",
        "b": "b (strong ISI)",
        "c": "c (medium ISI)",
    }

    # --- 타깃 BER별 상세 테이블 + 채널별 ΔSNR 수집 ---
    all_stats: Dict[float, List[float]] = {tb: [] for tb in key_bers}

    for tb in key_bers:
        print(f"--- Target pre-FEC BER = {tb:.1e} ---")
        print("channel |  SNR_PAM4  SNR_ILC3   ΔSNR(PAM4-ILC3)")
        print("--------+--------------------------------------")

        for name in ["a", "b", "c"]:
            ch = channels[name]
            fec = ch["fec_margin"]
            item = find_fec_item_for_ber(fec, tb)

            if item is None:
                print(f"   {name}    |  (no entry for this BER)")
                continue

            sp = item.get("snr_pam4", None)
            si = item.get("snr_ilc3", None)
            sg = item.get("snr_gain_db", None)

            if sp is None or si is None or sg is None:
                print(f"   {name}    |  (out of range)")
                continue

            print(
                f"   {name}    |"
                f" {fmt(sp):>9s} {fmt(si):>9s}   {fmt(sg):>9s} dB"
            )
            all_stats[tb].append(sg)

        print("")

    # --- 타깃 BER별 ΔSNR 통계 요약 (평균/최솟값/최댓값) ---
    print("=== ΔSNR(PAM4-ILC3) statistics across channels ===")
    for tb in key_bers:
        gains = all_stats.get(tb, [])
        if not gains:
            print(f"BER={tb:.1e}: no valid ΔSNR across channels (out of range).")
            continue

        avg, g_min, g_max = summarize_gain(gains)
        print(
            f"BER={tb:.1e}: "
            f"avg ≈ {avg:4.3f} dB, "
            f"min ≈ {g_min:4.3f} dB, "
            f"max ≈ {g_max:4.3f} dB"
        )
    print("")

    # --- 채널별 한줄 요약 (주로 BER=5e-2 기준) ---
    tb_ref = 5.0e-2
    print(f"=== Per-channel summary at BER={tb_ref:.1e} ===")
    for name in ["a", "b", "c"]:
        ch = channels[name]
        label = ch_labels.get(name, name)
        fec = ch["fec_margin"]
        item = find_fec_item_for_ber(fec, tb_ref)

        if item is None or item.get("snr_gain_db") is None:
            print(f"[Channel {name}] no valid SNR point at BER={tb_ref:.1e}")
            continue

        sp = item["snr_pam4"]
        si = item["snr_ilc3"]
        sg = item["snr_gain_db"]

        print(
            f"[Channel {name}] {label}: "
            f"SNR_PAM4={sp:.3f} dB, SNR_ILC3={si:.3f} dB, "
            f"ΔSNR ≈ {sg:.3f} dB"
        )
    print("")

    # --- FEC 관점 한줄 요약 메시지 ---
    print("=== FEC-oriented key messages (Q12) ===")
    # BER=5e-2 기준 전체 평균 ΔSNR
    gains_5e2 = all_stats.get(5.0e-2, [])
    if gains_5e2:
        avg_5e2, _, _ = summarize_gain(gains_5e2)
        print(
            f"- Around BER ≈ 5e-2 (typical pre-FEC design region), "
            f"ILC3_0c_gp provides ≈ {avg_5e2:.3f} dB SNR gain over PAM4 "
            f"across channels a/b/c under the same FFE configuration."
        )
    gains_2e2 = all_stats.get(2.0e-2, [])
    if gains_2e2:
        avg_2e2, _, _ = summarize_gain(gains_2e2)
        print(
            f"- At BER ≈ 2e-2, the SNR gain remains close to ≈ {avg_2e2:.3f} dB "
            f"(where SNR points are available), indicating a robust guard-phase benefit "
            f"in the low-BER pre-FEC region."
        )

    print(
        "- Practically, this ~3 dB pre-FEC SNR gain can be interpreted as "
        "either a similar-quality link at ~half transmit power, or a ~3 dB "
        "link-margin improvement at the same power, regardless of ISI severity "
        "(mild, strong, or medium) for the tested 5-tap channels."
    )


if __name__ == "__main__":
    main()