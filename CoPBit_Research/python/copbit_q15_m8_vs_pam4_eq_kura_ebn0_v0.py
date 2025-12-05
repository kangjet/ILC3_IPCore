#!/usr/bin/env python3
"""
CoPBit Q15 – M8 vs PAM4 (Channel-b + FFE + Kuramoto) BER vs Eb/N0 v0

- 채널: mid-ISI channel-a/b/c (5-tap) 또는 awgn (no-ISI, h=[1])
- 스킴:
    * PAM4 + FFE (baseline)
    * M8 (8-PSK) + FFE (baseline)
    * M8 (8-PSK) + FFE + decision-directed phase tracking (Kuramoto-style 1-lane 근사)
- 출력: Eb/N0 별 BER 비교 테이블
"""

import argparse
import numpy as np


# ---------------------------------------------------------------------
# 기본 유틸
# ---------------------------------------------------------------------
def set_seed(seed: int):
    if seed is not None:
        np.random.seed(seed)


def parse_ebn0_list(s: str):
    return [float(x) for x in s.split(",") if x.strip()]


# ---------------------------------------------------------------------
# 채널 / 노이즈
# ---------------------------------------------------------------------
def get_channel_taps(chan: str):
    """
    mid-ISI 채널 a/b/c 탭 정의 + awgn (no-ISI).
    (ILC 실험에서 쓰던 것과 동일한 형태)
    """
    chan = chan.lower()

    if chan == "awgn":
        # ISI 없는 기준 채널 (sanity check 용)
        h = np.array([1.0], dtype=float)

    elif chan == "a":
        # 가장 깨끗한 채널
        h = np.array([0.10, 0.40, 1.0, 0.40, 0.10], dtype=float)

    elif chan == "b":
        # 가장 강한(mild ISI보다 세게) 채널
        h = np.array([0.05, 0.50, 1.0, 0.50, 0.05], dtype=float)

    elif chan == "c":
        # 중간 채널
        h = np.array([0.075, 0.45, 1.0, 0.45, 0.075], dtype=float)

    else:
        raise ValueError(f"Unknown channel '{chan}' (use 'awgn'/'a'/'b'/'c')")

    # 에너지 정규화 (awgn의 경우에도 Es=1 그대로 유지)
    h = h / np.sqrt(np.sum(h ** 2))
    return h


def apply_channel(x, h):
    """
    선형 채널 컨볼루션 (same 길이).
    """
    y = np.convolve(x, h, mode="same")
    return y


def add_awgn_ebn0(x, ebn0_db, bits_per_sym):
    """
    Eb/N0 기준 AWGN 추가 (complex baseband).
    x 평균 에너지(Es)를 기준으로 N0 계산.
    """
    ebn0_linear = 10.0 ** (ebn0_db / 10.0)
    Es = np.mean(np.abs(x) ** 2)
    N0 = Es / (ebn0_linear * bits_per_sym)
    noise_var = N0  # complex baseband에서 variance = N0
    noise = np.sqrt(noise_var / 2.0) * (
        np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape)
    )
    return x + noise


# ---------------------------------------------------------------------
# Modem: PAM4 / M8
# ---------------------------------------------------------------------
def bits_to_int(bits, k):
    """bit array -> 0..(2^k-1) int 배열"""
    bits = bits.reshape(-1, k)
    vals = np.zeros(bits.shape[0], dtype=int)
    for i in range(k):
        vals = (vals << 1) | bits[:, i]
    return vals


def int_to_bits(vals, k):
    N = vals.shape[0]
    bits = np.zeros((N, k), dtype=int)
    for i in range(k):
        bits[:, k - 1 - i] = (vals >> i) & 1
    return bits.reshape(-1)


