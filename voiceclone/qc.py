"""Quality gate: transcribe every take and compare it with the script.

Listening to 2,000 lines is not a plan. This flags the handful worth a human ear:
skipped words, repeated words, a line read in the wrong language.

Needs the optional extra:  pip install "local-voice-clone[qc]"
"""
from __future__ import annotations

import re
from pathlib import Path

# Arabic-script variants that Whisper mixes freely when it writes Urdu.
_URDU_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ە": "ہ", "ۃ": "ہ", "ۓ": "ے",
    "أ": "ا", "إ": "ا", "ؤ": "و", "ھ": "ہ",
})
_DIACRITICS = re.compile(r"[ً-ٰٟ‌-‏]")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, spaces and diacritics, fold Urdu letter variants."""
    text = _DIACRITICS.sub("", text or "").translate(_URDU_MAP)
    return re.sub(r"[^\w]|_", "", text).lower()


def levenshtein(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer(reference: str, heard: str) -> float:
    """Character error rate after normalising. 0.0 = perfect, 1.0 = nothing matched."""
    ref, hyp = normalise(reference), normalise(heard)
    return round(levenshtein(ref, hyp) / max(1, len(ref)), 3)


def wer(reference: str, heard: str) -> float:
    """Word error rate on lowercase words."""
    ref = re.findall(r"[\w']+", reference.lower())
    hyp = re.findall(r"[\w']+", heard.lower())
    return round(levenshtein(ref, hyp) / max(1, len(ref)), 3)


def load_whisper(model: str = "small", device: str = "cpu"):
    """CPU by default: it always works and `small` is quick. Pass device="cuda" if your
    faster-whisper install has working CUDA libraries."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover - depends on optional extra
        raise RuntimeError('QC needs faster-whisper: pip install "local-voice-clone[qc]"') from e
    compute = "float16" if device == "cuda" else "int8"
    return WhisperModel(model, device=device, compute_type=compute)


def transcribe(whisper, wav: str | Path, lang: str = "en") -> str:
    # Decode the WAV here and hand Whisper a 16 kHz array: no dependency on its audio decoder.
    import numpy as np

    from .audio import read_wav

    data, rate = read_wav(wav)
    if rate != 16000 and data.size:
        target = np.arange(int(data.size * 16000 / rate)) * (rate / 16000.0)
        data = np.interp(target, np.arange(data.size), data).astype(np.float32)
    segments, _ = whisper.transcribe(
        data, language=lang, vad_filter=False, beam_size=5, condition_on_previous_text=False
    )
    return " ".join(s.text for s in segments).strip()


def check(jobs: list[dict], model: str = "small", device: str = "cpu", threshold: float = 0.35) -> list[dict]:
    """jobs = [{wav, text, lang}] -> same dicts plus heard, cer, flag.

    English words inside an Urdu line come back in Latin script and inflate CER, so the
    default threshold is loose: a flag means "listen to this one", not "this one is wrong".
    """
    whisper = load_whisper(model, device)
    results = []
    for job in jobs:
        heard = transcribe(whisper, job["wav"], job.get("lang", "en"))
        score = cer(job["text"], heard)
        results.append({**job, "wav": str(job["wav"]), "heard": heard, "cer": score, "flag": score > threshold})
    return results
