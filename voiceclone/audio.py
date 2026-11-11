"""WAV helpers: read, write, edge trim, fades, and joining takes into one clean track."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a PCM WAV as mono float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"{path}: unsupported sample width {width * 8} bit (convert with ffmpeg to 16 bit PCM)")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def write_wav(path: str | Path, data: np.ndarray, rate: int) -> None:
    """Write mono float audio as 16 bit PCM."""
    pcm = (np.clip(data, -1.0, 1.0) * 32767.0).astype("<i2")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def wav_seconds(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def trim_edges(data: np.ndarray, rate: int, threshold_db: float = -45.0, keep_ms: int = 40) -> np.ndarray:
    """Cut leading and trailing near-silence, keeping a small pad so words are not clipped."""
    if data.size == 0:
        return data
    limit = 10 ** (threshold_db / 20.0)
    loud = np.flatnonzero(np.abs(data) > limit)
    if loud.size == 0:
        return data[:0]
    pad = int(rate * keep_ms / 1000)
    return data[max(0, loud[0] - pad): min(data.size, loud[-1] + pad + 1)]


def fade(data: np.ndarray, rate: int, ms: int = 12) -> np.ndarray:
    """Short fade in and out. Without it every join between takes clicks."""
    n = min(int(rate * ms / 1000), data.size // 2)
    if n <= 0:
        return data
    out = data.astype(np.float32).copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def room_tone(samples: int, level_db: float = -62.0, seed: int = 0) -> np.ndarray:
    """Low, smoothed noise bed. Pure digital silence between sentences is an instant AI tell."""
    if samples <= 0:
        return np.zeros(0, dtype=np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(samples + 8).astype(np.float32)
    noise = np.convolve(noise, np.ones(8, dtype=np.float32) / 8.0, mode="valid")[:samples]
    peak = float(np.max(np.abs(noise))) or 1.0
    return noise / peak * (10 ** (level_db / 20.0))


def _tile(bed: np.ndarray, samples: int) -> np.ndarray:
    if bed.size == 0:
        return np.zeros(samples, dtype=np.float32)
    reps = int(np.ceil(samples / bed.size))
    return np.tile(bed, reps)[:samples].astype(np.float32)


def join(
    paths: list[str | Path],
    out: str | Path,
    pause_s: float = 0.45,
    speaker_pause_s: float = 0.7,
    speakers: list[str] | None = None,
    tone_db: float | None = -62.0,
    tone_file: str | Path | None = None,
) -> float:
    """Join takes into one track: trim edges, fade each take, pause between, bed of room tone.

    speakers (one name per path) makes the pause longer when the speaker changes.
    tone_file (a recording of your real empty room) beats generated tone if you have one.
    Returns the length of the result in seconds.
    """
    if not paths:
        raise ValueError("nothing to join")
    parts: list[np.ndarray] = []
    rate = 0
    for i, path in enumerate(paths):
        data, r = read_wav(path)
        if rate and r != rate:
            raise ValueError(f"{path}: sample rate {r} differs from {rate}")
        rate = r
        data = fade(trim_edges(data, rate), rate)
        if i:
            changed = bool(speakers) and speakers[i] != speakers[i - 1]
            gap = speaker_pause_s if changed else pause_s
            parts.append(np.zeros(int(rate * gap), dtype=np.float32))
        parts.append(data)
    track = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    if tone_file:
        bed, bed_rate = read_wav(tone_file)
        if bed_rate != rate:
            raise ValueError(f"{tone_file}: sample rate {bed_rate} differs from the takes ({rate})")
        track = track + _tile(bed, track.size)
    elif tone_db is not None:
        track = track + room_tone(track.size, tone_db)
    write_wav(out, track, rate)
    return track.size / float(rate) if rate else 0.0