# PAM4: Gray mapping, levels = [-3,-1,+1,+3] / sqrt(5) (Es=1)
def pam4_mod(bits):
    assert bits.size % 2 == 0
    idx = bits_to_int(bits, 2)
    # Gray mapping: 00->-3, 01->-1, 11->+1, 10->+3
    mapping = np.array([-3.0, -1.0, +3.0, +1.0], dtype=float)
    sym = mapping[idx]
    # 에너지 정규화
    Es = np.mean(sym ** 2)
    sym = sym / np.sqrt(Es)
    return sym.astype(np.complex128)  # 편의상 complex 로 처리


def pam4_slicer(y):
    y_real = np.real(y)
    # 동일한 레벨/정규화 사용
    base_levels = np.array([-3.0, -1.0, +3.0, +1.0], dtype=float)
    Es = np.mean(base_levels ** 2)
    levels = base_levels / np.sqrt(Es)
    idx = np.argmin(np.abs(y_real[:, None] - levels[None, :]), axis=1)
    dec_sym = levels[idx]
    return dec_sym.astype(np.complex128), idx


# M8: 8-PSK (unit circle, Es=1), Gray mapping 대충 사용 (순서만 중요)
def m8_mod(bits):
    assert bits.size % 3 == 0
    idx = bits_to_int(bits, 3)  # 0..7
    # 각도: 2πk/8
    k = idx
    ang = 2.0 * np.pi * k / 8.0
    sym = np.exp(1j * ang)
    # 이미 unit circle 이라 Es=1
    return sym


def m8_slicer(y):
    ang = np.angle(y)
    # 8 등분
    k = np.round((ang * 8.0) / (2.0 * np.pi)) % 8
    k = np.nan_to_num(k, nan=0.0, posinf=0.0, neginf=0.0)
    k = k.astype(int)
    dec_sym = np.exp(1j * (2.0 * np.pi * k / 8.0))
    return dec_sym, k


