#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q10: Channels a/b/c – PAM4 vs ILC3_0c_gp, FFE-only SNR curves + FEC margin summary

- 채널 a/b/c 공통 환경에서:
    * PAM4 + FFE
    * ILC3_0c_gp + FFE  (진폭 3-PAM, guard phase는 포함하지 않은 기본 성능)

- 각 채널에 대해 SNR sweep을 돌려 acc/ber를 얻고,
  몇 개의 타깃 pre-FEC BER에 대해
    "같은 BER을 만족하는 데 필요한 SNR_dB"
  를 PAM4 vs ILC3로 각각 추정한 뒤,
    SNR_gain_dB = SNR_PAM4 - SNR_ILC3
  를 계산한다.

출력:
    1) 콘솔: 채널별, 타깃 BER별 SNR 및 gain 요약
    2) JSON: results/q10_all_channels_fec_margin_ffe_only_YYYY-MM-DD_HH-MM-SS.json
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np

# ---------------------------
# 채널 / 코드북 / 파라미터
# ---------------------------

H_A = np.array([0.10, 0.40, 1.00, 0.40, 0.10], dtype=float)
H_B = np.array([0.05, 0.50, 1.00, 0.50, 0.05], dtype=float)
H_C = np.array([0.075, 0.45, 1.00, 0.45, 0.075], dtype=float)

PAM4_LEVELS = np.array([-3.0, -1.0, +1.0, +3.0], dtype=float)
ILC3_LEVELS = np.array([-1.0, 0.0, +1.0], dtype=float)

N_SYM = 200_000
SNR_LIST = [4.0, 6.0, 8.0, 10.0, 12.0, 14.0]

FFE_LEN = 11
FFE_RIDGE = 0.001

# pre-FEC 관점에서 의미 있는 타깃 BER들
TARGET_BERS = [0.20, 0.10, 0.05, 0.02, 0.01]


# ---------------------------
# 유틸 함수들
# ---------------------------

def design_ffe_mmse(h: np.ndarray, length: int, ridge: float = 0.0) -> np.ndarray:
    """
    T-spaced MMSE FFE 설계 (실수 채널 기준)
    h: 채널 임펄스 응답 (1D)
    length: FFE tap 길이 (홀수 권장)
    ridge: ridge regularization (λI)
    """
    h = np.asarray(h, dtype=float)
    L = length
    conv_len = len(h) + L - 1

    # convolution matrix A
    A = np.zeros((conv_len, L), dtype=float)
    for i in range(conv_len):
        for k in range(L):
            j = i - k
            if 0 <= j < len(h):
                A[i, k] = h[j]

    # desired response: 중앙에서 1, 나머지는 0 (Nyquist-like)
    d = np.zeros(conv_len, dtype=float)
    center_idx = conv_len // 2
    d[center_idx] = 1.0

    ATA = A.T @ A
    if ridge > 0:
        ATA += ridge * np.eye(L)
    ATd = A.T @ d
    w = np.linalg.solve(ATA, ATd)
    return w


