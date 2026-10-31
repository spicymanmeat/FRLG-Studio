#!/usr/bin/env python3
"""Legacy oscillator fallback for FRLG Studio's PC/UI cues.

The bundled bank at assets/sound/sfx is now rendered from the actual HGSS
sequences and SWAV samples.  This script is kept for reference and writes to
assets/sound/sfx_synth instead, so running it cannot overwrite the real bank.

Run from the repository root:

    python3 tools/generate_pc_sfx.py

Output: assets/sound/sfx_synth/*.wav, 16-bit mono / 44.1 kHz.  SoundPack does
not read this folder; it is a scratch/reference render only.
"""

from __future__ import annotations

import math
import random
import wave
from pathlib import Path

SAMPLE_RATE = 44_100
TAU = math.tau
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "sound" / "sfx_synth"
RNG = random.Random(0xF41A6)


# ---------------------------------------------------------------------------
# Oscillators and envelopes
# ---------------------------------------------------------------------------
def _samples(duration: float) -> int:
    return max(1, int(round(duration * SAMPLE_RATE)))


def _shape(phase: float, name: str, duty: float = 0.5) -> float:
    phase = phase % TAU
    if name == "sine":
        return math.sin(phase)
    if name == "triangle":
        return (2.0 / math.pi) * math.asin(math.sin(phase))
    if name == "square":
        return 1.0 if phase < TAU * duty else -1.0
    if name == "saw":
        return (phase / math.pi) - 1.0
    # Rounded square: fewer painful edges than a hard square while keeping the
    # GBA/DS "chip" body.
    return math.tanh(2.6 * math.sin(phase))


def _envelope(
    index: int,
    count: int,
    attack: float,
    decay: float,
    release: float = 0.01,
) -> float:
    t = index / SAMPLE_RATE
    atk = max(1, int(attack * SAMPLE_RATE))
    if index < atk:
        value = index / atk
    elif decay > 0:
        value = math.exp(-(t - attack) / decay)
    else:
        value = 1.0
    remaining = (count - index) / SAMPLE_RATE
    if release > 0 and remaining < release:
        value *= max(0.0, remaining / release)
    return value


def tone(
    start_hz: float,
    end_hz: float | None = None,
    duration: float = 0.12,
    *,
    shape: str = "triangle",
    amp: float = 0.35,
    attack: float = 0.003,
    decay: float = 0.08,
    release: float = 0.008,
    vibrato_hz: float = 0.0,
    vibrato_cents: float = 0.0,
    duty: float = 0.5,
) -> list[float]:
    """One gliding oscillator note."""
    end_hz = start_hz if end_hz is None else end_hz
    count = _samples(duration)
    out: list[float] = []
    phase = 0.0
    for i in range(count):
        u = i / max(1, count - 1)
        hz = start_hz * (end_hz / start_hz) ** u
        if vibrato_hz and vibrato_cents:
            hz *= 2.0 ** (
                (vibrato_cents / 1200.0)
                * math.sin(TAU * vibrato_hz * i / SAMPLE_RATE)
            )
        phase += TAU * hz / SAMPLE_RATE
        env = _envelope(i, count, attack, decay, release)
        out.append(amp * env * _shape(phase, shape, duty))
    return out


def note(
    hz: float,
    duration: float,
    *,
    amp: float = 0.3,
    decay: float = 0.16,
    shape: str = "triangle",
) -> list[float]:
    return tone(hz, hz, duration, shape=shape, amp=amp, decay=decay)


def pc_square(hz: float, duration: float, amp: float) -> list[float]:
    """The HGSS PC login/logout voice: 50% duty square, light vibrato."""
    return tone(
        hz,
        hz,
        duration,
        shape="square",
        duty=0.5,
        amp=amp,
        attack=0.004,
        decay=4.0,
        release=0.009,
        vibrato_hz=5.5,
        vibrato_cents=8.0,
    )


def _metal_partial(hz: float, duration: float, amp: float, decay: float) -> list[float]:
    count = _samples(duration)
    out = []
    for i in range(count):
        t = i / SAMPLE_RATE
        env = math.exp(-t / max(0.001, decay))
        remaining = (count - i) / SAMPLE_RATE
        if remaining < 0.006:
            env *= max(0.0, remaining / 0.006)
        out.append(amp * env * math.sin(TAU * hz * t))
    return out


