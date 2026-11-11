"""Runs Higgs Audio v3 through the audio.cpp CLI, with the retry logic that makes it usable.

Why the retry logic exists: every so often the model never emits its end token for a line and
keeps generating ("runaway"). In a batch that kills every line after it. So:

  1. run the whole batch in one process (the 4 GB model loads once)
  2. keep every good take that came before the first missing file
  3. retry the culprit line alone with a new seed and a bigger token budget
  4. put the lines after it back in the queue and go again

Takes whose length is far off the expected speaking time are treated the same way.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .audio import wav_seconds
from .text import duration_ok, max_tokens_for

SEED_STEP = 7919  # a prime, so retry seeds never collide with the base seeds people pick


class SetupError(RuntimeError):
    """audio.cpp, the model, or a voice reference is missing."""


def default_cli() -> str:
    exe = "audiocpp_cli.exe" if os.name == "nt" else "audiocpp_cli"
    return os.environ.get("AUDIOCPP_CLI") or shutil.which(exe) or shutil.which("audiocpp_cli") or ""


def default_model() -> str:
    return os.environ.get("HIGGS_GGUF", "")


@dataclass
class Voice:
    """A voice = a short clean clip plus the exact words spoken in it."""

    name: str
    wav: Path
    text: str

    @classmethod
    def load(cls, name: str, voices_dir: str | Path = "voices") -> "Voice":
        base = Path(voices_dir)
        wav, txt = base / f"{name}.wav", base / f"{name}.txt"
        if not wav.exists() or not txt.exists():
            raise SetupError(
                f"voice '{name}' not found: need {wav} and {txt}. Make one with: voiceclone ref --help"
            )
        text = " ".join(txt.read_text(encoding="utf-8").split())
        if not text:
            raise SetupError(f"{txt} is empty: it must hold the exact words spoken in {wav.name}")
        return cls(name, wav, text)


@dataclass
class Stats:
    lines: int = 0
    retries: int = 0
    failed: list[str] = field(default_factory=list)
    gen_s: float = 0.0
    audio_s: float = 0.0

    @property
    def rtf(self) -> float | None:
        """Seconds of compute per second of audio. Below 1.0 = faster than real time."""
        return round(self.gen_s / self.audio_s, 2) if self.audio_s else None


# runner(texts, voice, seed, max_tokens, workdir) -> one wav path (or None) per input line
Runner = Callable[[list[str], Voice, int, int, Path], list]


class Engine:
    def __init__(
        self,
        cli: str | None = None,
        model: str | None = None,
        backend: str = "best",
        threads: int = 3,
        temperature: float = 0.7,
        seed: int = 7,
        retries: int = 3,
        batch: int = 40,
        log: Callable[[str], None] = print,
        runner: Runner | None = None,
    ):
        self.cli = cli or default_cli()
        self.model = model or default_model()
        self.backend, self.threads, self.temperature = backend, threads, temperature
        self.seed, self.retries, self.batch, self.log = seed, retries, batch, log
        self.stats = Stats()
        self._runner = runner or self._run_cli

    # ------------------------------------------------------------------ checks
    def check(self) -> None:
        if not self.cli or not Path(self.cli).exists():
            raise SetupError(
                "audio.cpp CLI not found. Set AUDIOCPP_CLI to the full path of audiocpp_cli "
                "(see docs/SETUP.md)."
            )
        if not self.model or not Path(self.model).exists():
            raise SetupError(
                "Higgs model not found. Set HIGGS_GGUF to the full path of "
                "higgs-audio-v3-tts-4b-q8_0.gguf (see docs/SETUP.md)."
            )

    # ------------------------------------------------------------------ one CLI process
    def _run_cli(self, texts: list[str], voice: Voice, seed: int, max_tokens: int, workdir: Path) -> list:
        infile = workdir / "in.txt"
        infile.write_text("\n".join(t.replace("\n", " ") for t in texts) + "\n", encoding="utf-8")
        outdir = workdir / "o"
        cmd = [
            self.cli, "--task", "tts", "--family", "higgs_audio_tts", "--model", self.model,
            "--backend", self.backend, "--threads", str(self.threads),
            "--batch-text-file", str(infile), "--out-dir", str(outdir),
            "--voice-ref", str(voice.wav), "--reference-text", voice.text,
            "--request-option", f"seed={seed}",
            "--request-option", f"temperature={self.temperature}",
            "--max-tokens", str(max_tokens), "--metrics",
        ]
        # Below-normal priority so the machine stays usable while it voices a long script.
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) if os.name == "nt" else 0
        with open(workdir / "log.txt", "ab") as logfile:
            subprocess.run(cmd, stdout=logfile, stderr=logfile, creationflags=flags, check=False)
        found = []
        for i in range(len(texts)):
            f = outdir / f"line_{i + 1}.wav"
            found.append(f if f.exists() and f.stat().st_size > 1000 else None)
        return found

    def _run(self, texts: list[str], voice: Voice, seed: int, max_tokens: int):
        workdir = Path(tempfile.mkdtemp(prefix="voiceclone_"))
        started = time.time()
        outs = self._runner(texts, voice, seed, max_tokens, workdir)
        self.stats.gen_s += time.time() - started
        return outs, workdir

    # ------------------------------------------------------------------ public
    def synth(self, voice: Voice, texts: list[str], out_paths: list[str | Path], lang: str = "en") -> bool:
        """Voice every text into its out path. True when all lines produced a good take."""
        if len(texts) != len(out_paths):
            raise ValueError("texts and out_paths must be the same length")
        items = [(t, Path(p)) for t, p in zip(texts, out_paths)]
        failed: list[tuple[str, Path]] = []
        for start in range(0, len(items), self.batch):
            failed += self._synth_group(voice, items[start:start + self.batch], lang)
            done = min(start + self.batch, len(items))
            self.log(f"[{voice.name}] {done}/{len(items)} lines, retries {self.stats.retries}, RTF {self.stats.rtf}")
        for text, _ in failed:
            self.stats.failed.append(text)
            self.log(f"[{voice.name}] FAILED after {self.retries} retries: {text[:70]!r}")
        return not failed

    # ------------------------------------------------------------------ internals
    def _keep(self, take, text: str, dest: Path, lang: str) -> bool:
        if take is None:
            return False
        try:
            seconds = wav_seconds(take)
        except Exception:
            return False
        if not duration_ok(seconds, text, lang):
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(take, dest)
        self.stats.lines += 1
        self.stats.audio_s += seconds
        return True

    def _alone(self, voice: Voice, item: tuple[str, Path], lang: str) -> bool:
        text, dest = item
        for attempt in range(1, self.retries + 1):
            self.stats.retries += 1
            seed = self.seed + attempt * SEED_STEP
            outs, workdir = self._run([text], voice, seed, max_tokens_for([text], lang, attempt))
            good = self._keep(outs[0], text, dest, lang)
            shutil.rmtree(workdir, ignore_errors=True)
            if good:
                return True
        return False

    def _synth_group(self, voice: Voice, items: list[tuple[str, Path]], lang: str) -> list[tuple[str, Path]]:
        failed: list[tuple[str, Path]] = []
        queue = list(items)
        while queue:
            texts = [t for t, _ in queue]
            outs, workdir = self._run(texts, voice, self.seed, max_tokens_for(texts, lang))
            first_missing = next((i for i, o in enumerate(outs) if o is None), None)
            upto = len(queue) if first_missing is None else first_missing
            bad = [item for item, take in zip(queue[:upto], outs[:upto]) if not self._keep(take, item[0], item[1], lang)]
            shutil.rmtree(workdir, ignore_errors=True)
            if first_missing is not None:
                bad.append(queue[first_missing])
                queue = queue[first_missing + 1:]
            else:
                queue = []
            for item in bad:
                if not self._alone(voice, item, lang):
                    failed.append(item)
        return failed
