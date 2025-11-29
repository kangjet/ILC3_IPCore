#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q13: FEC 링크 버짓 관점 스토리 정리

- Input: Q10 JSON
    q10_all_channels_fec_margin_ffe_only_YYYY-MM-DD_HH-MM-SS.json
- Output:
    1) 콘솔:
       - BER = 5e-2, 2e-2 에서 채널별 SNR 및 ΔSNR, 전력비 해석
       - ΔSNR 통계 (평균/최소/최대)
       - 링크 버짓 관점 한줄 스토리
    2) MD 파일:
       results/q13_fec_link_budget_story_from_<Q10_JSON_STEM>.md
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def load_q10_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Optional[float], nd: int = 3, width: int = 7) -> str:
    """숫자 포맷팅 (+ None 대응)"""
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


def power_ratio_from_gain_db(gain_db: float) -> float:
    """ΔSNR(dB) -> 전력비 (P_PAM4 / P_ILC3)"""
    return 10.0 ** (gain_db / 10.0)


def build_md(
    q10_path: Path,
    snr_list: List[float],
    key_bers: List[float],
    channels: Dict[str, Any],
    per_ber_stats: Dict[float, Dict[str, Any]],
    per_channel_5e2: Dict[str, Dict[str, float]],
) -> str:
    """Q13 링크 버짓 스토리용 MD 텍스트 생성"""

    stem = q10_path.stem

    # 대표값: BER=5e-2 기준 평균 ΔSNR
    ber_5e2 = 5.0e-2
    stats_5e2 = per_ber_stats.get(ber_5e2, {})
    avg_5e2 = stats_5e2.get("avg_gain", float("nan"))

    ber_2e2 = 2.0e-2
    stats_2e2 = per_ber_stats.get(ber_2e2, {})
    avg_2e2 = stats_2e2.get("avg_gain", float("nan"))

    lines: List[str] = []

    lines.append(f"# Q13 – ILC3_0c_guard-phase FEC Link-Budget Story")
    lines.append("")
    lines.append(f"- Source JSON (Q10 결과): `{q10_path.name}`")
    lines.append(f"- SNR grid: `{snr_list}`")
    lines.append(f"- Target pre-FEC BERs in Q10/Q11: `{key_bers}` (중에서 5e-2, 2e-2 집중)")
    lines.append("")
    lines.append("## 1. 요약 (Summary)")
    lines.append("")
    lines.append(
        f"- 세 채널(a/b/c) 모두에서 **BER ≈ 5×10⁻²** 기준으로 "
        f"ILC3_0c_gp는 PAM4 대비 평균 약 **{avg_5e2:.3f} dB**의 pre-FEC SNR 이득을 제공한다."
    )
    lines.append(
        f"- **BER ≈ 2×10⁻²**에서도 평균 ΔSNR은 약 **{avg_2e2:.3f} dB** 수준으로 유지되어, "
        "낮은 pre-FEC BER 영역에서도 guard-phase 이득이 안정적으로 유지된다."
    )
    lines.append(
        "- 이 ≈3 dB SNR 이득은 링크 버짓 관점에서 "
        "**동일 품질을 유지하면서 송신 전력을 약 1/2 수준으로 줄이거나**, "
        "**동일 전력에서 약 3 dB의 링크 마진을 추가 확보**하는 효과와 동치로 해석할 수 있다."
    )
    lines.append("")

    # 2. BER별 채널/ΔSNR/전력비 테이블
    lines.append("## 2. Target pre-FEC BER별 SNR 및 전력비 요약")
    lines.append("")
    for tb in key_bers:
        stats = per_ber_stats.get(tb, {})
        gains = stats.get("gains", [])
        if not gains:
            lines.append(f"### BER = {tb:.1e}")
            lines.append("")
            lines.append("- 해당 BER에서는 유효한 ΔSNR 포인트가 없습니다 (out of range).")
            lines.append("")
            continue

        lines.append(f"### BER = {tb:.1e}")
        lines.append("")
        lines.append("| 채널 | SNR_PAM4 [dB] | SNR_ILC3 [dB] | ΔSNR(PAM4-ILC3) [dB] | P_PAM4 / P_ILC3 |")
        lines.append("|:----:|:-------------:|:-------------:|:--------------------:|:---------------:|")

        for ch_name in ["a", "b", "c"]:
            ch = channels[ch_name]
            fec_list = ch["fec_margin"]
            item = find_fec_item_for_ber(fec_list, tb)
            if item is None:
                continue
            sp = item.get("snr_pam4")
            si = item.get("snr_ilc3")
            sg = item.get("snr_gain_db")
            if sp is None or si is None or sg is None:
                continue
            pr = power_ratio_from_gain_db(sg)
            lines.append(
                f"| {ch_name} | {sp:>7.3f} | {si:>7.3f} | {sg:>8.3f} | {pr:>7.3f}× |"
            )

        avg_gain = stats.get("avg_gain")
        min_gain = stats.get("min_gain")
        max_gain = stats.get("max_gain")
        if avg_gain is not None:
            pr_avg = power_ratio_from_gain_db(avg_gain)
            lines.append(
                f"| **avg** |  –  |  –  | **{avg_gain:>8.3f}** | **{pr_avg:>7.3f}×** |"
            )
        lines.append("")

    # 3. 채널별 링크 버짓 해석 (BER=5e-2 기준)
    lines.append("## 3. 채널별 링크 버짓 해석 (BER ≈ 5×10⁻² 기준)")
    lines.append("")
    lines.append(
        "Q11/Q12에서와 같이, BER ≈ 5×10⁻²는 전형적인 pre-FEC 설계 타깃 구간으로 보고, "
        "이 지점에서의 ΔSNR과 전력비를 채널별로 해석한다."
    )
    lines.append("")

    ch_labels = {
        "a": "a (mild ISI)",
        "b": "b (strong ISI)",
        "c": "c (medium ISI)",
    }

    for name in ["a", "b", "c"]:
        info = per_channel_5e2.get(name)
        if info is None:
            lines.append(f"- [Channel {name}] 해당 BER에서 유효한 데이터 없음.")
            continue
        sp = info["snr_pam4"]
        si = info["snr_ilc3"]
        sg = info["snr_gain_db"]
        pr = power_ratio_from_gain_db(sg)
        label = ch_labels.get(name, name)
        lines.append(
            f"- **[Channel {name}] {label}**: "
            f"SNR_PAM4 = {sp:.3f} dB, SNR_ILC3 = {si:.3f} dB, "
            f"ΔSNR ≈ {sg:.3f} dB → 전력비 P_PAM4 / P_ILC3 ≈ {pr:.3f}×"
        )
    lines.append("")

    # 4. 실무적 링크 버짓 관점 해석
    lines.append("## 4. 실무적 링크 버짓 관점 해석")
    lines.append("")
    lines.append(
        "- **송신 전력 절감 관점**: ΔSNR ≈ 3 dB는, 동일한 pre-FEC BER 타깃에서\n"
        "  PAM4 대비 **ILC3_0c_gp가 약 1/2 수준의 송신 전력으로 동등한 품질**을 달성할 수 있음을 의미한다."
    )
    lines.append(
        "- **링크 마진 관점**: 동일 송신 전력을 유지한다면, ILC3_0c_gp는 **채널 삽입손실을 약 3 dB 더 허용**하거나,\n"
        "  온도 상승, 제조 편차, aging 등에 대한 **여유 마진을 약 3 dB 확보**하는 효과를 제공한다."
    )
    lines.append(
        "- **ISI 세기와 무관한 상수 이득**: a/b/c 세 채널(약한/middle/강한 ISI) 모두에서 ΔSNR이 "
        "≈3 dB 주변으로 매우 좁게 몰려 있으므로,\n"
        "  guard-phase를 포함한 ILC3 구조가 **ISI 강도와 무관하게 안정적인 pre-FEC 이득**을 준다는 점을 보여준다."
    )
    lines.append(
        "- 결과적으로, 동일한 5-tap ISI 조건과 동일 FFE 조건에서 ILC3_0c_guard-phase를 적용하면,\n"
        "  표준 PAM4 대비 **약 3 dB의 FEC 전(pre-FEC) SNR 이득**을 얻을 수 있고,\n"
        "  이는 실질적으로 **전력 절감·채널 길이 증가·링크 신뢰도 향상**으로 바로 번역 가능하다."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_q13_fec_link_budget_story.py <q10_json_path>")
        sys.exit(1)

    in_path = Path(sys.argv[1]).expanduser().resolve()
    if not in_path.exists():
        print(f"[ERR] file not found: {in_path}")
        sys.exit(1)

    data = load_q10_json(in_path)

    snr_list = data["snr_list"]
    target_bers = data["target_bers"]
    channels = data["channels"]

    print("Q13: FEC link-budget story based on Q10/Q11/Q12 results")
    print(f"  q10_json   = {in_path}")
    print(f"  snr_list   = {snr_list}")
    print(f"  target_bers(available in Q10) = {target_bers}")
    print("")

    # Q13에서 집중할 타깃 BER
    key_bers = [5.0e-2, 2.0e-2]

    # ΔSNR 통계 저장용
    per_ber_stats: Dict[float, Dict[str, Any]] = {}
    # BER=5e-2에서 채널별 상세 정보 저장 (MD 섹션 3용)
    per_channel_5e2: Dict[str, Dict[str, float]] = {}

    # --- 타깃 BER별 상세 출력 및 ΔSNR 수집 ---
    for tb in key_bers:
        print(f"--- Target pre-FEC BER = {tb:.1e} ---")
        print("channel |  SNR_PAM4  SNR_ILC3   ΔSNR(PAM4-ILC3)   P_PAM4/P_ILC3")
        print("--------+------------------------------------------------------")

        gains: List[float] = []

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

            pr = power_ratio_from_gain_db(sg)
            gains.append(sg)

            print(
                f"   {name}    |"
                f" {fmt(sp):>9s} {fmt(si):>9s}   {fmt(sg):>9s} dB"
                f"   {fmt(pr):>9s}×"
            )

            if abs(tb - 5.0e-2) < 1e-12:
                per_channel_5e2[name] = {
                    "snr_pam4": float(sp),
                    "snr_ilc3": float(si),
                    "snr_gain_db": float(sg),
                }

        if gains:
            avg, g_min, g_max = summarize_gain(gains)
            per_ber_stats[tb] = {
                "gains": gains,
                "avg_gain": avg,
                "min_gain": g_min,
                "max_gain": g_max,
            }
        else:
            per_ber_stats[tb] = {"gains": []}

        print("")

    # --- ΔSNR 통계 요약 ---
    print("=== ΔSNR(PAM4-ILC3) statistics across channels ===")
    for tb in key_bers:
        stats = per_ber_stats.get(tb, {})
        gains = stats.get("gains", [])
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

    # --- 링크 버짓 관점 핵심 메시지 ---
    print("=== Link-budget oriented key messages (Q13) ===")
    stats_5e2 = per_ber_stats.get(5.0e-2, {})
    gains_5e2 = stats_5e2.get("gains", [])
    if gains_5e2:
        avg_5e2, _, _ = summarize_gain(gains_5e2)
        pr_5e2 = power_ratio_from_gain_db(avg_5e2)
        print(
            f"- Around BER ≈ 5e-2, ILC3_0c_gp provides ≈ {avg_5e2:.3f} dB SNR gain "
            f"over PAM4 across channels a/b/c, corresponding to a transmit power "
            f"ratio P_PAM4 / P_ILC3 ≈ {pr_5e2:.3f}× (≈ half power for ILC3)."
        )

    stats_2e2 = per_ber_stats.get(2.0e-2, {})
    gains_2e2 = stats_2e2.get("gains", [])
    if gains_2e2:
        avg_2e2, _, _ = summarize_gain(gains_2e2)
        pr_2e2 = power_ratio_from_gain_db(avg_2e2)
        print(
            f"- At BER ≈ 2e-2, the SNR gain remains close to ≈ {avg_2e2:.3f} dB "
            f"(P_PAM4 / P_ILC3 ≈ {pr_2e2:.3f}×), indicating a robust guard-phase "
            f"benefit in the lower pre-FEC BER region."
        )

    print(
        "- Practically, this ~3 dB pre-FEC SNR gain can be interpreted as either a "
        "similar-quality link at ~half transmit power, or a ~3 dB link-margin "
        "improvement at the same power, regardless of ISI severity (mild/strong/medium) "
        "for the tested 5-tap channels."
    )
    print("")

    # --- MD 파일 생성 ---
    md_text = build_md(
        q10_path=in_path,
        snr_list=snr_list,
        key_bers=key_bers,
        channels=channels,
        per_ber_stats=per_ber_stats,
        per_channel_5e2=per_channel_5e2,
    )

    out_dir = in_path.parent  # Q10 JSON과 같은 results 디렉터리
    md_path = out_dir / f"q13_fec_link_budget_story_from_{in_path.stem}.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md_text)

    print(f"[WRITE] {md_path}")


if __name__ == "__main__":
    main()