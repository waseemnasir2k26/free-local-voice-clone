"""Tests run without a GPU: the audio.cpp call is replaced by a fake runner."""
import json
from pathlib import Path

import numpy as np
import pytest

from voiceclone import cli
from voiceclone.audio import fade, join, read_wav, trim_edges, wav_seconds, write_wav
from voiceclone.engine import SEED_STEP, Engine, SetupError, Voice
from voiceclone.qc import cer, normalise, wer
from voiceclone.text import duration_ok, expected_secs, max_tokens_for, parse_script, respell, split_chunks

RATE = 24000


def tone(seconds: float, lead: float = 0.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    body = 0.3 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    return np.concatenate([np.zeros(int(RATE * lead), dtype=np.float32), body, np.zeros(int(RATE * lead), dtype=np.float32)])


@pytest.fixture
def voice(tmp_path) -> Voice:
    d = tmp_path / "voices"
    d.mkdir()
    write_wav(d / "me.wav", tone(1.0), RATE)
    (d / "me.txt").write_text("This is my reference clip.\n", encoding="utf-8")
    return Voice.load("me", d)


class FakeRunner:
    """Stands in for audio.cpp. `runaway` maps text -> seeds that fail for it."""

    def __init__(self, runaway=None, wrong_length=None):
        self.runaway = runaway or {}
        self.wrong_length = wrong_length or {}
        self.calls = []

    def __call__(self, texts, voice, seed, max_tokens, workdir):
        self.calls.append((list(texts), seed, max_tokens))
        out = []
        aborted = False
        for i, text in enumerate(texts):
            if aborted or seed in self.runaway.get(text, ()):
                aborted = True  # a runaway kills this line and every line after it in the batch
                out.append(None)
                continue
            seconds = 60.0 if seed in self.wrong_length.get(text, ()) else expected_secs(text)
            path = Path(workdir) / f"line_{i + 1}.wav"
            write_wav(path, tone(seconds), RATE)
            out.append(path)
        return out


def make_engine(runner, **kw) -> Engine:
    return Engine(cli="x", model="y", runner=runner, log=lambda _m: None, **kw)


# ------------------------------------------------------------------ text
def test_respell_whole_words_only():
    assert respell("Open n8n now") == "Open N, eight, N now"
    assert respell("N8N rocks") == "N, eight, N rocks"
    assert respell("fn8nx stays") == "fn8nx stays"
    assert respell("use SQL", {"SQL": "sequel"}) == "use sequel"


def test_split_chunks_respects_limit_and_keeps_words():
    text = "First sentence here. Second one is a bit longer than the first. Third! Fourth?"
    chunks = split_chunks(text, 40)
    assert all(len(c) <= 40 for c in chunks)
    assert " ".join(chunks).split() == text.split()
    assert split_chunks("short line", 320) == ["short line"]
    assert split_chunks("   ", 320) == []
    long_word_run = "word " * 100
    assert all(len(c) <= 50 for c in split_chunks(long_word_run, 50))


def test_parse_script_speakers_and_comments():
    raw = "# intro\nzoya: Hello there.\n\nPlain line.\nChacha: Kya haal hai?\nhttp://x.y is not a speaker\n"
    assert parse_script(raw, "me") == [
        ("zoya", "Hello there."), ("me", "Plain line."), ("chacha", "Kya haal hai?"),
        ("me", "http://x.y is not a speaker"),
    ]


def test_duration_gate_and_token_budget():
    text = "x" * 140  # about 10 s
    assert duration_ok(10, text) and not duration_ok(2, text) and not duration_ok(40, text)
    assert max_tokens_for(["hi"]) == 900
    assert max_tokens_for([text], attempt=1) > max_tokens_for([text])
    assert max_tokens_for(["x" * 5000]) == 6000


# ------------------------------------------------------------------ audio
def test_wav_roundtrip_trim_fade(tmp_path):
    p = tmp_path / "a.wav"
    write_wav(p, tone(1.0, lead=0.5), RATE)
    data, rate = read_wav(p)
    assert rate == RATE and abs(wav_seconds(p) - 2.0) < 0.01
    trimmed = trim_edges(data, rate)
    assert 1.0 <= trimmed.size / rate <= 1.1
    faded = fade(trimmed, rate)
    assert abs(faded[0]) < 1e-6 and abs(faded[-1]) < 1e-6
    assert trim_edges(np.zeros(1000, dtype=np.float32), rate).size == 0


def test_join_pauses_and_room_tone(tmp_path):
    a, b, c = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"
    for p in (a, b, c):
        write_wav(p, tone(1.0), RATE)
    out = tmp_path / "joined.wav"
    seconds = join([a, b, c], out, pause_s=0.5, speaker_pause_s=1.0, speakers=["x", "x", "y"])
    assert abs(seconds - 4.5) < 0.05  # 3 s speech + 0.5 same speaker + 1.0 speaker change
    data, rate = read_wav(out)
    gap = data[int(1.2 * rate): int(1.3 * rate)]
    assert 0 < np.max(np.abs(gap)) < 0.01  # room tone, not digital silence, not speech
    silent = tmp_path / "silent.wav"
    join([a, b], silent, pause_s=0.5, tone_db=None)
    data, rate = read_wav(silent)
    assert np.max(np.abs(data[int(1.2 * rate): int(1.3 * rate)])) == 0
    with pytest.raises(ValueError):
        join([], out)


# ------------------------------------------------------------------ engine
def test_clean_batch_is_one_model_load(voice, tmp_path):
    runner = FakeRunner()
    engine = make_engine(runner)
    texts = [f"Line number {i} of the script." for i in range(5)]
    outs = [tmp_path / f"{i}.wav" for i in range(5)]
    assert engine.synth(voice, texts, outs)
    assert len(runner.calls) == 1 and all(o.exists() for o in outs)
    assert engine.stats.lines == 5 and engine.stats.retries == 0


def test_runaway_line_is_retried_alone_and_rest_requeued(voice, tmp_path):
    texts = ["Alpha line is fine.", "Bravo line runs away.", "Charlie line is fine.", "Delta line is fine."]
    runner = FakeRunner(runaway={texts[1]: {7}})
    engine = make_engine(runner)
    outs = [tmp_path / f"{i}.wav" for i in range(4)]
    assert engine.synth(voice, texts, outs)
    assert all(o.exists() for o in outs)
    assert runner.calls[0][0] == texts                       # full batch, aborted at line 2
    assert (runner.calls[1][0], runner.calls[1][1]) == ([texts[1]], 7 + SEED_STEP)  # culprit alone, new seed
    assert runner.calls[2][0] == texts[2:]                   # the rest go back in one batch
    assert engine.stats.retries == 1


def test_wrong_length_take_is_rejected_and_retried(voice, tmp_path):
    text = "This take comes back sixty seconds long."
    runner = FakeRunner(wrong_length={text: {7}})
    engine = make_engine(runner)
    out = tmp_path / "o.wav"
    assert engine.synth(voice, [text], [out])
    assert wav_seconds(out) < 10 and engine.stats.retries == 1


def test_line_that_never_works_is_reported_not_hung(voice, tmp_path):
    bad = "This line always runs away."
    runner = FakeRunner(runaway={bad: {7, 7 + SEED_STEP, 7 + 2 * SEED_STEP, 7 + 3 * SEED_STEP}})
    engine = make_engine(runner)
    outs = [tmp_path / "a.wav", tmp_path / "b.wav"]
    assert not engine.synth(voice, [bad, "This one is fine."], outs)
    assert not outs[0].exists() and outs[1].exists()
    assert engine.stats.failed == [bad] and len(runner.calls) == 5


def test_batches_split_by_batch_size(voice, tmp_path):
    runner = FakeRunner()
    engine = make_engine(runner, batch=2)
    texts = [f"Sentence number {i} here." for i in range(5)]
    assert engine.synth(voice, texts, [tmp_path / f"{i}.wav" for i in range(5)])
    assert [len(c[0]) for c in runner.calls] == [2, 2, 1]


def test_missing_setup_is_a_clear_error(tmp_path):
    with pytest.raises(SetupError):
        Voice.load("nobody", tmp_path)
    with pytest.raises(SetupError):
        Engine(cli=str(tmp_path / "nope"), model=str(tmp_path / "nope")).check()
    (tmp_path / "v.wav").write_bytes(b"x")
    (tmp_path / "v.txt").write_text("  \n", encoding="utf-8")
    with pytest.raises(SetupError):
        Voice.load("v", tmp_path)


# ------------------------------------------------------------------ qc
def test_cer_wer_and_urdu_normalisation():
    assert cer("Hello, world!", "hello world") == 0.0
    assert wer("the quick brown fox", "the quick fox") == 0.25
    assert normalise("كتاب") == normalise("کتاب")
    assert cer("abcd", "") == 1.0


# ------------------------------------------------------------------ cli
def test_batch_cli_end_to_end_with_fake_engine(voice, tmp_path, monkeypatch):
    script = tmp_path / "s.txt"
    script.write_text("me: Welcome to the n8n show.\nSecond line here for the test.\n", encoding="utf-8")
    runner = FakeRunner()
    monkeypatch.setattr(cli, "_engine", lambda args: make_engine(runner))
    monkeypatch.setattr(Engine, "check", lambda self: None)
    out, joined = tmp_path / "out", tmp_path / "final.wav"
    code = cli.main(["batch", "--file", str(script), "--voice", "me", "--voices", str(voice.wav.parent),
                     "--out", str(out), "--join", str(joined)])
    assert code == 0 and joined.exists()
    rows = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert [r["ok"] for r in rows] == [True, True]
    assert rows[0]["text"] == "Welcome to the n8n show." and "N, eight, N" in rows[0]["spoken"]
    assert "N, eight, N" in runner.calls[0][0][0]            # the model got the respelled text


def test_say_cli_writes_one_joined_file_and_cleans_up(voice, tmp_path, monkeypatch):
    runner = FakeRunner()
    monkeypatch.setattr(cli, "_engine", lambda args: make_engine(runner))
    monkeypatch.setattr(Engine, "check", lambda self: None)
    out = tmp_path / "hello.wav"
    code = cli.main(["say", "First sentence of the take. Second sentence of the take.", "--voice", "me",
                     "--voices", str(voice.wav.parent), "--out", str(out), "--max-chars", "30"])
    assert code == 0 and out.exists() and wav_seconds(out) > 1
    assert len(runner.calls[0][0]) == 2                      # split into two chunks, voiced in one load
    assert not (tmp_path / ".hello_takes").exists()


def test_cli_reports_setup_problem(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIOCPP_CLI", raising=False)
    monkeypatch.delenv("HIGGS_GGUF", raising=False)
    code = cli.main(["say", "hi there", "--voice", "me", "--voices", str(tmp_path), "--cli", str(tmp_path / "no"),
                     "--out", str(tmp_path / "o.wav")])
    assert code == 2