def add_awgn(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """
    Es/N0 기반 실수 AWGN 추가.
    각 스킴별 Es(=E[x^2])를 이용해 같은 SNR_dB 조건 보장.
    """
    x = np.asarray(x, dtype=float)
    Es = np.mean(x ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_var = Es / snr_lin
    noise = rng.normal(scale=np.sqrt(noise_var), size=x.shape)
    return x + noise


def pam4_hard_decision(y: np.ndarray) -> np.ndarray:
    """PAM4: 최인접 레벨 slicing."""
    y = np.asarray(y, dtype=float)
    idx = np.argmin(np.abs(y[:, None] - PAM4_LEVELS[None, :]), axis=1)
    return idx


def ilc3_hard_decision(y: np.ndarray) -> np.ndarray:
    """ILC3_0c_gp: 진폭 기준 3-PAM slicing."""
    y = np.asarray(y, dtype=float)
    idx = np.argmin(np.abs(y[:, None] - ILC3_LEVELS[None, :]), axis=1)
    return idx


def pam4_generate_symbols(n: int, rng: np.random.Generator):
    idx = rng.integers(low=0, high=4, size=n)
    x = PAM4_LEVELS[idx]
    return idx, x


def ilc3_generate_symbols(n: int, rng: np.random.Generator):
    idx = rng.integers(low=0, high=3, size=n)
    x = ILC3_LEVELS[idx]
    return idx, x


def apply_channel_and_ffe(x: np.ndarray, h: np.ndarray, w_ffe: np.ndarray) -> np.ndarray:
    """
    x -> 채널 h -> FFE w_ffe 까지 통과한 후의 시퀀스 (same 길이로 잘라줌)
    """
    y_ch = np.convolve(x, h, mode="same")
    y_eq = np.convolve(y_ch, w_ffe, mode="same")
    return y_eq


def run_scheme(
    scheme: str,
    h: np.ndarray,
    w_ffe: np.ndarray,
    snr_db: float,
    n_sym: int,
    rng: np.random.Generator,
):
    """
    scheme: "PAM4" or "ILC3"
    """
    if scheme == "PAM4":
        gt_idx, x = pam4_generate_symbols(n_sym, rng)
        y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
        y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
        dec_idx = pam4_hard_decision(y_eq)
    elif scheme == "ILC3":
        gt_idx, x = ilc3_generate_symbols(n_sym, rng)
        y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
        y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
        dec_idx = ilc3_hard_decision(y_eq)
    else:
        raise ValueError(f"Unknown scheme: {scheme}")

    acc = float(np.mean(dec_idx == gt_idx))
    ber = 1.0 - acc
    return acc, ber


def interp_snr_for_target_ber(snr_list, ber_list, target_ber):
    """
    단조 감소하는 ber(snr)에 대해, ber ~= target_ber 가 되는 SNR_dB를
    1D 선형 보간으로 추정.
    범위를 벗어나면 None 리턴.
    """
    snr = np.asarray(snr_list, dtype=float)
    ber = np.asarray(ber_list, dtype=float)

    # high BER -> low SNR, low BER -> high SNR 이라 가정 (일반적인 모양)
    # target_ber 보다 큰 구간과 작은 구간이 모두 있어야 crossing 이 존재.
    for i in range(len(snr) - 1):
        b0, b1 = ber[i], ber[i + 1]
        if (b0 >= target_ber and b1 <= target_ber) or (b0 <= target_ber and b1 >= target_ber):
            # 선형 보간
            s0, s1 = snr[i], snr[i + 1]
            if b1 == b0:
                return float(s0)  # flat 구간이면 아무거나
            t = (target_ber - b0) / (b1 - b0)
            s_target = s0 + t * (s1 - s0)
            return float(s_target)

    # crossing이 없는 경우 (항상 위/아래 한쪽에만 있는 경우)
    return None


# ---------------------------
# 메인 루프
# ---------------------------

def main():
    rng = np.random.default_rng(1234)

    channels = {
        "a": H_A,
        "b": H_B,
        "c": H_C,
    }

    print("Q10: Channels a/b/c – PAM4 vs ILC3_0c_gp, FFE-only SNR curves + FEC margin")
    print(f"N_sym   = {N_SYM}")
    print(f"SNR_dB  = {SNR_LIST}")
    print(f"FFE_LEN = {FFE_LEN}, FFE_RIDGE = {FFE_RIDGE}")
    print(f"Target pre-FEC BERs = {TARGET_BERS}")
    print("")

    all_results = {
        "n_sym": int(N_SYM),
        "snr_list": [float(s) for s in SNR_LIST],
        "ffe_len": int(FFE_LEN),
        "ffe_ridge": float(FFE_RIDGE),
        "target_bers": [float(b) for b in TARGET_BERS],
        "channels": {},
    }

    for name, h in channels.items():
        print(f"--- Channel {name}: h = {h.tolist()} ---")
        w_ffe = design_ffe_mmse(h, length=FFE_LEN, ridge=FFE_RIDGE)
        print("[FFE DESIGN] w_ffe:", w_ffe)
        print("")

        snr_vals = []
        pam4_accs, pam4_bers = [], []
        ilc3_accs, ilc3_bers = [], []

        for snr_db in SNR_LIST:
            snr_vals.append(float(snr_db))

            pam4_acc, pam4_ber = run_scheme(
                scheme="PAM4",
                h=h,
                w_ffe=w_ffe,
                snr_db=snr_db,
                n_sym=N_SYM,
                rng=rng,
            )
            ilc3_acc, ilc3_ber = run_scheme(
                scheme="ILC3",
                h=h,
                w_ffe=w_ffe,
                snr_db=snr_db,
                n_sym=N_SYM,
                rng=rng,
            )

            pam4_accs.append(pam4_acc)
            pam4_bers.append(pam4_ber)
            ilc3_accs.append(ilc3_acc)
            ilc3_bers.append(ilc3_ber)

            print(
                f"SNR={snr_db:4.1f} dB | "
                f"PAM4 acc={pam4_acc:.6f} ber={pam4_ber:.6f} | "
                f"ILC3 acc={ilc3_acc:.6f} ber={ilc3_ber:.6f}"
            )

        print("")
        # 타깃 BER 기준 SNR point & margin 계산
        fec_summary = []
        print(f"[Channel {name}] FEC-oriented SNR points (same pre-FEC BER):")
        print("target_ber |  SNR_PAM4  SNR_ILC3  (PAM4-ILC3)")

        for tb in TARGET_BERS:
            s_pam4 = interp_snr_for_target_ber(snr_vals, pam4_bers, tb)
            s_ilc3 = interp_snr_for_target_ber(snr_vals, ilc3_bers, tb)
            if s_pam4 is None or s_ilc3 is None:
                gain = None
            else:
                gain = s_pam4 - s_ilc3

            if gain is None:
                print(f"{tb:9.3e} |  (out of range)")
            else:
                print(f"{tb:9.3e} |  {s_pam4:7.3f}   {s_ilc3:7.3f}    {gain:7.3f} dB")

            fec_summary.append(
                {
                    "target_ber": float(tb),
                    "snr_pam4": None if s_pam4 is None else float(s_pam4),
                    "snr_ilc3": None if s_ilc3 is None else float(s_ilc3),
                    "snr_gain_db": None if gain is None else float(gain),
                }
            )

        print("")

        all_results["channels"][name] = {
            "h": h.tolist(),
            "snr": snr_vals,
            "pam4": {
                "acc": pam4_accs,
                "ber": pam4_bers,
            },
            "ilc3_0c_gp": {
                "acc": ilc3_accs,
                "ber": ilc3_bers,
            },
            "fec_margin": fec_summary,
        }

    # JSON 저장
    base_dir = Path(__file__).resolve().parents[1] / "results"
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = base_dir / f"q10_all_channels_fec_margin_ffe_only_{ts}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"[WRITE] {out_path}")


if __name__ == "__main__":
    main()