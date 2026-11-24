"""Real-time vectorized NumPy/SciPy DSP engine for extreme voice boost and strong echo."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import threading
from typing import Dict, Tuple

import numpy as np
from scipy.signal import lfilter


@dataclass
class DSPParams:
    enabled: bool = True
    # Amplification / Thickening
    preamp_db: float = 12.0          # 0 .. +24 dB
    bass_boost_db: float = 12.0      # 0 .. +20 dB (low shelf @ 135 Hz)
    body_boost_db: float = 6.0       # 0 .. +14 dB (peaking @ 280 Hz)
    presence_db: float = 4.0         # -6 .. +10 dB (peaking @ 2400 Hz)
    sub_bass: float = 0.75           # 0.0 .. 1.5 (sub-harmonic octave thickener)
    drive: float = 3.2               # 1.0 .. 8.0 (tube saturation + punch)
    gate_db: float = -75.0           # -75 .. -20 dB (noise gate threshold; <= -72 disables gate)

    # Strong Echo & Reverb
    echo_delay_ms: float = 240.0     # 60 .. 800 ms
    echo_feedback: float = 0.74      # 0.0 .. 0.90
    echo_level: float = 1.45         # 0.0 .. 2.0 (wet boost up to 200%)
    reverb_level: float = 0.75       # 0.0 .. 1.5
    reverb_decay: float = 0.76       # 0.20 .. 0.92

    # Master
    output_gain_db: float = 6.0      # -12 .. +18 dB


DEFAULT_PRESET_NAME = "وزنية أبو فهد (الأساسية)"

PRESETS: Dict[str, DSPParams] = {
    "وزنية أبو فهد (الأساسية)": DSPParams(
        enabled=True,
        preamp_db=12.0,
        bass_boost_db=13.0,
        body_boost_db=7.0,
        presence_db=4.0,
        sub_bass=0.80,
        drive=3.5,
        gate_db=-75.0,
        echo_delay_ms=245.0,
        echo_feedback=0.76,
        echo_level=1.55,
        reverb_level=0.80,
        reverb_decay=0.78,
        output_gain_db=6.0,
    ),
    "تضخيم وحشي + صدى عالي": DSPParams(
        enabled=True,
        preamp_db=16.0,
        bass_boost_db=17.0,
        body_boost_db=10.0,
        presence_db=5.0,
        sub_bass=1.15,
        drive=5.2,
        gate_db=-75.0,
        echo_delay_ms=310.0,
        echo_feedback=0.82,
        echo_level=1.75,
        reverb_level=1.05,
        reverb_decay=0.84,
        output_gain_db=8.0,
    ),
    "صدى متكرر قوي": DSPParams(
        enabled=True,
        preamp_db=11.0,
        bass_boost_db=10.0,
        body_boost_db=5.0,
        presence_db=5.0,
        sub_bass=0.60,
        drive=3.0,
        gate_db=-75.0,
        echo_delay_ms=280.0,
        echo_feedback=0.86,
        echo_level=1.90,
        reverb_level=0.95,
        reverb_decay=0.85,
        output_gain_db=6.0,
    ),
    "صدى عميق وطويل": DSPParams(
        enabled=True,
        preamp_db=11.0,
        bass_boost_db=6.0,
        body_boost_db=8.5,
        presence_db=3.0,
        sub_bass=0.35,
        drive=3.0,
        gate_db=-75.0,
        echo_delay_ms=260.0,
        echo_feedback=0.78,
        echo_level=1.45,
        reverb_level=1.25,
        reverb_decay=0.88,
        output_gain_db=5.0,
    ),
    "تضخيم ثقيل + صدى سريع": DSPParams(
        enabled=True,
        preamp_db=14.5,
        bass_boost_db=4.5,
        body_boost_db=12.0,
        presence_db=3.5,
        sub_bass=0.25,
        drive=3.8,
        gate_db=-75.0,
        echo_delay_ms=94.0,
        echo_feedback=0.72,
        echo_level=1.35,
        reverb_level=1.05,
        reverb_decay=0.80,
        output_gain_db=4.5,
    ),
    "صدى واسع ومفتوح": DSPParams(
        enabled=True,
        preamp_db=10.5,
        bass_boost_db=6.5,
        body_boost_db=8.0,
        presence_db=2.5,
        sub_bass=0.30,
        drive=2.8,
        gate_db=-75.0,
        echo_delay_ms=220.0,
        echo_feedback=0.74,
        echo_level=1.30,
        reverb_level=1.15,
        reverb_decay=0.84,
        output_gain_db=5.0,
    ),
    "صوت جهوري وواضح": DSPParams(
        enabled=True,
        preamp_db=11.5,
        bass_boost_db=8.0,
        body_boost_db=9.0,
        presence_db=4.0,
        sub_bass=0.45,
        drive=3.2,
        gate_db=-75.0,
        echo_delay_ms=190.0,
        echo_feedback=0.68,
        echo_level=1.25,
        reverb_level=1.10,
        reverb_decay=0.82,
        output_gain_db=5.5,
    ),
    "صدى ناعم ومرتب": DSPParams(
        enabled=True,
        preamp_db=10.0,
        bass_boost_db=5.0,
        body_boost_db=7.0,
        presence_db=3.5,
        sub_bass=0.20,
        drive=2.6,
        gate_db=-75.0,
        echo_delay_ms=165.0,
        echo_feedback=0.66,
        echo_level=1.15,
        reverb_level=0.95,
        reverb_decay=0.76,
        output_gain_db=4.5,
    ),
    "صوت مكتوم وثقيل": DSPParams(
        enabled=True,
        preamp_db=13.0,
        bass_boost_db=7.5,
        body_boost_db=11.0,
        presence_db=2.0,
        sub_bass=0.30,
        drive=4.0,
        gate_db=-75.0,
        echo_delay_ms=72.0,
        echo_feedback=0.64,
        echo_level=1.20,
        reverb_level=0.85,
        reverb_decay=0.72,
        output_gain_db=6.0,
    ),
    "تضخيم صافي + صدى خفيف": DSPParams(
        enabled=True,
        preamp_db=9.0,
        bass_boost_db=11.0,
        body_boost_db=6.0,
        presence_db=3.0,
        sub_bass=0.55,
        drive=2.0,
        gate_db=-75.0,
        echo_delay_ms=210.0,
        echo_feedback=0.60,
        echo_level=1.05,
        reverb_level=0.50,
        reverb_decay=0.68,
        output_gain_db=4.0,
    ),
}


def _biquad_highpass(fc: float, q: float, fs: float) -> Tuple[np.ndarray, np.ndarray]:
    w0 = 2.0 * math.pi * fc / fs
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _biquad_lowpass(fc: float, q: float, fs: float) -> Tuple[np.ndarray, np.ndarray]:
    w0 = 2.0 * math.pi * fc / fs
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = (1.0 - cos_w0) / 2.0
    b1 = 1.0 - cos_w0
    b2 = (1.0 - cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _biquad_lowshelf(fc: float, gain_db: float, slope: float, fs: float) -> Tuple[np.ndarray, np.ndarray]:
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / fs
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / 2.0 * math.sqrt((A + 1.0 / A) * (1.0 / slope - 1.0) + 2.0)
    sqrt_a_2_alpha = 2.0 * math.sqrt(A) * alpha
    b0 = A * ((A + 1.0) - (A - 1.0) * cos_w0 + sqrt_a_2_alpha)
    b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cos_w0)
    b2 = A * ((A + 1.0) - (A - 1.0) * cos_w0 - sqrt_a_2_alpha)
    a0 = (A + 1.0) + (A - 1.0) * cos_w0 + sqrt_a_2_alpha
    a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cos_w0)
    a2 = (A + 1.0) + (A - 1.0) * cos_w0 - sqrt_a_2_alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _biquad_peaking(fc: float, gain_db: float, q: float, fs: float) -> Tuple[np.ndarray, np.ndarray]:
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / fs
    cos_w0 = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * q)
    b0 = 1.0 + alpha * A
    b1 = -2.0 * cos_w0
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha / A
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


class AudioDSP:
    """Real-time stereo voice amplifier + heavy echo/reverb processor."""

    MAX_SUBBLOCK = 512

    def __init__(self, sample_rate: int = 48000) -> None:
        self.fs = float(sample_rate)
        self._lock = threading.Lock()
        self.params = DSPParams(**asdict(PRESETS[DEFAULT_PRESET_NAME]))

        # Filter coefficients & persistent states
        self._eq_dirty = True
        self._hp_ba = _biquad_highpass(38.0, 0.707, self.fs)
        self._hp_zi = np.zeros(2, dtype=np.float64)

        self._ls_ba = _biquad_lowshelf(145.0, self.params.bass_boost_db, 0.85, self.fs)
        self._ls_zi = np.zeros(2, dtype=np.float64)

        self._body_ba = _biquad_peaking(520.0, self.params.body_boost_db, 0.85, self.fs)
        self._body_zi = np.zeros(2, dtype=np.float64)

        self._pres_ba = _biquad_peaking(2400.0, self.params.presence_db, 1.1, self.fs)
        self._pres_zi = np.zeros(2, dtype=np.float64)

        self._sub_lp_ba = _biquad_lowpass(115.0, 0.75, self.fs)
        self._sub_lp_zi = np.zeros(2, dtype=np.float64)
        self._sub_hp_ba = _biquad_highpass(32.0, 0.707, self.fs)
        self._sub_hp_zi = np.zeros(2, dtype=np.float64)

        self._echo_lp_ba = _biquad_lowpass(3800.0, 0.707, self.fs)
        self._echo_lp_zi_l = np.zeros(2, dtype=np.float64)
        self._echo_lp_zi_r = np.zeros(2, dtype=np.float64)

        # Gate envelope state
        self._gate_env = 1.0
        self._gate_hold_blocks = 0
        self._comp_gain = 1.0

        # Stereo Echo ring buffer (up to 4 seconds)
        self._echo_buf_len = int(self.fs * 4.0)
        self._echo_buf = np.zeros((self._echo_buf_len, 2), dtype=np.float32)
        self._echo_idx = 0

        # 6 parallel comb filters for dense hall reverb (all >= 1024 samples at 48kHz)
        scale = self.fs / 48000.0
        base_combs = [1319, 1601, 1933, 2267, 2659, 3079]
        self._comb_delays = [max(self.MAX_SUBBLOCK + 16, int(d * scale)) for d in base_combs]
        self._comb_bufs = [np.zeros(d + self.MAX_SUBBLOCK, dtype=np.float32) for d in self._comb_delays]
        self._comb_idx = [0 for _ in self._comb_delays]
        self._comb_lp_state = [0.0 for _ in self._comb_delays]

        # Telemetry (read by UI)
        self.input_level_db = -60.0
        self.output_level_db = -60.0
        self.echo_level_db = -60.0
        self.is_clipping = False

    def set_sample_rate(self, sample_rate: int) -> None:
        if int(sample_rate) == int(self.fs):
            return
        with self._lock:
            self.__init__(sample_rate=int(sample_rate))

    def update_params(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.params, key):
                    setattr(self.params, key, value)
            self._eq_dirty = True

    def load_preset(self, preset_name: str) -> DSPParams:
        preset = PRESETS[preset_name]
        with self._lock:
            self.params = DSPParams(**asdict(preset))
            self._eq_dirty = True
            return DSPParams(**asdict(self.params))

    def reset_buffers(self) -> None:
        with self._lock:
            self._echo_buf.fill(0.0)
            for buf in self._comb_bufs:
                buf.fill(0.0)
            self._hp_zi.fill(0.0)
            self._ls_zi.fill(0.0)
            self._body_zi.fill(0.0)
            self._pres_zi.fill(0.0)
            self._sub_lp_zi.fill(0.0)
            self._sub_hp_zi.fill(0.0)
            self._echo_lp_zi_l.fill(0.0)
            self._echo_lp_zi_r.fill(0.0)

    def _rebuild_eq(self, p: DSPParams) -> None:
        self._ls_ba = _biquad_lowshelf(145.0, p.bass_boost_db, 0.85, self.fs)
        self._body_ba = _biquad_peaking(520.0, p.body_boost_db, 0.85, self.fs)
        self._pres_ba = _biquad_peaking(2400.0, p.presence_db, 1.1, self.fs)
        self._eq_dirty = False

    def process(self, indata: np.ndarray) -> np.ndarray:
        """Process mono or stereo float32 block and return stereo float32 block."""
        if indata.ndim == 2 and indata.shape[1] > 1:
            mono = 0.5 * (indata[:, 0] + indata[:, 1])
        else:
            mono = indata.reshape(-1)

        n = len(mono)
        if n == 0:
            return np.zeros((0, 2), dtype=np.float32)

        in_rms = float(np.sqrt(np.mean(mono * mono) + 1e-12))
        self.input_level_db = max(-60.0, min(0.0, 20.0 * math.log10(in_rms + 1e-9)))

        with self._lock:
            p = DSPParams(**asdict(self.params))
            if self._eq_dirty:
                self._rebuild_eq(p)

        if not p.enabled:
            out = np.column_stack((mono, mono)).astype(np.float32)
            self.output_level_db = self.input_level_db
            self.echo_level_db = -60.0
            self.is_clipping = False
            return out

        # Process in sub-blocks <= MAX_SUBBLOCK so all ring-buffer slices are single vectorized ops
        out = np.empty((n, 2), dtype=np.float32)
        echo_energy_acc = 0.0
        pos = 0
        while pos < n:
            end = min(n, pos + self.MAX_SUBBLOCK)
            out[pos:end], blk_echo_rms = self._process_subblock(mono[pos:end], p)
            echo_energy_acc += blk_echo_rms * (end - pos)
            pos = end

        out_rms = float(np.sqrt(np.mean(out * out) + 1e-12))
        self.output_level_db = max(-60.0, min(0.0, 20.0 * math.log10(out_rms + 1e-9)))
        avg_echo = echo_energy_acc / max(1, n)
        self.echo_level_db = max(-60.0, min(0.0, 20.0 * math.log10(avg_echo + 1e-9)))
        self.is_clipping = bool(np.max(np.abs(out)) >= 0.96)
        return out

    def _process_subblock(self, x: np.ndarray, p: DSPParams) -> Tuple[np.ndarray, float]:
        n = len(x)
        x64 = x.astype(np.float64, copy=False)

        # 1. Clean ultra-low rumble
        x64, self._hp_zi = lfilter(self._hp_ba[0], self._hp_ba[1], x64, zi=self._hp_zi)

        # 2. Optional smooth noise gate (completely bypassed when gate_db <= -72 dB)
        if p.gate_db > -72.0:
            blk_rms = float(np.sqrt(np.mean(x64 * x64) + 1e-12))
            blk_db = 20.0 * math.log10(blk_rms + 1e-9)
            if blk_db >= p.gate_db:
                self._gate_hold_blocks = 24  # ~250 ms smooth hold so syllables never chop
                target_gate = 1.0
            elif self._gate_hold_blocks > 0:
                self._gate_hold_blocks -= 1
                target_gate = 1.0
            else:
                target_gate = 0.0
            alpha_g = 0.65 if target_gate > self._gate_env else 0.08
            self._gate_env += alpha_g * (target_gate - self._gate_env)
            x64 = x64 * self._gate_env
        else:
            self._gate_env = 1.0

        # 3. Preamp gain
        preamp_lin = 10.0 ** (p.preamp_db / 20.0)
        x64 = x64 * preamp_lin

        # 4. Vocal Body EQ (Low-Shelf Bass + Chest Body + Presence)
        x64, self._ls_zi = lfilter(self._ls_ba[0], self._ls_ba[1], x64, zi=self._ls_zi)
        x64, self._body_zi = lfilter(self._body_ba[0], self._body_ba[1], x64, zi=self._body_zi)
        x64, self._pres_zi = lfilter(self._pres_ba[0], self._pres_ba[1], x64, zi=self._pres_zi)

        # 5. Sub-harmonic bass thickener (adds deep chest octave weight)
        if p.sub_bass > 0.01:
            sub_raw = np.abs(x64)
            sub_lp, self._sub_lp_zi = lfilter(
                self._sub_lp_ba[0], self._sub_lp_ba[1], sub_raw, zi=self._sub_lp_zi
            )
            sub_clean, self._sub_hp_zi = lfilter(
                self._sub_hp_ba[0], self._sub_hp_ba[1], sub_lp, zi=self._sub_hp_zi
            )
            x64 = x64 + sub_clean * (p.sub_bass * 1.35)

        # 6. Tube saturation & auto-leveling compressor ("تضخيم متوحش")
        driven = np.tanh(x64 * (p.drive * 0.65)) / math.tanh(max(0.5, p.drive * 0.65))
        # Fast upward/downward leveling so quiet syllables are also huge
        drv_rms = float(np.sqrt(np.mean(driven * driven) + 1e-12))
        target_comp = min(2.4, 0.38 / max(0.08, drv_rms))
        self._comp_gain += 0.18 * (target_comp - self._comp_gain)
        dry = (driven * self._comp_gain).astype(np.float32)

        # 7. Multi-Tap Stereo Echo (صدى قوي جداً)
        delay_1 = max(n + 1, int((p.echo_delay_ms / 1000.0) * self.fs))
        delay_1 = min(delay_1, self._echo_buf_len - n - 1)
        delay_2 = max(n + 1, int(delay_1 * 0.62))
        delay_3 = min(self._echo_buf_len - n - 1, max(n + 1, int(delay_1 * 1.48)))

        buf_len = self._echo_buf_len
        idx = self._echo_idx

        def _read_ring(delay_samples: int) -> np.ndarray:
            start = (idx - delay_samples) % buf_len
            end = start + n
            if end <= buf_len:
                return self._echo_buf[start:end]
            first = buf_len - start
            return np.vstack((self._echo_buf[start:], self._echo_buf[: n - first]))

        tap1 = _read_ring(delay_1)
        tap2 = _read_ring(delay_2)
        tap3 = _read_ring(delay_3)

        # Stereo cross-bounce for wide, massive echo presence
        echo_l = 0.62 * tap1[:, 0] + 0.30 * tap2[:, 1] + 0.24 * tap3[:, 0]
        echo_r = 0.62 * tap1[:, 1] + 0.30 * tap2[:, 0] + 0.24 * tap3[:, 1]

        # Warm low-pass inside feedback loop so repeats stay thick and never harsh
        fb_l, self._echo_lp_zi_l = lfilter(
            self._echo_lp_ba[0], self._echo_lp_ba[1], echo_l.astype(np.float64), zi=self._echo_lp_zi_l
        )
        fb_r, self._echo_lp_zi_r = lfilter(
            self._echo_lp_ba[0], self._echo_lp_ba[1], echo_r.astype(np.float64), zi=self._echo_lp_zi_r
        )

        fb = min(0.90, max(0.0, p.echo_feedback))
        write_l = np.tanh((dry * 0.85 + fb_l * fb) * 0.95).astype(np.float32)
        write_r = np.tanh((dry * 0.85 + fb_r * fb) * 0.95).astype(np.float32)

        end_w = idx + n
        if end_w <= buf_len:
            self._echo_buf[idx:end_w, 0] = write_l
            self._echo_buf[idx:end_w, 1] = write_r
        else:
            first = buf_len - idx
            self._echo_buf[idx:, 0] = write_l[:first]
            self._echo_buf[idx:, 1] = write_r[:first]
            self._echo_buf[: n - first, 0] = write_l[first:]
            self._echo_buf[: n - first, 1] = write_r[first:]
        self._echo_idx = (idx + n) % buf_len

        echo_stereo = np.column_stack((echo_l, echo_r)).astype(np.float32) * p.echo_level

        # 8. Dense 6-Comb Hall Reverb (fed by dry + echo for giant room tail)
        reverb_in = dry + 0.55 * (echo_stereo[:, 0] + echo_stereo[:, 1]) * 0.5
        rev_l = np.zeros(n, dtype=np.float32)
        rev_r = np.zeros(n, dtype=np.float32)
        decay = min(0.92, max(0.1, p.reverb_decay))

        if p.reverb_level > 0.01:
            for c_idx, (d_len, buf) in enumerate(zip(self._comb_delays, self._comb_bufs)):
                c_pos = self._comb_idx[c_idx]
                buf_sz = len(buf)
                # Read d_len samples behind c_pos
                r_start = (c_pos - d_len) % buf_sz
                r_end = r_start + n
                if r_end <= buf_sz:
                    delayed = buf[r_start:r_end]
                else:
                    first = buf_sz - r_start
                    delayed = np.concatenate((buf[r_start:], buf[: n - first]))

                # Damped feedback
                damped = delayed * (decay * (0.94 - 0.015 * c_idx))
                new_val = np.tanh((reverb_in + damped) * 0.85).astype(np.float32)

                w_end = c_pos + n
                if w_end <= buf_sz:
                    buf[c_pos:w_end] = new_val
                else:
                    first = buf_sz - c_pos
                    buf[c_pos:] = new_val[:first]
                    buf[: n - first] = new_val[first:]
                self._comb_idx[c_idx] = (c_pos + n) % buf_sz

                if c_idx % 2 == 0:
                    rev_l += delayed
                else:
                    rev_r += delayed

            rev_gain = p.reverb_level * 0.34
            rev_stereo = np.column_stack((rev_l * rev_gain, rev_r * rev_gain))
        else:
            rev_stereo = np.zeros((n, 2), dtype=np.float32)

        # 9. Mix Dry + Strong Echo + Hall Reverb + Master Gain + Soft Limiter
        dry_stereo = np.column_stack((dry, dry))
        mixed = dry_stereo + echo_stereo + rev_stereo

        master_lin = 10.0 ** (p.output_gain_db / 20.0)
        mixed = mixed * master_lin

        # Brickwall soft-ceiling limiter at +/- 0.98
        limited = np.tanh(mixed * 0.82) / 0.85
        limited = np.clip(limited, -0.98, 0.98).astype(np.float32)

        echo_rms = float(np.sqrt(np.mean((echo_stereo + rev_stereo) ** 2) + 1e-12))
        return limited, echo_rms
