#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q16_midISI – 2-lane p_ref + data (mid-ISI + FFE + 공통 위상 노이즈) v0

- Lane0: p_ref (고정 8-PSK 심볼)
- Lane1: data (랜덤 3bit/sym, M8)
- 채널: mid-ISI (ILC3에서 사용하던 5-tap 형태)
- EQ: 복소 FFE (LMS), 동일 w를 p_ref / data 모두에 적용
- PLL 모드:
  * No PLL      : 위상 추적 없음
  * Data-DD only: data lane만 보고 위상 추적
  * Data+p_ref  : p_ref lane + data lane 에러 혼합해 위상 추적

사용 예)
python copbit_q16_midISI_pref_awgn_phase_v0.py \
  --n_sym 200000 \
  --ebn0_list "12,14,16" \
  --theta_std_deg 3.0 \
  --ffe_len 7 \
  --train_frac 0.5 \
  --mu_ffe 0.005 \
  --mu_phase 0.05 \
  --alpha_ref 0.3 \
  --seed 1
"""

import argparse
import numpy as np


# -----------------------------
# 유틸: 파라미터 파서
# -----------------------------
def parse_ebn0_list(s):
    return [float(x) for x in s.split(",") if x.strip() != ""]


# -----------------------------
# 유틸: M8 (8-PSK) 맵핑
# -----------------------------
BITS_PER_SYM = 3  # M8 (3 bit / symbol)


def bits_to_ints(bits, k=BITS_PER_SYM):
    bits = bits.reshape(-1, k)
    vals = np.zeros(bits.shape[0], dtype=int)
    for i in range(k):
        vals = (vals << 1) | bits[:, i]
    return vals


def ints_to_bits(vals, k=BITS_PER_SYM):
    vals = np.array(vals, dtype=int).reshape(-1)
    bits = np.zeros((vals.shape[0], k), dtype=int)
    for i in range(k - 1, -1, -1):
        bits[:, i] = vals & 1
        vals >>= 1
    return bits.reshape(-1)


def m8_constellation():
    """
    index k=0..7 → 8-PSK on unit circle: exp(j*2πk/8)
    """
    k = np.arange(8)
    return np.exp(1j * 2 * np.pi * k / 8.0)


def map_ints_to_m8(sym_idx):
    const = m8_constellation()
    return const[sym_idx]


def slicer_m8(z):
    """
    복소 샘플 z를 가장 가까운 8-PSK 포인트 index로 양자화
    """
    angles = np.angle(z)
    angles[angles < 0] += 2 * np.pi
    # 8등분
    k_hat = np.round(angles * 8.0 / (2 * np.pi)) % 8
    return k_hat.astype(int)


# -----------------------------
# 채널: mid-ISI 5-tap (symbol-rate)
# -----------------------------
def make_mid_isi_channel():
    """
    ILC3에서 쓰던 mid-ISI 채널 계수 (norm) 5-tap 버전.
    실제 ILC3에서는 oversample=4로 더 길게 펴지만,
    여기서는 symbol-rate equalizer 테스트용으로 5-tap만 사용.
    """
    h = np.array([0.04075696, 0.40756957, 0.81513915, 0.40756957, 0.04075696], dtype=float)
    # 정규화 (에너지 1)
    h = h / np.sqrt(np.sum(h**2))
    return h


def apply_channel_mid_isi(x, h):
    """
    symbol-rate mid-ISI 채널: y = x * h (선형 컨볼루션, same 길이)
    """
    y = np.convolve(x, h, mode="same")
    return y


# -----------------------------
# AWGN 추가 (Eb/N0 기준)
# -----------------------------
def add_awgn(x, ebn0_db, bits_per_sym=BITS_PER_SYM):
    """
    Es=E[|x|^2] 기반으로 Eb/N0에 맞는 AWGN 추가
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    es = np.mean(np.abs(x) ** 2)
    # Eb = Es / k
    n0 = es / (bits_per_sym * ebn0_lin)
    sigma2 = n0 / 2.0
    noise = np.sqrt(sigma2) * (np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape))
    return x + noise


# -----------------------------
# FFE (복소 LMS)
# -----------------------------
def lms_ffe_train(rx, tx_sym, ffe_len, mu_ffe, train_frac):
    """
    rx: 수신 심볼 시퀀스 (complex), 채널+AWGN+phase 포함
    tx_sym: 송신 심볼 (training용 ground truth, complex)
    ffe_len: 탭 길이
    mu_ffe: LMS step size
    train_frac: 전체 중 training으로 쓸 비율 (0~1)

    출력:
        y_eq   : rx를 FFE 통과시킨 equalized 출력
        w      : 최종 FFE 계수 (복소)
    """
    n = len(rx)
    n_train = int(n * train_frac)
    if n_train < ffe_len:
        n_train = ffe_len

    # 초기 탭 (중앙 1, 나머지 0) 형태로 시작
    w = np.zeros(ffe_len, dtype=np.complex128)
    center = ffe_len // 2
    w[center] = 1.0 + 0j

    # 버퍼
    x_buf = np.zeros(ffe_len, dtype=np.complex128)
    y_eq = np.zeros_like(rx, dtype=np.complex128)

    for i in range(n):
        # 입력 탭 벡터 구성 (최신 샘플을 x_buf[0]에 넣는 형태)
        x_buf = np.roll(x_buf, 1)
        x_buf[0] = rx[i]

        y = np.vdot(w, x_buf)  # w^H x
        y_eq[i] = y

        if i < n_train:
            d = tx_sym[i]  # desired (training)
            e = d - y
            w = w + mu_ffe * np.conjugate(e) * x_buf

    return y_eq, w