def clink(
    base_hz: float = 1_880.0,
    duration: float = 0.14,
    *,
    amp: float = 0.42,
) -> list[float]:
    """A short ceramic/metallic A-button tick."""
    out = [0.0] * _samples(duration)
    partials = (
        (base_hz, 0.55, 0.045),
        (base_hz * 1.49, 0.30, 0.032),
        (base_hz * 2.24, 0.17, 0.024),
        (base_hz * 3.31, 0.08, 0.018),
    )
    for hz, weight, decay in partials:
        add(out, _metal_partial(hz, duration, amp * weight, decay))
    add(out, tone(base_hz * 0.52, base_hz * 0.50, 0.055,
                  shape="sine", amp=amp * 0.22, decay=0.020), 0.0)
    add(out, click(0.014, amp * 0.22, 2_600.0), 0.0)
    return out


def click(duration: float = 0.018, amp: float = 0.18, cutoff: float = 2_200.0) -> list[float]:
    """A tiny high-passed noise transient."""
    count = _samples(duration)
    out = []
    low = 0.0
    alpha = 1.0 - math.exp(-TAU * cutoff / SAMPLE_RATE)
    for i in range(count):
        sample = RNG.uniform(-1.0, 1.0)
        low += alpha * (sample - low)
        high = sample - low
        env = math.exp(-(i / SAMPLE_RATE) / max(0.001, duration * 0.25))
        out.append(amp * env * high)
    return out


def noise_sweep(
    duration: float,
    amp: float,
    start_hz: float,
    end_hz: float,
    *,
    q: float = 0.9,
) -> list[float]:
    """Band-passed noise whose centre frequency glides."""
    count = _samples(duration)
    out = []
    low = 0.0
    band = 0.0
    nyquist = SAMPLE_RATE * 0.45
    for i in range(count):
        u = i / max(1, count - 1)
        cutoff = start_hz * (end_hz / start_hz) ** u
        cutoff = max(60.0, min(nyquist, cutoff))
        f = 2.0 * math.sin(math.pi * cutoff / SAMPLE_RATE)
        sample = RNG.uniform(-1.0, 1.0)
        high = sample - low - q * band
        band += f * high
        low += f * band
        env = math.sin(math.pi * u) ** 1.4
        out.append(amp * env * band)
    return out


def thump(duration: float = 0.18, amp: float = 0.3) -> list[float]:
    return tone(95.0, 62.0, duration, shape="sine", amp=amp,
                attack=0.002, decay=duration * 0.35)


# ---------------------------------------------------------------------------
# Mixing helpers
# ---------------------------------------------------------------------------
def add(dst: list[float], src: list[float], at: float = 0.0, gain: float = 1.0) -> None:
    start = int(round(at * SAMPLE_RATE))
    if start < 0:
        src = src[-start:]
        start = 0
    need = start + len(src)
    if len(dst) < need:
        dst.extend([0.0] * (need - len(dst)))
    for i, sample in enumerate(src):
        dst[start + i] += sample * gain


def delay(samples: list[float], seconds: float, mix: float = 0.2) -> list[float]:
    """A simple feedback echo, kept short so the cue still ends cleanly."""
    out = list(samples) + [0.0] * int(seconds * SAMPLE_RATE * 2)
    step = max(1, int(round(seconds * SAMPLE_RATE)))
    for i in range(step, len(out)):
        out[i] += out[i - step] * mix
    return out


def lowpass(samples: list[float], cutoff: float) -> list[float]:
    out = []
    value = 0.0
    alpha = 1.0 - math.exp(-TAU * cutoff / SAMPLE_RATE)
    for sample in samples:
        value += alpha * (sample - value)
        out.append(value)
    return out


def normalize(samples: list[float], peak: float = 0.9) -> list[float]:
    top = max((abs(value) for value in samples), default=0.0)
    if top <= 1e-9:
        return samples
    scale = peak / top
    return [value * scale for value in samples]


def retro(samples: list[float], bits: int = 12) -> list[float]:
    """Gentle quantisation for a DS-era edge without audible grit."""
    levels = float(2 ** (bits - 1))
    return [round(value * levels) / levels for value in samples]