# ---------------------------------------------------------------------
# FFE (LMS) – complex 공용
# ---------------------------------------------------------------------
def train_ffe_lms(rx, tx_sym, ffe_len, mu_ffe, train_frac):
    """
    rx: 채널 출력 (complex)
    tx_sym: 이상적인 심볼 (complex)
    ffe_len: 탭 길이
    mu_ffe: LMS step
    train_frac: 0~1, 학습에 사용하는 앞부분 비율
    """
    N = len(tx_sym)
    assert len(rx) == N

    n_train = int(N * train_frac)
    if n_train < ffe_len + 1:
        raise ValueError("train_frac 너무 작아서 FFE 학습길이가 부족함")

    w = np.zeros(ffe_len, dtype=np.complex128)
    # 중심 탭 1.0 초기화 (대략적인 delay 보상)
    w[ffe_len // 2] = 1.0 + 0j

    # LMS 학습
    for n in range(ffe_len - 1, n_train):
        u = rx[n - ffe_len + 1 : n + 1]  # 길이 = ffe_len
        y_hat = np.vdot(w, u)  # w^H u
        e = tx_sym[n] - y_hat
        w = w + mu_ffe * e * np.conjugate(u)

    return w


def apply_ffe(rx, w):
    """
    rx: complex, 길이 N
    w: complex, 길이 L
    """
    N = len(rx)
    L = len(w)
    y = np.zeros(N, dtype=np.complex128)
    for n in range(L - 1, N):
        u = rx[n - L + 1 : n + 1]
        y[n] = np.vdot(w, u)
    return y


# ---------------------------------------------------------------------
# Kuramoto-style phase tracker (1-lane 근사)
# ---------------------------------------------------------------------
def apply_kuramoto_phase_tracker(y_eq, mu_phase):
    """
    y_eq: FFE 결과 (complex)
    mu_phase: 위상 업데이트 스텝 (rad-scale gain)

    phi_k 를 하나 두고, decision-directed 방식으로 위상 보정.
    """
    N = len(y_eq)
    z = np.zeros(N, dtype=np.complex128)
    phi = 0.0

    for n in range(N):
        z_n = y_eq[n] * np.exp(-1j * phi)
        z[n] = z_n
        d_n, _ = m8_slicer(z_n)
        # d_n * z_n* = |d||z| e^{j(θ_d - θ_z)} = error phasor
        err_phasor = d_n * np.conjugate(z_n)
        dphi = np.angle(err_phasor)
        # ★ 여기 부호 수정: 안정 루프를 위해 음수 방향으로 업데이트
        phi -= mu_phase * dphi

    return z


# ---------------------------------------------------------------------
# BER 계산
# ---------------------------------------------------------------------
def ber_from_indices(gt_idx, dec_idx):
    assert gt_idx.shape == dec_idx.shape
    return np.mean(gt_idx != dec_idx)


# ---------------------------------------------------------------------
# 메인 실험 루틴
# ---------------------------------------------------------------------
def run_q15(
    n_sym: int,
    ebn0_list,
    chan: str,
    ffe_len: int,
    train_frac: float,
    mu_ffe: float,
    mu_phase: float,
    seed: int,
):
    set_seed(seed)
    h = get_channel_taps(chan)

    print("=== CoPBit Q15 – M8 vs PAM4 (Channel-{0}, FFE + Kuramoto) BER vs Eb/N0 v0 ===".format(chan))
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] channel        = {chan} (taps = {h.tolist()})")
    print(f"[Param] ffe_len        = {ffe_len}")
    print(f"[Param] train_frac     = {train_frac}")
    print(f"[Param] mu_ffe         = {mu_ffe}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] seed           = {seed}")
    print()

    # 공통 비트 생성
    # PAM4: 2 bit/sym, M8: 3 bit/sym
    bits_pam4 = np.random.randint(0, 2, size=2 * n_sym, dtype=int)
    bits_m8 = np.random.randint(0, 2, size=3 * n_sym, dtype=int)

    # 모듈레이션
    s_pam4 = pam4_mod(bits_pam4)  # complex (실수부만 의미)
    s_m8 = m8_mod(bits_m8)        # complex

    # 채널 적용 (노이즈 없는 채널 출력)
    x_pam4_chan = apply_channel(s_pam4, h)
    x_m8_chan = apply_channel(s_m8, h)

    # 노이즈 없는 채널 출력으로 FFE 한 번만 학습
    w_pam4 = train_ffe_lms(
        x_pam4_chan,
        s_pam4,
        ffe_len=ffe_len,
        mu_ffe=mu_ffe,
        train_frac=train_frac,
    )
    w_m8 = train_ffe_lms(
        x_m8_chan,
        s_m8,
        ffe_len=ffe_len,
        mu_ffe=mu_ffe,
        train_frac=train_frac,
    )

    print("[INFO] Channel-{0} FFE 설계 (PAM4, M8 각각 학습)".format(chan))
    print()

    print("===============================================================")
    print(" Eb/N0_dB |  BER_PAM4_FFE  |  BER_M8_FFE  |  BER_M8_FFE+Kura ")
    print("---------------------------------------------------------------")

    for eb in ebn0_list:
        # --- PAM4 branch (노이즈만 Eb/N0별로 추가, FFE는 고정) ---
        y_pam4 = add_awgn_ebn0(x_pam4_chan, eb, bits_per_sym=2)
        y_pam4_eq = apply_ffe(y_pam4, w_pam4)

        # 유효 구간 (FFE 탭 길이만큼 앞쪽 제거)
        valid_start = ffe_len - 1
        gt_pam4 = s_pam4[valid_start:]
        y_pam4_eq_valid = y_pam4_eq[valid_start:]

        dec_pam4_sym, dec_pam4_idx = pam4_slicer(y_pam4_eq_valid)
        gt_pam4_levels, gt_pam4_idx = pam4_slicer(gt_pam4)  # 같은 slicer로 index 추출
        ber_pam4 = ber_from_indices(gt_pam4_idx, dec_pam4_idx)

        # --- M8 FFE only (노이즈만 Eb/N0별로 추가, FFE는 고정) ---
        y_m8 = add_awgn_ebn0(x_m8_chan, eb, bits_per_sym=3)
        y_m8_eq = apply_ffe(y_m8, w_m8)

        gt_m8 = s_m8[valid_start:]
        y_m8_eq_valid = y_m8_eq[valid_start:]

        dec_m8_eq_sym, dec_m8_eq_idx = m8_slicer(y_m8_eq_valid)
        _, gt_m8_idx = m8_slicer(gt_m8)
        ber_m8_eq = ber_from_indices(gt_m8_idx, dec_m8_eq_idx)

        # --- M8 FFE + Kuramoto ---
        z_m8_kura = apply_kuramoto_phase_tracker(y_m8_eq, mu_phase=mu_phase)
        z_m8_kura_valid = z_m8_kura[valid_start:]
        dec_m8_kura_sym, dec_m8_kura_idx = m8_slicer(z_m8_kura_valid)
        ber_m8_kura = ber_from_indices(gt_m8_idx, dec_m8_kura_idx)

        print(
            f" {eb:7.1f} |   {ber_pam4:1.9f} |   {ber_m8_eq:1.9f} |   {ber_m8_kura:1.9f}"
        )

    print("---------------------------------------------------------------")
    print()
    print("※ 주석")
    print(" - 채널 awgn: h=[1.0] (no-ISI), a/b/c: [0.1/0.05/0.075, 0.4/0.5/0.45, 1.0, ...] 5-tap mid-ISI (에너지 정규화).")
    print(" - PAM4 레벨: Gray-mapped [-3,-1,+3,+1], Es=1 로 정규화.")
    print(" - M8: 8-PSK unit circle (Es=1), 3 bit/sym 기준 Eb/N0로 잡음 주입.")
    print(" - FFE: complex LMS, ffe_len={0}, train_frac={1}, mu_ffe={2}.".format(ffe_len, train_frac, mu_ffe))
    print(" - Kuramoto-style phase tracker: 1-lane decision-directed 위상 보정부.")
    print("   · y_eq(k)에 대해 φ_k 를 유지하면서 z_k = y_eq(k)·e^{-jφ_k}.")
    print("   · slicer(d_k) 후 error phasor = d_k·z_k* 의 각도를 이용해 φ 업데이트.")
    print("   · φ_{k+1} = φ_k + μ_phase·angle(error_phasor).")
    print(" - 이 v0 실험은 multi-lane CoPBit Kuramoto의 단일 레인 근사 모델로,")
    print("   Q10~Q14에서 잡은 PhaseLock_std 파라미터를 단일 레인에 투영해")
    print("   'M8+위상락 vs PAM4+EQ' 구조의 intrinsic Eb/N0 이득을 보는 용도에 가깝다.")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q15 – M8 vs PAM4 (Channel-b + FFE + Kuramoto) BER vs Eb/N0 v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000, help="심볼 수 (기본: 200000)")
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="10,12,14,16,18,20,22",
        help='Eb/N0 리스트 (쉼표 구분, 예: "10,12,14,16")',
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="b",
        help="채널 선택: awgn / a / b / c (기본: b)",
    )
    parser.add_argument(
        "--ffe_len",
        type=int,
        default=7,
        help="FFE 탭 길이 (기본: 7)",
    )
    parser.add_argument(
        "--train_frac",
        type=float,
        default=0.2,
        help="FFE 학습에 사용하는 심볼 비율 (0~1, 기본: 0.2)",
    )
    parser.add_argument(
        "--mu_ffe",
        type=float,
        default=0.005,
        help="FFE LMS step (기본: 0.005)",
    )
    parser.add_argument(
        "--mu_phase",
        type=float,
        default=0.05,
        help="Kuramoto-style 위상 추적 step (기본: 0.05)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드 (기본: 1)",
    )

    args = parser.parse_args()
    ebn0_list = parse_ebn0_list(args.ebn0_list)

    run_q15(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        chan=args.channel,
        ffe_len=args.ffe_len,
        train_frac=args.train_frac,
        mu_ffe=args.mu_ffe,
        mu_phase=args.mu_phase,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()