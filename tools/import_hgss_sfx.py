#!/usr/bin/env python3
"""Deprecated approximate renderer for the HGSS PC cues.

The bundled bank at assets/sound/sfx is now rendered with the kode54 SSEQ
player, which handles portamento.  This earlier Python renderer does not, and
its output is the wrong "!"-like pickup cue.  It writes to soundpack/sfx_synth
by default so it cannot overwrite the real cues; use it only for comparison.

The five cues FRLG Studio uses for Bill's PC are SSEQ sequences, not plain WAV
files:

    SEQ_SE_DP_PC_LOGIN      1548   -> pc_open.wav
    SEQ_SE_DP_PC_LOGOFF     1549   -> pc_close.wav
    SEQ_SE_DP_BOX02         1515   -> pc_pick.wav
    SEQ_SE_DP_BOX01         1514   -> pc_place.wav
    SEQ_SE_DP_DECIDE        1501   -> menu_select.wav

This tool reads the `gs_sound_data.sdat` from your own dumped copy (the
pret/pokeheartgold decomp also carries a copy), decodes its SWAV samples,
applies the sequence events, and writes the five WAVs into the writable
soundpack.  It does not ship, copy or read any audio from this repository.

Install the one Python dependency:

    venv/bin/pip install 'ndspy==4.2.0'

Then run:

    venv/bin/python tools/import_hgss_sfx.py /path/to/gs_sound_data.sdat

By default the output goes to the same `soundpack/sfx` folder the app reads.
Use `--out DIR` to render into a scratch directory first.  Existing files are
left alone unless `--force` is passed.  Reload the pack in SOUND SETTINGS
after installing.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from ndspy.soundArchive import SDAT
    from ndspy.soundBank import RegionalInstrument, SingleNoteInstrument
except ImportError:  # pragma: no cover - exercised only on a fresh checkout
    SDAT = None
    RegionalInstrument = None
    SingleNoteInstrument = None

import paths

RATE = 44_100
TICKS_PER_BEAT = 48

# Cues this PC UI actually calls.
SEQUENCES = {
    "pc_open": ("SEQ_SE_DP_PC_LOGIN", 1548),
    "pc_close": ("SEQ_SE_DP_PC_LOGOFF", 1549),
    "pc_pick": ("SEQ_SE_DP_BOX02", 1515),
    "pc_place": ("SEQ_SE_DP_BOX01", 1514),
    "menu_select": ("SEQ_SE_DP_DECIDE", 1501),
}

# Nintendo DS IMA-ADPCM tables.
_STEP = (
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130,
    143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408,
    449, 494, 544, 598, 658, 724, 796, 876, 963, 1_060, 1_166,
    1_282, 1_411, 1_552, 1_707, 1_878, 2_066, 2_272, 2_499, 2_749,
    3_024, 3_327, 3_660, 4_026, 4_428, 4_871, 5_358, 5_894, 6_484,
    7_132, 7_845, 8_630, 9_493, 10_442, 11_487, 12_635, 13_899,
    15_289, 16_818, 18_500, 20_350, 22_385, 24_623, 27_086,
    29_794, 32_767,
)
_INDEX = (-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8)


@dataclass
class Note:
    start: float
    duration: float
    pitch: int
    velocity: int
    instrument: int
    volume: int


@dataclass
class Parsed:
    notes: list[Note]
    volume_events: list[tuple[float, int]]
    bank_id: int
    sequence_volume: int
    vibrato_depth: int = 0


@dataclass
class Sample:
    pcm: list[float]
    rate: int
    loop_start: int | None = None


@dataclass
class Voice:
    sample: Sample | None
    base_pitch: int
    is_psg: bool
    duty: float
    attack: float
    decay: float
    sustain: float
    release: float


def _load_sdat(path: Path):
    if SDAT is None:
        raise SystemExit(
            "ndspy is not installed.  Run:\n"
            "  venv/bin/pip install 'ndspy==4.2.0'\n"
            "then run this tool again."
        )
    return SDAT.fromFile(str(path))


def _find_sequence(sdat, name: str, index: int):
    if 0 <= index < len(sdat.sequences):
        candidate = sdat.sequences[index]
        if candidate and candidate[0] == name:
            return candidate[1]
    for candidate in sdat.sequences:
        if candidate and candidate[0] == name:
            return candidate[1]
    raise SystemExit(f"SDAT does not contain {name} (#{index}).")


def _tick_seconds(tempo: int) -> float:
    return 60.0 / (tempo * TICKS_PER_BEAT)


def _parse(seq) -> Parsed:
    seq.parse()
    tempo = 120
    instrument = 0
    track_volume = 127
    vibrato_depth = 0
    now = 0.0
    notes: list[Note] = []
    volume_events: list[tuple[float, int]] = []
    for event in seq.events:
        kind = type(event).__name__
        if kind == "TempoSequenceEvent":
            tempo = event.value
        elif kind == "InstrumentSwitchSequenceEvent":
            instrument = event.instrumentID
        elif kind == "TrackVolumeSequenceEvent":
            track_volume = event.value
            volume_events.append((now, track_volume))
        elif kind == "VibratoDepthSequenceEvent":
            vibrato_depth = event.value
        elif kind == "NoteSequenceEvent":
            duration = event.duration * _tick_seconds(tempo)
            notes.append(
                Note(
                    start=now,
                    duration=duration,
                    pitch=event.type,
                    velocity=event.velocity,
                    instrument=instrument,
                    volume=track_volume,
                )
            )
            now += duration
        elif kind == "RestSequenceEvent":
            now += event.duration * _tick_seconds(tempo)
        elif kind == "EndTrackSequenceEvent":
            break
    return Parsed(
        notes=notes,
        volume_events=volume_events,
        bank_id=seq.bankID,
        sequence_volume=seq.volume,
        vibrato_depth=vibrato_depth,
    )


def _decode_swav(swav) -> Sample:
    wave_type = int(swav.waveType)
    data = swav.data
    if wave_type == 0:  # signed 8-bit PCM
        pcm = [value / 128.0 for value in struct.unpack(f"<{len(data)}b", data)]
        loop = swav.loopOffset if swav.isLooped else None
    elif wave_type == 1:  # signed 16-bit PCM
        count = len(data) // 2
        pcm = [value / 32_768.0 for value in struct.unpack(f"<{count}h", data)]
        loop = swav.loopOffset if swav.isLooped else None
    elif wave_type == 2:  # IMA-ADPCM, one 4-byte header then 4-bit nibbles
        if len(data) < 4:
            return Sample([], swav.sampleRate, None)
        initial, index, _ = struct.unpack_from("<hBB", data, 0)
        sample = initial
        index = max(0, min(88, index))
        pcm: list[float] = []
        for byte in data[4:]:
            for nibble in (byte & 0x0F, byte >> 4):
                step = _STEP[index]
                delta = step >> 3
                if nibble & 1:
                    delta += step >> 2
                if nibble & 2:
                    delta += step >> 1
                if nibble & 4:
                    delta += step
                sample += -delta if nibble & 8 else delta
                sample = max(-32_768, min(32_767, sample))
                index = max(0, min(88, index + _INDEX[nibble]))
                pcm.append(sample / 32_768.0)
        # ADPCM lengths are in 4-byte words including the 4-byte header.
        loop = None
        if swav.isLooped:
            loop = max(0, (int(swav.loopOffset) - 1) * 8)
    else:
        raise SystemExit(f"Unsupported SWAV encoding: {wave_type}")

    if loop is not None and loop >= len(pcm):
        loop = None
    return Sample(pcm, int(swav.sampleRate), loop)


def _note_definition(bank, instrument_id: int, pitch: int):
    if instrument_id >= len(bank.instruments):
        raise SystemExit(f"Instrument {instrument_id} is missing from the bank.")
    instrument = bank.instruments[instrument_id]
    if isinstance(instrument, SingleNoteInstrument):
        return instrument.noteDefinition
    if isinstance(instrument, RegionalInstrument):
        for region in instrument.regions:
            if pitch <= region.lastPitch:
                return region.noteDefinition
    raise SystemExit(f"Instrument {instrument_id} has no usable note definition.")


def _voice(sdat, bank, instrument_id: int, pitch: int) -> Voice:
    note = _note_definition(bank, instrument_id, pitch)
    if int(note.type) == 2:  # PSG square wave
        # Duty cycle 0..7 maps to 12.5%..100%; value 3 is the 50% square.
        duty = ((note.dutyCycle & 7) + 1) / 8.0
        return Voice(None, note.pitch, True, duty, 0.003, 0.12, 0.315, 0.06)
    if int(note.type) != 1:
        raise SystemExit(f"Instrument {instrument_id} is not PCM or PSG square.")

    archive_slot = note.waveArchiveIDID
    archive_id = (
        bank.waveArchiveIDs[archive_slot]
        if 0 <= archive_slot < len(bank.waveArchiveIDs)
        else archive_slot
    )
    archive = sdat.waveArchives[archive_id][1]
    swav = archive.waves[note.waveID]
    sample = _decode_swav(swav)

    # Envelope rates are not milliseconds in the format.  These mappings are
    # deliberately short and conservative; the sample's own envelope carries
    # most of the character.
    if note.sustain >= 120:
        decay = 10.0
        sustain = 1.0
    else:
        decay = max(0.01, (127 - note.decay) * 0.0012)
        sustain = note.sustain / 127.0
    release = max(0.008, (127 - note.release) * 0.0008)
    attack = max(0.001, (127 - note.attack) * 0.0002)
    return Voice(sample, note.pitch, False, 0.5, attack, decay, sustain, release)


def _volume_at(events: list[tuple[float, int]], time: float) -> int:
    value = 127
    for at, candidate in events:
        if at > time:
            break
        value = candidate
    return value


def _envelope(voice: Voice, time: float, note_length: float) -> float:
    if time < voice.attack:
        gain = time / voice.attack
    elif time < voice.attack + voice.decay:
        gain = 1.0 + (voice.sustain - 1.0) * (
            (time - voice.attack) / voice.decay
        )
    else:
        gain = voice.sustain
    if time > note_length:
        gain *= max(0.0, 1.0 - (time - note_length) / voice.release)
    return gain


def _sample_at(sample: Sample, position: float) -> float:
    if not sample.pcm:
        return 0.0
    if position >= len(sample.pcm):
        if sample.loop_start is None:
            return 0.0
        length = len(sample.pcm) - sample.loop_start
        if length <= 0:
            return 0.0
        position = sample.loop_start + (position - sample.loop_start) % length
    index = int(position)
    fraction = position - index
    if index + 1 >= len(sample.pcm):
        return sample.pcm[index]
    return sample.pcm[index] * (1.0 - fraction) + sample.pcm[index + 1] * fraction


def _add(buf: list[float], offset: int, value: float) -> None:
    if 0 <= offset < len(buf):
        buf[offset] += value


def _render_psg(parsed: Parsed) -> list[float]:
    if not parsed.notes:
        return []
    end = max(note.start + note.duration for note in parsed.notes) + 0.09
    buf = [0.0] * int(end * RATE)
    for note in parsed.notes:
        voice = Voice(
            sample=None,
            base_pitch=note.pitch,
            is_psg=True,
            duty=0.5,
            attack=0.003,
            decay=0.12,
            sustain=0.315,
            release=0.06,
        )
        length = note.duration + voice.release
        amplitude = (
            (note.velocity / 127.0)
            * (note.volume / 127.0)
            * (parsed.sequence_volume / 127.0)
        )
        phase = 0.0
        start = int(note.start * RATE)
        for i in range(int(length * RATE)):
            t = i / RATE
            frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
            if parsed.vibrato_depth:
                # A light default vibrato; the SSEQ only stores the depth.
                frequency *= 2.0 ** (
                    (parsed.vibrato_depth / 1200.0)
                    * math.sin(math.tau * 5.5 * t)
                )
            phase = (phase + frequency / RATE) % 1.0
            wave_value = 1.0 if phase < voice.duty else -1.0
            gain = _envelope(voice, t, note.duration)
            _add(buf, start + i, amplitude * gain * wave_value)
    return buf


def _render_pcm_notes(sdat, parsed: Parsed) -> list[float]:
    bank = sdat.banks[parsed.bank_id][1]
    if not parsed.notes:
        return []
    end = max(note.start + note.duration for note in parsed.notes) + 0.08
    buf = [0.0] * int(end * RATE)
    for note in parsed.notes:
        voice = _voice(sdat, bank, note.instrument, note.pitch)
        if voice.sample is None:
            continue
        base_freq = 440.0 * 2.0 ** ((voice.base_pitch - 69) / 12.0)
        frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
        ratio = (frequency / base_freq) * (voice.sample.rate / RATE)
        amplitude = (
            (note.velocity / 127.0)
            * (_volume_at(parsed.volume_events, note.start) / 127.0)
            * (parsed.sequence_volume / 127.0)
        )
        start = int(note.start * RATE)
        length = note.duration + voice.release
        position = 0.0
        for i in range(int(length * RATE)):
            t = i / RATE
            value = _sample_at(voice.sample, position)
            gain = _envelope(voice, t, note.duration)
            _add(buf, start + i, amplitude * gain * value)
            position += ratio
    return buf


def _render_box(sdat, parsed: Parsed) -> list[float]:
    """Render BOX01/BOX02 as two sample hits, not a full-interval glide.

    The sequence has an E3/G4 pair with a short rest between them.  Treating
    that as one continuous glide turns the low sample into a rising siren
    (the "!" exclamation); the actual cue retriggers the sample for the second
    note.  The 2-semitone portamento is a small bend, not the whole interval.
    """
    return _render_pcm_notes(sdat, parsed)


def _trim(buf: list[float]) -> list[float]:
    threshold = 0.0005
    end = len(buf)
    while end > 0 and abs(buf[end - 1]) < threshold:
        end -= 1
    if end < len(buf):
        end = min(len(buf), end + int(0.02 * RATE))
    return buf[:end]


def _lowpass(buf: list[float], cutoff: float) -> list[float]:
    if cutoff >= RATE * 0.45:
        return buf
    alpha = 1.0 - math.exp(-math.tau * cutoff / RATE)
    value = 0.0
    out = []
    for sample in buf:
        value += alpha * (sample - value)
        out.append(value)
    return out


def _finish(buf: list[float], *, cutoff: float = 16_000.0, peak: float = 0.86) -> list[float]:
    buf = _lowpass(buf, cutoff)
    if cutoff < 6_000.0:
        buf = _lowpass(buf, cutoff)
    buf = _trim(buf)
    if not buf:
        return buf
    top = max(abs(value) for value in buf)
    if top > 0:
        buf = [value * (peak / top) for value in buf]
    fade = min(len(buf) // 2, int(0.0015 * RATE))
    for i in range(fade):
        buf[i] *= i / fade
        buf[-1 - i] *= i / fade
    return buf


def _write(path: Path, buf: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        frames = bytearray()
        for value in buf:
            integer = int(max(-1.0, min(1.0, value)) * 32_767)
            frames.extend(integer.to_bytes(2, "little", signed=True))
        handle.writeframes(bytes(frames))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("sdat", type=Path, help="your gs_sound_data.sdat")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default: the app's soundpack/sfx)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing cue files",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the sequences this tool will render and exit",
    )
    args = parser.parse_args()

    sdat = _load_sdat(args.sdat)
    if args.list:
        for cue, (name, index) in SEQUENCES.items():
            try:
                _find_sequence(sdat, name, index)
                found = "found"
            except SystemExit:
                found = "MISSING"
            print(f"{cue:12s} {name:22s} {index:4d}  {found}")
        return 0

    out_dir = args.out or (paths.SOUNDPACK_DIR / "sfx_synth")
    out_dir.mkdir(parents=True, exist_ok=True)

    for cue, (name, index) in SEQUENCES.items():
        destination = out_dir / f"{cue}.wav"
        if destination.exists() and not args.force:
            print(f"{destination} exists; use --force to replace it")
            continue
        seq = _find_sequence(sdat, name, index)
        parsed = _parse(seq)
        if cue in ("pc_open", "pc_close"):
            buffer = _render_psg(parsed)
            # The DS square is bright; a gentle 3.5 kHz roll-off keeps the
            # two-note "boop" from turning into a piercing beep.
            cutoff = 3_500.0
            level = 0.66
        elif cue in ("pc_pick", "pc_place"):
            buffer = _render_box(sdat, parsed)
            cutoff = 12_000.0
            level = 0.86
        else:
            buffer = _render_pcm_notes(sdat, parsed)
            cutoff = 12_000.0
            level = 0.80
        buffer = _finish(buffer, cutoff=cutoff, peak=level)
        if not buffer:
            print(f"{cue}: no audio rendered")
            continue
        _write(destination, buffer)
        print(f"{destination}  {len(buffer) / RATE:.3f}s")

    print("\nDone.  In the app, open SOUND SETTINGS and choose RELOAD PACK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