def write(
    name: str,
    samples: list[float],
    *,
    peak: float = 0.9,
    cutoff: float = 16_500.0,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = lowpass(samples, cutoff)
    samples = normalize(samples, peak)
    samples = retro(samples)
    # Avoid a speaker pop at either edge.
    fade = min(len(samples) // 2, int(0.003 * SAMPLE_RATE))
    for i in range(fade):
        samples[i] *= i / fade
        samples[-1 - i] *= i / fade
    path = OUT_DIR / f"{name}.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for value in samples:
            integer = int(max(-1.0, min(1.0, value)) * 32_767)
            frames.extend(integer.to_bytes(2, "little", signed=True))
        handle.writeframes(bytes(frames))
    return path


# ---------------------------------------------------------------------------
# Cue designs
# ---------------------------------------------------------------------------
def make_pc_open() -> list[float]:
    """SEQ_SE_DP_PC_LOGIN: two low C5 square boops with quiet echoes.

    Platinum/HGSS sequence data: tempo 143, C5 at 16 ticks, rest 16, a
    velocity-25 C5 at 8 ticks, rest 8, then the loud/quiet pair repeats.
    That is 0.84 s total, not a four-note logo sting.
    """
    tick = 60.0 / (143 * 48)
    out: list[float] = []
    for start, duration, amp in (
        (0, 16, 0.34),
        (32, 8, 0.085),
        (48, 16, 0.34),
        (80, 8, 0.075),
    ):
        add(out, pc_square(523.251, duration * tick, amp), start * tick)
    return out


def make_pc_close() -> list[float]:
    """SEQ_SE_DP_PC_LOGOFF: C4 -> C3 -> C2, plus a quiet C2 tail.

    Tempo 120, eight ticks per note/rest.  This is the low descending
    'de-doo' the storage screen uses on exit.
    """
    tick = 60.0 / (120 * 48)
    out: list[float] = []
    for start, hz, amp in (
        (0, 261.626, 0.30),
        (16, 130.813, 0.30),
        (32, 65.406, 0.30),
        (48, 65.406, 0.07),
    ):
        add(out, pc_square(hz, 8 * tick, amp), start * tick)
    return out


def make_pc_pick() -> list[float]:
    """BOX02: the soft rising 'sutya' lift, not the A-click.

    The original is a short filtered-noise sample at E4 that glides up to
    G5.  Keep the low-mid body and airy tail; avoid the metallic partials
    that made this sound like a button press.
    """
    out: list[float] = []
    add(out, tone(329.63, 329.63, 0.045, shape="triangle",
                  amp=0.14, attack=0.002, decay=0.020), 0.0)
    add(out, noise_sweep(0.060, 0.060, 280.0, 900.0, q=1.0), 0.0)
    add(out, tone(329.63, 783.99, 0.105, shape="triangle",
                  amp=0.20, attack=0.004, decay=0.055), 0.030)
    add(out, noise_sweep(0.125, 0.13, 400.0, 1_400.0, q=1.1), 0.025)
    add(out, noise_sweep(0.070, 0.045, 900.0, 1_800.0, q=0.9), 0.110)
    return out


def make_pc_place() -> list[float]:
    """BOX01: the soft falling 'sutya' set-down.

    The original reverses the BOX02 contour: G4 down to E4, with the same
    filtered-noise body.  A low settle thump replaces the old high ping.
    """
    out: list[float] = []
    add(out, tone(783.99, 783.99, 0.045, shape="triangle",
                  amp=0.14, attack=0.002, decay=0.020), 0.0)
    add(out, noise_sweep(0.060, 0.060, 1_400.0, 380.0, q=1.1), 0.0)
    add(out, tone(783.99, 329.63, 0.115, shape="triangle",
                  amp=0.20, attack=0.004, decay=0.060), 0.025)
    add(out, noise_sweep(0.125, 0.12, 1_400.0, 320.0, q=1.1), 0.025)
    add(out, thump(0.10, 0.10), 0.095)
    return out


def make_menu_select() -> list[float]:
    """SEQ_SE_DP_DECIDE: the A-button click.

    The HGSS sample is a blunt low-mid click with a fast high transient,
    not a ceramic bell.  We keep it short enough for repeated UI use.
    """
    out: list[float] = []
    add(out, noise_sweep(0.085, 0.18, 1_000.0, 280.0, q=1.2), 0.0)
    add(out, tone(170.0, 132.0, 0.055, shape="sine",
                  amp=0.27, attack=0.001, decay=0.022), 0.0)
    # DECIDE plays the low click sample at B5, then B6.  Keep a short
    # pitched tick inside the low-passed body so it reads as the A press.
    add(out, tone(987.77, 987.77, 0.024, shape="triangle",
                  amp=0.085, attack=0.001, decay=0.010), 0.0)
    add(out, tone(1_975.5, 1_975.5, 0.016, shape="sine",
                  amp=0.030, attack=0.001, decay=0.007), 0.005)
    add(out, click(0.006, 0.06, 2_400.0), 0.0)
    return out


def make_cursor() -> list[float]:
    """SE_CONFIRM / SELECT: the very short high grid tick."""
    out: list[float] = []
    add(out, tone(3_729.0, 3_729.0, 0.030, shape="square",
                  amp=0.11, attack=0.001, decay=0.008), 0.0)
    add(out, tone(6_272.0, 6_272.0, 0.022, shape="sine",
                  amp=0.055, attack=0.001, decay=0.006), 0.0)
    add(out, click(0.007, 0.06, 5_000.0), 0.0)
    return out


def make_ui_click() -> list[float]:
    out: list[float] = []
    add(out, noise_sweep(0.070, 0.10, 1_500.0, 500.0, q=1.0), 0.0)
    add(out, tone(220.0, 180.0, 0.035, shape="sine",
                  amp=0.14, decay=0.014), 0.0)
    add(out, click(0.006, 0.05, 3_200.0), 0.0)
    return out


def make_ui_confirm() -> list[float]:
    return make_menu_select()


def make_back() -> list[float]:
    out: list[float] = []
    add(out, click(0.012, 0.10, 1_600.0), 0.0)
    add(out, tone(1_050.0, 760.0, 0.10, shape="soft_square",
                  amp=0.26, attack=0.002, decay=0.045), 0.0)
    add(out, tone(760.0, 540.0, 0.11, shape="triangle",
                  amp=0.20, attack=0.002, decay=0.050), 0.055)
    return out


def make_open_short() -> list[float]:
    out: list[float] = []
    add(out, tone(620.0, 920.0, 0.16, shape="triangle",
                  amp=0.25, attack=0.004, decay=0.075), 0.0)
    add(out, note(1_240.0, 0.18, amp=0.10, decay=0.080), 0.035)
    return delay(out, 0.055, 0.10)


def make_close_short() -> list[float]:
    out: list[float] = []
    add(out, tone(920.0, 620.0, 0.16, shape="triangle",
                  amp=0.23, attack=0.003, decay=0.080), 0.0)
    add(out, note(460.0, 0.16, amp=0.08, decay=0.070), 0.0)
    return out


def make_page() -> list[float]:
    """A soft box-page flip: air and paper, not a ceramic bell."""
    out: list[float] = []
    add(out, noise_sweep(0.18, 0.16, 800.0, 3_200.0, q=0.8), 0.0)
    add(out, noise_sweep(0.14, 0.09, 2_800.0, 700.0, q=0.9), 0.025)
    add(out, thump(0.09, 0.055), 0.0)
    return out


def make_tab() -> list[float]:
    out: list[float] = []
    add(out, note(659.25, 0.13, amp=0.19, decay=0.055), 0.0)
    add(out, note(987.77, 0.13, amp=0.16, decay=0.055), 0.045)
    add(out, clink(2_100.0, 0.07, amp=0.13), 0.0)
    return out


def make_toggle() -> list[float]:
    out: list[float] = []
    add(out, clink(1_760.0, 0.07, amp=0.25), 0.0)
    add(out, clink(2_350.0, 0.07, amp=0.21), 0.045)
    return out


def make_warning() -> list[float]:
    out: list[float] = []
    add(out, tone(330.0, 330.0, 0.20, shape="soft_square",
                  amp=0.22, attack=0.006, decay=0.075), 0.0)
    add(out, tone(247.0, 247.0, 0.24, shape="soft_square",
                  amp=0.20, attack=0.006, decay=0.090), 0.105)
    add(out, click(0.014, 0.07, 1_300.0), 0.0)
    return out


def make_error() -> list[float]:
    """SEQ_SE_DP_BOX03: a blunt, low refusal buzz."""
    out: list[float] = []
    add(out, tone(172.0, 145.0, 0.34, shape="soft_square",
                  amp=0.23, attack=0.003, decay=0.16,
                  vibrato_hz=27.0, vibrato_cents=36.0), 0.0)
    add(out, tone(180.0, 152.0, 0.30, shape="saw",
                  amp=0.075, attack=0.003, decay=0.14,
                  vibrato_hz=27.0, vibrato_cents=30.0), 0.0)
    add(out, thump(0.20, 0.20), 0.0)
    add(out, click(0.020, 0.10, 900.0), 0.0)
    return out


def make_deposit() -> list[float]:
    out = make_pc_place()
    add(out, note(987.77, 0.20, amp=0.13, decay=0.070), 0.12)
    add(out, note(1_318.51, 0.22, amp=0.10, decay=0.080), 0.18)
    return delay(out, 0.07, 0.10)


def make_withdraw() -> list[float]:
    out = make_pc_pick()
    add(out, note(783.99, 0.16, amp=0.10, decay=0.060), 0.11)
    return delay(out, 0.06, 0.08)


def make_release() -> list[float]:
    out: list[float] = []
    add(out, noise_sweep(0.42, 0.13, 4_200.0, 260.0, q=0.7), 0.0)
    add(out, tone(440.0, 180.0, 0.38, shape="triangle",
                  amp=0.20, attack=0.004, decay=0.15), 0.0)
    add(out, note(880.0, 0.20, amp=0.08, decay=0.070), 0.0)
    add(out, thump(0.28, 0.15), 0.12)
    return out


def make_import() -> list[float]:
    out: list[float] = []
    for i, hz in enumerate((880.0, 1_108.73, 1_318.51)):
        add(out, tone(hz, hz, 0.11, shape="triangle",
                      amp=0.20, attack=0.003, decay=0.045), i * 0.055)
        add(out, clink(hz * 2.0, 0.06, amp=0.06), i * 0.055)
    add(out, noise_sweep(0.16, 0.035, 1_000.0, 6_000.0), 0.0)
    return out


def make_undo() -> list[float]:
    out: list[float] = []
    add(out, tone(1_250.0, 520.0, 0.16, shape="triangle",
                  amp=0.22, attack=0.003, decay=0.065,
                  vibrato_hz=18.0, vibrato_cents=20.0), 0.0)
    add(out, tone(620.0, 880.0, 0.14, shape="soft_square",
                  amp=0.12, attack=0.003, decay=0.055), 0.09)
    add(out, click(0.014, 0.08, 2_200.0), 0.0)
    return out


def make_editor_save() -> list[float]:
    out: list[float] = []
    for start, hz in ((0.0, 659.25), (0.09, 987.77), (0.18, 1_318.51)):
        add(out, note(hz, 0.32, amp=0.18, decay=0.105), start)
    add(out, note(2_637.0, 0.22, amp=0.045, decay=0.085), 0.18)
    return delay(out, 0.09, 0.13)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main() -> int:
    cues = {
        # Bill's PC
        "pc_open": make_pc_open,
        "pc_close": make_pc_close,
        "pc_cursor": make_cursor,
        "pc_pick": make_pc_pick,
        "pc_place": make_pc_place,
        "pc_cancel": make_back,
        "pc_box": make_page,
        "pc_deposit": make_deposit,
        "pc_withdraw": make_withdraw,
        "pc_release": make_release,
        "pc_import": make_import,
        "pc_undo": make_undo,
        "pc_error": make_error,
        # Shared UI
        "menu_move": make_cursor,
        "menu_select": make_menu_select,
        "ui_click": make_ui_click,
        "ui_confirm": make_ui_confirm,
        "ui_back": make_back,
        "ui_open": make_open_short,
        "ui_close": make_close_short,
        "ui_page": make_page,
        "ui_tab": make_tab,
        "ui_toggle": make_toggle,
        "ui_warning": make_warning,
        "ui_error": make_error,
        # Editor
        "editor_open": make_open_short,
        "editor_save": make_editor_save,
    }
    # The login/logout notes are deliberately quieter than a UI click so they
    # sit under the game's music instead of stinging.  Per-cue peaks also stop
    # one long cue from setting the whole kit's loudness.
    peaks = {
        "pc_open": 0.62,
        "pc_close": 0.68,
        "pc_pick": 0.80,
        "pc_place": 0.80,
        "pc_cursor": 0.62,
        "menu_move": 0.62,
        "menu_select": 0.75,
        "ui_click": 0.66,
        "ui_confirm": 0.75,
        "pc_box": 0.74,
        "ui_page": 0.74,
    }
    # The retail SWAVs are much darker than a raw oscillator/noise sketch:
    # BOX01/02 sit around 1 kHz with an 85% roll-off near 1.25 kHz, and
    # DECIDE is a low thud.  These filters remove the fizzy top end that made
    # the first kit sound synthetic while preserving the transient.
    cutoffs = {
        "pc_open": 6_500.0,
        "pc_close": 6_000.0,
        "pc_pick": 3_000.0,
        "pc_place": 2_800.0,
        "pc_cursor": 9_000.0,
        "menu_move": 9_000.0,
        "menu_select": 2_200.0,
        "ui_click": 2_600.0,
        "ui_confirm": 2_200.0,
        "pc_box": 3_500.0,
        "ui_page": 3_500.0,
    }
    for name, factory in cues.items():
        path = write(
            name,
            factory(),
            peak=peaks.get(name, 0.9),
            cutoff=cutoffs.get(name, 16_500.0),
        )
        print(f"{path.relative_to(ROOT)}")
    print(f"{len(cues)} cues written to {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
