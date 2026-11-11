"""Text preparation: respelling, chunking, script parsing, length estimates."""
from __future__ import annotations

import json
import re
from pathlib import Path

# Words a TTS model reads badly. Extend with your own JSON file (see examples/respell.json).
DEFAULT_RESPELL = {
    "n8n": "N, eight, N",
}

# Characters of text per second of speech, measured on Higgs Audio v3 output.
CHARS_PER_SEC = {"en": 14.0, "ur": 12.8}

_SPEAKER = re.compile(r"^\s*([A-Za-z0-9_\-]{1,32})\s*:\s+(.+)$")
_SENTENCE_END = re.compile(r"(?<=[.!?۔؟])\s+")


def load_respell(path: str | Path | None) -> dict[str, str]:
    """Default table merged with an optional JSON file of {"word": "how to say it"}."""
    table = dict(DEFAULT_RESPELL)
    if path:
        extra = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(extra, dict):
            raise ValueError(f"{path}: respell file must be a JSON object")
        table.update({str(k): str(v) for k, v in extra.items()})
    return table


def respell(text: str, table: dict[str, str] | None = None) -> str:
    """Swap hard-to-pronounce words for a spoken spelling. Whole words only, case-insensitive."""
    table = DEFAULT_RESPELL if table is None else table
    for word in sorted(table, key=len, reverse=True):
        pattern = r"(?<![\w])" + re.escape(word) + r"(?![\w])"
        text = re.sub(pattern, lambda _m, w=word: table[w], text, flags=re.IGNORECASE)
    return text


def split_chunks(text: str, max_chars: int = 320) -> list[str]:
    """Split long text into sentence-aligned chunks no longer than max_chars.

    Short chunks keep the model stable: long inputs are where runaway generations start.
    """
    text = " ".join(text.split())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > max_chars:  # one giant sentence: break on a space
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def expected_secs(text: str, lang: str = "en") -> float:
    """Rough spoken duration of a line. Used to size the token budget and spot runaway takes."""
    return max(1.0, len(text) / CHARS_PER_SEC.get(lang, CHARS_PER_SEC["en"]))


def duration_ok(seconds: float, text: str, lang: str = "en") -> bool:
    """True when a take is neither cut short nor a looping runaway."""
    expected = expected_secs(text, lang)
    return 0.35 * expected <= seconds <= 2.6 * expected + 1.0


def max_tokens_for(texts: list[str], lang: str = "en", attempt: int = 0) -> int:
    """Token budget for a batch: enough for the longest line, capped so a runaway stops early."""
    longest = max(expected_secs(t, lang) for t in texts)
    return int(min(6000, max(900, (2.6 * longest + 2) * 60 * (1 + attempt))))


def parse_script(raw: str, default_voice: str) -> list[tuple[str, str]]:
    """Turn a script into [(voice, text)].

    One line of speech per line. `name: text` switches speaker, plain lines use default_voice.
    Blank lines and lines starting with # are skipped.
    """
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SPEAKER.match(line)
        if match:
            out.append((match.group(1).lower(), match.group(2).strip()))
        else:
            out.append((default_voice, line))
    return out
