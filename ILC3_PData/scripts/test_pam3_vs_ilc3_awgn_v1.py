#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAM3 vs ILC3_0c_gp comparison on AWGN-only channel
2025-11-26

- Channel: h = [1.0] (no ISI, only AWGN)

Goal:
- Compare PAM3 and ILC3_0c_gp under the same AWGN (no ISI)
- Measure acc / ber vs SNR on clean channel

Notes:
- 심볼당 2-샘플 구조는 기존 abc 테스트와 동일:
  * PAM3: 0 -> [-1, -1], 1 -> [0, 0], 2 -> [+1, +1]
  * ILC3_0c_gp (0-code):
        0 -> [-1,  0]
        1 -> [ 0, -1]
        2 -> [+1,  0]
        3 -> [ 0, +1]
"""

import numpy as np
from pathlib import Path
from datetime import datetime


# AWGN-only 채널 (ISI 없음)
H_AWGN = np.array([1.0], dtype=float)


def pam3_gen_symbols(n_sym: int, rng: np.random.Generator) -> np.ndarray:
    """Generate PAM3 symbols in {0,1,2}."""
    return rng.integers(0, 3, size=n_sym, dtype=np.int64)


def pam3_encode(sym: np.ndarray) -> np.ndarray:
    """
    PAM3 심볼을 2-샘플 시퀀스로 변환.
    0 -> [-1, -1]
    1 -> [ 0,  0]
    2 -> [+1, +1]
    평균 심볼 에너지가 ILC3_0c_gp와 맞도록 레벨 스케일링(α=√(3/4)≈0.866)을 적용한다.
    """
    alpha = np.sqrt(3.0 / 4.0)  # ≈ 0.866025403...
    amp_lut = np.array([-alpha, 0.0, alpha], dtype=float)
    amp = amp_lut[sym]  # shape (N,)
    x = np.empty(sym.size * 2, dtype=float)
    x[0::2] = amp
    x[1::2] = amp
    return x


def pam3_decode(y: np.ndarray) -> np.ndarray:
    """
    2-샘플 평균을 내서 PAM3 심볼로 디코딩.
    임계값은 -0.5, +0.5 기준으로 3레벨 슬라이스.
    """
    y0 = y[0::2]
    y1 = y[1::2]
    m = 0.5 * (y0 + y1)

    sym_hat = np.zeros_like(m, dtype=np.int64)
    sym_hat[m > 0.5] = 2
    mid_mask = (m >= -0.5) & (m <= 0.5)
    sym_hat[mid_mask] = 1
    return sym_hat


def ilc3_gen_symbols(n_sym: int, rng: np.random.Generator) -> np.ndarray:
    """Generate ILC3_0c_gp symbols in {0,1,2,3}."""
    return rng.integers(0, 4, size=n_sym, dtype=np.int64)


def ilc3_encode(sym: np.ndarray) -> np.ndarray:
    """
    ILC3_0c_gp 0-code 매핑을 2-샘플 시퀀스로 변환.
    코드북:
        0 -> [-1,  0]
        1 -> [ 0, -1]
        2 -> [+1,  0]
        3 -> [ 0, +1]
    """
    codebook = np.array(
        [
            [-1.0, 0.0],
            [0.0, -1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=float,
    )
    x_pairs = codebook[sym]  # (N, 2)
    x = x_pairs.reshape(-1).astype(float)
    return x


def ilc3_decode(y: np.ndarray) -> np.ndarray:
    """
    ILC3_0c_gp 디코더 (메모리리스 2-샘플 유클리드 디코더).
    """
    y0 = y[0::2]
    y1 = y[1::2]
    v = np.stack([y0, y1], axis=1)  # (N, 2)

    codebook = np.array(
        [
            [-1.0, 0.0],
            [0.0, -1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=float,
    )

    diff = v[:, None, :] - codebook[None, :, :]
    d2 = np.sum(diff * diff, axis=2)
    sym_hat = np.argmin(d2, axis=1).astype(np.int64)
    return sym_hat


def apply_channel_awgn(
    x: np.ndarray,
    h: np.ndarray,
    snr_db: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    x → 채널(h) 컨볼루션 → AWGN 추가.
    여기서는 h = [1.0] 이므로 사실상 AWGN-only.
    SNR은 채널 출력 평균 전력 기준.
    """
    y = np.convolve(x, h, mode="same")
    sig_pow = np.mean(y * y)
    snr_linear = 10.0 ** (snr_db / 10.0)
    noise_pow = sig_pow / snr_linear
    noise_std = np.sqrt(noise_pow)
    noise = rng.normal(loc=0.0, scale=noise_std, size=y.shape)
    return y + noise


def run_scheme_awgn(
    scheme: str,
    h: np.ndarray,
    snr_db: float,
    n_sym: int,
    rng: np.random.Generator,
):
    """
    단일 스킴(PAM3 또는 ILC3_0c_gp)에 대해
    AWGN-only 채널에서 acc / ber 측정.
    """
    if scheme == "PAM3":
        gt_sym = pam3_gen_symbols(n_sym, rng)
        x = pam3_encode(gt_sym)
        y = apply_channel_awgn(x, h, snr_db, rng)
        dec_sym = pam3_decode(y)
    elif scheme == "ILC3_0c_gp":
        gt_sym = ilc3_gen_symbols(n_sym, rng)
        x = ilc3_encode(gt_sym)
        y = apply_channel_awgn(x, h, snr_db, rng)
        dec_sym = ilc3_decode(y)
    else:
        raise ValueError(f"Unknown scheme: {scheme}")

    assert dec_sym.shape == gt_sym.shape
    acc = float(np.mean(dec_sym == gt_sym))
    ber = 1.0 - acc
    return acc, ber


def prepare_results_path() -> Path:
    """
    ILC3_PData/results/ 아래에 timestamp를 포함한 CSV 파일 경로를 만든다.
    """
    this_file = Path(__file__).resolve()
    base_dir = this_file.parents[1]  # ILC3_PData/
    res_dir = base_dir / "results"
    res_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = res_dir / f"pam3_vs_ilc3_awgn_{ts}.csv"
    return out_path


def main():
    rng = np.random.default_rng(1234)

    n_sym = 50000
    snr_dbs = [10, 13, 16, 19, 22, 25]

    print("PAM3 vs ILC3_0c_gp on AWGN-only channel (h=[1.0])")
    print(f"N_sym = {n_sym}")
    print(f"h = {H_AWGN}")

    out_path = prepare_results_path()
    rows = []
    rows.append("scheme,channel,snr_db,acc,ber\n")

    ch_name = "awgn"
    h = H_AWGN

    for snr_db in snr_dbs:
        for scheme in ("PAM3", "ILC3_0c_gp"):
            acc, ber = run_scheme_awgn(
                scheme=scheme,
                h=h,
                snr_db=snr_db,
                n_sym=n_sym,
                rng=rng,
            )
            print(
                f"{scheme:9s}  ch={ch_name}  SNR={snr_db:4.1f} dB  "
                f"acc={acc:.6f}  ber={ber:.6f}"
            )
            rows.append(
                f"{scheme},{ch_name},{snr_db:.2f},{acc:.6f},{ber:.6f}\n"
            )

    with out_path.open("w", encoding="utf-8") as f:
        for line in rows:
            f.write(line)

    print(f"\n[WRITE] {out_path}")


if __name__ == "__main__":
    main()