# -----------------------------
# 위상 노이즈 (공통, Wiener process)
# -----------------------------
def generate_common_phase_noise(n_sym, theta_std_deg):
    sigma = theta_std_deg * np.pi / 180.0
    dphi = np.random.randn(n_sym) * sigma
    phi = np.cumsum(dphi)
    return phi  # length n_sym


# -----------------------------
# Q16_midISI 메인 루프
# -----------------------------
def run_q16_midisi(args):
    np.random.seed(args.seed)

    n_sym = args.n_sym
    ebn0_list = parse_ebn0_list(args.ebn0_list)
    theta_std_deg = args.theta_std_deg
    mu_phase = args.mu_phase
    alpha_ref = args.alpha_ref
    ffe_len = args.ffe_len
    train_frac = args.train_frac
    mu_ffe = args.mu_ffe

    # -------------------------
    # Tx 심볼 생성
    # -------------------------
    # data bits
    n_bits = n_sym * BITS_PER_SYM
    tx_bits = np.random.randint(0, 2, size=n_bits, dtype=int)
    tx_ints = bits_to_ints(tx_bits, k=BITS_PER_SYM)
    s_data = map_ints_to_m8(tx_ints)

    # p_ref lane: 고정 심볼 (k=0 → 1+0j)
    k_ref_const = 0
    s_const = m8_constellation()
    s_ref = np.full_like(s_data, s_const[k_ref_const])

    # 공통 위상 노이즈
    phi_noise = generate_common_phase_noise(n_sym, theta_std_deg)

    # mid-ISI 채널
    h = make_mid_isi_channel()

    # 결과 저장용
    ber_no_pll = []
    ber_dd_only = []
    ber_dd_pref = []

    print("=== CoPBit Q16_midISI – 2-lane (1 p_ref + 1 data), mid-ISI + FFE + common phase-noise v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_std_deg  = {theta_std_deg}")
    print(f"[Param] mu_phase       = {mu_phase}")
    print(f"[Param] alpha_ref      = {alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] ffe_len        = {ffe_len}")
    print(f"[Param] train_frac     = {train_frac}")
    print(f"[Param] mu_ffe         = {mu_ffe}")
    print(f"[Param] seed           = {args.seed}")
    print("")
    print(f"[Chan ] h_midISI (norm) = {h}")
    print("[Info ] 2-lane: Lane0=p_ref, Lane1=data, 공통 위상 노이즈 + AWGN + mid-ISI + FFE")
    print("")

    for ebn0 in ebn0_list:
        # -------------------------
        # 채널 + 위상 노이즈 + AWGN
        # -------------------------
        y_ref_ch = apply_channel_mid_isi(s_ref, h)
        y_data_ch = apply_channel_mid_isi(s_data, h)

        # 공통 위상 노이즈 적용
        phasor = np.exp(1j * phi_noise)
        y_ref_ph = y_ref_ch * phasor
        y_data_ph = y_data_ch * phasor

        # AWGN
        y_ref_noisy = add_awgn(y_ref_ph, ebn0, bits_per_sym=BITS_PER_SYM)
        y_data_noisy = add_awgn(y_data_ph, ebn0, bits_per_sym=BITS_PER_SYM)

        # -------------------------
        # FFE 학습 (training 구간에서만)
        #  - data lane 기준으로 w 학습 후, 동일 w를 p_ref lane에도 적용
        # -------------------------
        y_data_eq, w_ffe = lms_ffe_train(
            rx=y_data_noisy,
            tx_sym=s_data,
            ffe_len=ffe_len,
            mu_ffe=mu_ffe,
            train_frac=train_frac,
        )
        # p_ref에도 동일 w 적용
        # (실제론 joint training 등 여러 변형 가능하지만, v0에서는 단순 공유)
        y_ref_eq, _ = lms_ffe_train(
            rx=y_ref_noisy,
            tx_sym=s_ref,
            ffe_len=ffe_len,
            mu_ffe=0.0,        # w_ffe 고정 사용 (mu=0)
            train_frac=0.0,    # 학습 없음
        )
        # 위에서 mu_ffe=0, train_frac=0 로 넣었으므로 사실상 w_ffe를 다시 쓰기만 해야 하는데,
        # 구현 단순화를 위해 w_ffe를 직접 적용하는 방식으로 교체해도 됨.
        # 여기서는 간단히 직접 필터링:
        def apply_ffe(x, w):
            y = np.zeros_like(x, dtype=np.complex128)
            buf = np.zeros_like(w, dtype=np.complex128)
            L = len(w)
            for i in range(len(x)):
                buf = np.roll(buf, 1)
                buf[0] = x[i]
                y[i] = np.vdot(w, buf)
            return y

        y_ref_eq = apply_ffe(y_ref_noisy, w_ffe)
        y_data_eq = apply_ffe(y_data_noisy, w_ffe)

        # -------------------------
        # 3가지 모드에 대해 BER 계산
        # -------------------------
        # No PLL: 위상 추적 없음
        k_hat_no = slicer_m8(y_data_eq)
        bits_hat_no = ints_to_bits(k_hat_no, k=BITS_PER_SYM)
        ber_no = np.mean(bits_hat_no != tx_bits)

        # Data-DD only PLL
        phi_hat_dd = 0.0
        bits_hat_dd_list = []

        # Data+p_ref PLL
        phi_hat_pref = 0.0
        bits_hat_pref_list = []

        const = m8_constellation()

        for i in range(n_sym):
            # ---------------------
            # Data-DD only
            # ---------------------
            z_dd = y_data_eq[i] * np.exp(-1j * phi_hat_dd)
            k_dec_dd = slicer_m8(np.array([z_dd]))[0]
            s_dec_dd = const[k_dec_dd]
            # phase error (결정 심볼 vs 관측)
            e_dd = np.angle(s_dec_dd * np.conjugate(z_dd))
            phi_hat_dd += mu_phase * e_dd
            bits_hat_dd_list.extend(ints_to_bits(np.array([k_dec_dd]), k=BITS_PER_SYM))

            # ---------------------
            # Data + p_ref
            # ---------------------
            # p_ref 쪽
            z_ref = y_ref_eq[i] * np.exp(-1j * phi_hat_pref)
            k_dec_ref = slicer_m8(np.array([z_ref]))[0]
            s_dec_ref = const[k_dec_ref]
            e_ref = np.angle(s_const[k_ref_const] * np.conjugate(z_ref))

            # data 쪽
            z_pref = y_data_eq[i] * np.exp(-1j * phi_hat_pref)
            k_dec_pref = slicer_m8(np.array([z_pref]))[0]
            s_dec_pref = const[k_dec_pref]
            e_data = np.angle(s_dec_pref * np.conjugate(z_pref))

            e_total = (1.0 - alpha_ref) * e_ref + alpha_ref * e_data
            phi_hat_pref += mu_phase * e_total

            bits_hat_pref_list.extend(ints_to_bits(np.array([k_dec_pref]), k=BITS_PER_SYM))

        bits_hat_dd = np.array(bits_hat_dd_list, dtype=int)
        bits_hat_pref = np.array(bits_hat_pref_list, dtype=int)

        ber_dd = np.mean(bits_hat_dd != tx_bits)
        ber_pref = np.mean(bits_hat_pref != tx_bits)

        ber_no_pll.append(ber_no)
        ber_dd_only.append(ber_dd)
        ber_dd_pref.append(ber_pref)

    # -----------------------------
    # 결과 출력
    # -----------------------------
    print("")
    print("===============================================================")
    print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef       ")
    print("---------------------------------------------------------------")
    for eb, b0, b1, b2 in zip(ebn0_list, ber_no_pll, ber_dd_only, ber_dd_pref):
        print(f"{eb:9.1f} | {b0:12.6f} | {b1:12.6f} | {b2:12.6f}")
    print("---------------------------------------------------------------")
    print("")
    print("※ 주석")
    print(" - mid-ISI 채널(5-tap symbol-rate) + 공통 위상 노이즈 + AWGN + FFE 환경에서")
    print("   2-lane (p_ref + data)의 위상 추적 성능을 비교하는 Q16_midISI v0 실험.")
    print(" - No PLL       : equalized data에 대해 위상 추적 없이 8-PSK slicer만 적용.")
    print(" - Data-DD only : data lane만 보고 위상 에러를 추정해 φ 업데이트.")
    print(" - Data+p_ref   : p_ref lane 에러(e_ref)와 data lane 에러(e_data)를")
    print("                  alpha_ref 비율로 섞어서 φ 업데이트.")
    print(" - theta_std_deg, alpha_ref, mu_phase, ffe_len, mu_ffe 등을 바꿔 가며")
    print("   Q13/Q14(64-lane) 결과와의 스케일링 관계를 보는 용도로 사용 가능.")


# -----------------------------
# main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q16_midISI – 2-lane p_ref + data (mid-ISI + FFE + 공통 위상 노이즈) v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000)
    parser.add_argument("--ebn0_list", type=str, default="12,14,16")
    parser.add_argument("--theta_std_deg", type=float, default=3.0)
    parser.add_argument("--mu_phase", type=float, default=0.05)
    parser.add_argument("--alpha_ref", type=float, default=0.3)
    parser.add_argument("--ffe_len", type=int, default=7)
    parser.add_argument("--train_frac", type=float, default=0.5)
    parser.add_argument("--mu_ffe", type=float, default=0.005)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    run_q16_midisi(args)


if __name__ == "__main__":
    main()