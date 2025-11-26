#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_pam3_vs_ilc3_b_ffe_dfe_v1.py

채널 b (h = [0.05, 0.5, 1.0, 0.5, 0.05]) 에서
PAM3 vs ILC3_0c_gp 에 대해

    - AWGN + ISI (channel b)
    - FFE (LS + ridge)
    - FFE + DFE (채널 기반 postcursor 캔슬)

구조를 비교하는 스크립트.

출력:
- 터미널에 SNR별 성능 로그
- results/ 디렉터리에 CSV 저장
"""

import numpy as np
from pathlib import Path
from datetime import datetime
import csv


# ======================================================================
# 기본 설정
# ======================================================================

N_SYM = 50_000

# 채널 b: 가장 ISI가 강한 채널
H_B = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=float)

# 테스트할 SNR 목록 (dB)
SNR_LIST = [16.0, 19.0, 22.0, 25.0]

# FFE 길이 (채널 b에서 fairness sweep 결과 기반 가이드)
L_FFE_PAM3 = 15   # PAM3 쪽 FFE 길이
L_FFE_ILC3 = 5    # ILC3 쪽 FFE 길이 (짧은 구조로도 충분하다고 가정)

# DFE 길이 (채널 b: postcursor가 2탭이므로 2 또는 3 정도면 충분)
L_DFE = 2

# FFE ridge 계수 (fairness sweep에서 잘 먹던 수준 기준)
RIDGE = 1e-5

# 난수 시드
SEED = 1234

# 결과 저장 디렉터리
ROOT_DIR = Path(__file__).resolve().parent.parent
RES_DIR = ROOT_DIR / "results"
RES_DIR.mkdir(parents=True, exist_ok=True)


# ======================================================================
# PAM3 / ILC3 모듈레이션 & 슬라이서
# ======================================================================

def gen_ternary_indices(rng: np.random.Generator, n: int) -> np.ndarray:
    """0,1,2 3-ary 인덱스를 균일하게 생성."""
    return rng.integers(0, 3, size=n, dtype=int)


def modulate_pam3(idx: np.ndarray) -> np.ndarray:
    """PAM3: {0,1,2} -> {-1, 0, +1}"""
    levels = np.array([-1.0, 0.0, +1.0], dtype=float)
    return levels[idx]


def slice_pam3_vec(x: np.ndarray):
    """PAM3 벡터 슬라이서: 실수 -> {-1,0,1} + 인덱스(0,1,2)."""
    levels = np.array([-1.0, 0.0, +1.0], dtype=float)
    diff2 = (x[:, None] - levels[None, :]) ** 2
    idx_hat = np.argmin(diff2, axis=1)
    sym_hat = levels[idx_hat]
    return idx_hat, sym_hat


def slice_pam3_scalar(x: float):
    """PAM3 스칼라 슬라이서 (DFE에서 사용)."""
    levels = np.array([-1.0, 0.0, +1.0], dtype=float)
    diff2 = (x - levels) ** 2
    k = int(np.argmin(diff2))
    return k, float(levels[k])


# ----- 단순화된 ILC3_0c_gp 모델 -------------------------------------
# 주의: 여기서는 1D 실수 채널 상에서의 "강화된" 3레벨로 단순 모델링한다.
# 실제 네가 쓰던 ILC3_0c_gp 정의가 따로 있다면,
# 아래 세 함수(modulate_ilc3_0c_gp, slice_ilc3_0c_gp_vec, slice_ilc3_0c_gp_scalar)를
# 그 코드로 교체해서 사용하면 된다.

def modulate_ilc3_0c_gp(idx: np.ndarray) -> np.ndarray:
    """
    단순화된 ILC3_0c_gp 모듈레이션.

    - 평균 전력은 PAM3와 비슷하게 맞추고,
    - 레벨 간 거리는 약간 더 떨어지도록 스케일링.

    여기서는 예시로 {-1.2, 0.0, +1.2} 사용.
    """
    levels = np.array([-1.2, 0.0, +1.2], dtype=float)
    return levels[idx]


def slice_ilc3_0c_gp_vec(x: np.ndarray):
    """단순화된 ILC3 벡터 슬라이서."""
    levels = np.array([-1.2, 0.0, +1.2], dtype=float)
    diff2 = (x[:, None] - levels[None, :]) ** 2
    idx_hat = np.argmin(diff2, axis=1)
    sym_hat = levels[idx_hat]
    return idx_hat, sym_hat


def slice_ilc3_0c_gp_scalar(x: float):
    """단순화된 ILC3 스칼라 슬라이서 (DFE에서 사용)."""
    levels = np.array([-1.2, 0.0, +1.2], dtype=float)
    diff2 = (x - levels) ** 2
    k = int(np.argmin(diff2))
    return k, float(levels[k])


# ======================================================================
# 채널 + 노이즈
# ======================================================================

def apply_isi_channel(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """선형 ISI 채널 (convolution, same length)."""
    y = np.convolve(x, h, mode="same")
    return y


def add_awgn(y: np.ndarray, snr_db: float, x_ref: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    AWGN 추가.
    SNR(dB) = 10 * log10(Es / N0), 여기서는 현실적으로
    SNR = Es / sigma^2 로 두고 sigma 계산.
    """
    es = np.mean(np.abs(x_ref) ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    sigma2 = es / snr_lin
    sigma = np.sqrt(sigma2)
    noise = sigma * rng.standard_normal(size=y.shape)
    return y + noise


# ======================================================================
# FFE LS 설계 (1D, ridge 포함)
# ======================================================================

def build_ffe_regressor(y: np.ndarray, L_ffe: int):
    """
    FFE 설계용 regressor matrix R 생성.
    - R.shape = (N_eff, L_ffe)
    - 각 row R[n,:] = y[n : n+L_ffe]
    - decision delay D = L_ffe // 2
    """
    L = L_ffe
    D = L // 2
    N = len(y) - L + 1
    if N <= 0:
        raise ValueError("signal length too short for FFE length")

    R = np.empty((N, L), dtype=float)
    for n in range(N):
        R[n, :] = y[n:n + L]
    return R, D


def design_ffe_ls(R: np.ndarray, x_tgt: np.ndarray, ridge: float) -> np.ndarray:
    """
    R @ w ≈ x_tgt 를 최소제곱으로 푸는 FFE 설계.
    - ridge: Tikhonov regularization 계수
    """
    # 길이 확인
    N, L = R.shape
    if len(x_tgt) != N:
        raise ValueError("x_tgt length must match R rows")

    RtR = R.T @ R
    Rtx = R.T @ x_tgt

    base = np.trace(RtR) / float(L)
    lam = ridge * base + 1e-8

    A = RtR + lam * np.eye(L, dtype=float)

    try:
        w = np.linalg.solve(A, Rtx)
    except np.linalg.LinAlgError:
        # fallback: lstsq
        w, *_ = np.linalg.lstsq(R, x_tgt, rcond=None)

    # NaN / inf 방지
    if not np.all(np.isfinite(w)):
        w = np.nan_to_num(w, nan=0.0, posinf=0.0, neginf=0.0)

    return w


# ======================================================================
# DFE 설계 및 적용
# ======================================================================

def design_dfe_from_channel(h: np.ndarray, L_dfe: int) -> np.ndarray:
    """
    채널 impulse response h 에서 post-cursor 부분을 기반으로
    간단한 DFE tap 설계.

    - 여기서는 중심 tap을 h의 최대값 인덱스로 보고,
      그 뒤쪽 tap들을 post-cursor로 사용.
    """
    center = int(np.argmax(np.abs(h)))
    post = h[center + 1:]
    if len(post) <= 0:
        return np.zeros(L_dfe, dtype=float)

    # 필요한 길이만큼 잘라서 사용
    taps = np.zeros(L_dfe, dtype=float)
    m = min(L_dfe, len(post))
    taps[:m] = post[:m] / (h[center] + 1e-8)
    return taps


def apply_dfe(eq_out: np.ndarray,
              mod: str,
              dfe_taps: np.ndarray):
    """
    eq_out: FFE 출력 (길이 N_eff)
    mod: "pam3" 또는 "ilc3"
    dfe_taps: 길이 L_dfe

    리턴:
        idx_hat (N_eff,), sym_hat (N_eff,)
    """
    N = len(eq_out)
    L_dfe = len(dfe_taps)

    idx_hat = np.zeros(N, dtype=int)
    sym_hat = np.zeros(N, dtype=float)

    for n in range(N):
        # feedback ISI 추정
        fb = 0.0
        max_j = min(L_dfe, n)
        for j in range(max_j):
            fb += dfe_taps[j] * sym_hat[n - 1 - j]

        y_can = eq_out[n] - fb

        if mod == "pam3":
            k, s = slice_pam3_scalar(y_can)
        else:
            k, s = slice_ilc3_0c_gp_scalar(y_can)

        idx_hat[n] = k
        sym_hat[n] = s

    return idx_hat, sym_hat


# ======================================================================
# 시뮬레이션 본체
# ======================================================================

def simulate_for_mod(mod: str,
                     snr_db: float,
                     rng: np.random.Generator):
    """
    단일 모듈레이션(PAM3 or ILC3)에 대해
    채널 b + FFE + (옵션)DFE 성능 측정.

    리턴:
        dict with keys:
            "snr_db", "acc_ffe", "ber_ffe",
            "acc_ffedfe", "ber_ffedfe"
    """
    # 공통 3-ary 데이터 (fairness용)
    idx = gen_ternary_indices(rng, N_SYM)

    if mod == "pam3":
        x = modulate_pam3(idx)
        L_ffe = L_FFE_PAM3
    else:
        x = modulate_ilc3_0c_gp(idx)
        L_ffe = L_FFE_ILC3

    # 채널 + 노이즈
    y_isi = apply_isi_channel(x, H_B)
    y = add_awgn(y_isi, snr_db, x, rng)

    # FFE 설계
    R, D = build_ffe_regressor(y, L_ffe)
    # target 심볼 (중앙 정렬)
    x_eff = x[D:D + R.shape[0]]

    w_ffe = design_ffe_ls(R, x_eff, ridge=RIDGE)
    eq_out = R @ w_ffe

    # FFE-only slicing
    if mod == "pam3":
        idx_hat_ffe, _ = slice_pam3_vec(eq_out)
    else:
        idx_hat_ffe, _ = slice_ilc3_0c_gp_vec(eq_out)

    idx_eff = idx[D:D + len(eq_out)]
    acc_ffe = float(np.mean(idx_hat_ffe == idx_eff))
    ber_ffe = 1.0 - acc_ffe

    # FFE + DFE
    dfe_taps = design_dfe_from_channel(H_B, L_DFE)
    idx_hat_dfe, _ = apply_dfe(eq_out, mod=mod, dfe_taps=dfe_taps)

    acc_ffedfe = float(np.mean(idx_hat_dfe == idx_eff))
    ber_ffedfe = 1.0 - acc_ffedfe

    return {
        "snr_db": snr_db,
        "acc_ffe": acc_ffe,
        "ber_ffe": ber_ffe,
        "acc_ffedfe": acc_ffedfe,
        "ber_ffedfe": ber_ffedfe,
    }


def main():
    rng = np.random.default_rng(SEED)

    print("PAM3 vs ILC3_0c_gp on channel b (AWGN+ISI + FFE + DFE)")
    print(f"N_sym = {N_SYM}")
    print(f"h_b   = {H_B.tolist()}")
    print(f"SNR list = {SNR_LIST}")
    print(f"FFE lengths: PAM3 L={L_FFE_PAM3}, ILC3 L={L_FFE_ILC3}, ridge={RIDGE}")
    print(f"DFE length: L_dfe={L_DFE}")
    print()

    results_pam3 = []
    results_ilc3 = []

    for snr_db in SNR_LIST:
        print(f"=== SNR = {snr_db:.1f} dB ===")

        res_p = simulate_for_mod("pam3", snr_db, rng)
        res_i = simulate_for_mod("ilc3", snr_db, rng)

        results_pam3.append(res_p)
        results_ilc3.append(res_i)

        print(
            "PAM3       ch=b  "
            f"SNR={snr_db:4.1f} dB  "
            f"FFE_acc={res_p['acc_ffe']:.6f} FFE_ber={res_p['ber_ffe']:.6f}  "
            f"FFE+DFE_acc={res_p['acc_ffedfe']:.6f} FFE+DFE_ber={res_p['ber_ffedfe']:.6f}"
        )
        print(
            "ILC3_0c_gp ch=b  "
            f"SNR={snr_db:4.1f} dB  "
            f"FFE_acc={res_i['acc_ffe']:.6f} FFE_ber={res_i['ber_ffe']:.6f}  "
            f"FFE+DFE_acc={res_i['acc_ffedfe']:.6f} FFE+DFE_ber={res_i['ber_ffedfe']:.6f}"
        )
        print()

    # CSV 저장
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = RES_DIR / f"pam3_vs_ilc3_b_ffe_dfe_{ts}.csv"

    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mod", "snr_db",
            "acc_ffe", "ber_ffe",
            "acc_ffedfe", "ber_ffedfe",
        ])
        for res in results_pam3:
            writer.writerow([
                "PAM3",
                res["snr_db"],
                res["acc_ffe"],
                res["ber_ffe"],
                res["acc_ffedfe"],
                res["ber_ffedfe"],
            ])
        for res in results_ilc3:
            writer.writerow([
                "ILC3_0c_gp",
                res["snr_db"],
                res["acc_ffe"],
                res["ber_ffe"],
                res["acc_ffedfe"],
                res["ber_ffedfe"],
            ])

    print(f"[WRITE] CSV -> {csv_path}")


if __name__ == "__main__":
    main()