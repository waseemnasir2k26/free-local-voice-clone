"""voiceclone command line.

  voiceclone doctor                          check audio.cpp, the model, ffmpeg
  voiceclone ref   --in me.m4a --name me     cut a 10-20 s reference clip + transcript
  voiceclone say   --voice me "Hello."       one line -> out.wav
  voiceclone batch --voice me --file s.txt   a whole script -> one wav per line (+ joined track)
  voiceclone qc    --manifest out/manifest.json   flag takes that do not match the script
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .audio import join, wav_seconds
from .engine import Engine, SetupError, Voice, default_cli, default_model
from .text import load_respell, parse_script, respell, split_chunks

CONSENT = (
    "Only clone a voice you own or have written permission to use. "
    "See docs/ETHICS.md and the model licence."
)


def _engine(args) -> Engine:
    return Engine(
        cli=args.cli, model=args.model, backend=args.backend, threads=args.threads,
        temperature=args.temperature, seed=args.seed, batch=args.batch_size,
    )


def _add_engine_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--voices", default=os.environ.get("VOICECLONE_VOICES", "voices"), help="folder of <name>.wav + <name>.txt")
    p.add_argument("--cli", default=None, help="path to audiocpp_cli (or env AUDIOCPP_CLI)")
    p.add_argument("--model", default=None, help="path to the Higgs GGUF (or env HIGGS_GGUF)")
    p.add_argument("--backend", default="best", help="cuda | vulkan | metal | cpu | best")
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--seed", type=int, default=7, help="change it if a voice keeps looping")
    p.add_argument("--batch-size", type=int, default=40, help="lines per model load")
    p.add_argument("--lang", default="en", help="en or ur: sets pacing estimates and QC language")
    p.add_argument("--respell", default=None, help="JSON of {word: spoken spelling}")


# ---------------------------------------------------------------------- doctor
def cmd_doctor(args) -> int:
    ok = True

    def line(good: bool, label: str, detail: str) -> None:
        nonlocal ok
        ok = ok and good
        print(f"  {'OK  ' if good else 'MISS'} {label}: {detail}")

    cli, model = args.cli or default_cli(), args.model or default_model()
    print(f"local-voice-clone {__version__}")
    line(bool(cli) and Path(cli).exists(), "audio.cpp CLI", cli or "set AUDIOCPP_CLI")
    line(bool(model) and Path(model).exists(), "Higgs model", model or "set HIGGS_GGUF")
    ffmpeg = shutil.which("ffmpeg")
    print(f"  {'OK  ' if ffmpeg else 'opt '} ffmpeg: {ffmpeg or 'not found (only needed for: voiceclone ref)'}")
    if cli and Path(cli).exists():
        try:
            out = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
            print("  " + out.replace("\n", "\n  "))
        except Exception as e:
            print(f"  could not run the CLI: {e}")
    voices = Path(args.voices)
    names = sorted(p.stem for p in voices.glob("*.wav") if (voices / f"{p.stem}.txt").exists()) if voices.exists() else []
    print(f"  voices in {voices}: {', '.join(names) if names else 'none yet (voiceclone ref --help)'}")
    print("Ready." if ok else "Not ready. See docs/SETUP.md.")
    return 0 if ok else 1


# ---------------------------------------------------------------------- ref
def cmd_ref(args) -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg is required for this command.", file=sys.stderr)
        return 1
    if not 5 <= args.dur <= 30:
        print("--dur should be 5 to 30 seconds (10 to 20 is the sweet spot).", file=sys.stderr)
        return 1
    voices = Path(args.voices)
    voices.mkdir(parents=True, exist_ok=True)
    wav = voices / f"{args.name}.wav"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(args.start), "-t", str(args.dur), "-i", args.infile,
           "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(wav)]
    if subprocess.run(cmd).returncode != 0 or not wav.exists():
        print("ffmpeg could not cut the clip.", file=sys.stderr)
        return 1
    text = args.text
    if not text:
        from .qc import load_whisper, transcribe
        text = transcribe(load_whisper(args.whisper), wav, args.lang)
        print("Transcript (auto, CHECK IT word by word, a wrong transcript hurts the clone):")
    (voices / f"{args.name}.txt").write_text(text.strip() + "\n", encoding="utf-8")
    print(f"  {text.strip()}")
    print(f"Saved {wav} ({wav_seconds(wav):.1f} s) + {args.name}.txt")
    print(CONSENT)
    return 0


# ---------------------------------------------------------------------- say / batch
def _voice_lines(args, script: list[tuple[str, str]], outdir: Path) -> tuple[list[dict], Engine]:
    """Voice a parsed script. Returns the manifest rows in script order."""
    table = load_respell(args.respell)
    engine = _engine(args)
    engine.check()
    rows: list[dict] = []
    for n, (voice_name, text) in enumerate(script, 1):
        for c, chunk in enumerate(split_chunks(text, args.max_chars), 1):
            rows.append({
                "n": n, "voice": voice_name, "text": chunk, "spoken": respell(chunk, table), "lang": args.lang,
                "wav": str(outdir / f"{n:04d}_{c:02d}_{voice_name}.wav"),
            })
    for voice_name in dict.fromkeys(r["voice"] for r in rows):  # one model run per voice
        voice = Voice.load(voice_name, args.voices)
        mine = [r for r in rows if r["voice"] == voice_name and not (args.resume and Path(r["wav"]).exists())]
        if mine:
            engine.synth(voice, [r["spoken"] for r in mine], [r["wav"] for r in mine], args.lang)
    for r in rows:
        r["ok"] = Path(r["wav"]).exists()
    return rows, engine


def _report(engine: Engine, rows: list[dict]) -> int:
    s = engine.stats
    missing = [r for r in rows if not r["ok"]]
    print(f"Voiced {len(rows) - len(missing)}/{len(rows)} takes, {s.audio_s:.1f} s of audio in {s.gen_s:.1f} s "
          f"(RTF {s.rtf}), {s.retries} retries.")
    for r in missing:
        print(f"  FAILED line {r['n']}: {r['text'][:70]!r}  -> shorten it or try --seed")
    return 1 if missing else 0


def cmd_say(args) -> int:
    out = Path(args.out)
    tmp = out.parent / f".{out.stem}_takes"
    try:
        rows, engine = _voice_lines(args, [(args.voice, args.text)], tmp)
        code = _report(engine, rows)
        good = [r["wav"] for r in rows if r["ok"]]
        if good and not code:
            join(good, out, pause_s=args.pause, tone_db=None if args.no_tone else args.tone_db)
            print(f"Saved {out} ({wav_seconds(out):.1f} s)")
        return code
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_batch(args) -> int:
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    script = parse_script(Path(args.file).read_text(encoding="utf-8"), args.voice)
    if not script:
        print("The script has no lines.", file=sys.stderr)
        return 1
    rows, engine = _voice_lines(args, script, outdir)
    manifest = outdir / "manifest.json"
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    code = _report(engine, rows)
    good = [r for r in rows if r["ok"]]
    if args.join and good:
        seconds = join([r["wav"] for r in good], args.join, pause_s=args.pause, speaker_pause_s=args.speaker_pause,
                       speakers=[r["voice"] for r in good], tone_db=None if args.no_tone else args.tone_db,
                       tone_file=args.tone_file)
        print(f"Joined track: {args.join} ({seconds:.1f} s)")
    print(f"Manifest: {manifest}")
    return code


# ---------------------------------------------------------------------- qc
def cmd_qc(args) -> int:
    from .qc import check
    rows = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    jobs = [{"wav": r["wav"], "text": r["text"], "lang": r.get("lang", "en"), "n": r["n"]} for r in rows if r.get("ok", True)]
    results = check(jobs, model=args.whisper, device=args.device, threshold=args.threshold)
    flagged = [r for r in results if r["flag"]]
    out = Path(args.manifest).with_name("qc.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in flagged:
        print(f"  LISTEN line {r['n']} (CER {r['cer']}): wrote {r['text'][:50]!r} heard {r['heard'][:50]!r}")
    print(f"{len(results) - len(flagged)}/{len(results)} takes match the script. Report: {out}")
    return 1 if flagged else 0


# ---------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="voiceclone", description="Clone a voice on your own GPU. " + CONSENT)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check the setup")
    d.add_argument("--cli", default=None)
    d.add_argument("--model", default=None)
    d.add_argument("--voices", default=os.environ.get("VOICECLONE_VOICES", "voices"))
    d.set_defaults(fn=cmd_doctor)

    r = sub.add_parser("ref", help="cut a reference clip from a recording")
    r.add_argument("--in", dest="infile", required=True, help="any audio or video file of the voice")
    r.add_argument("--name", required=True, help="voice name, e.g. me")
    r.add_argument("--start", type=float, default=0.0, help="start second of the clean part")
    r.add_argument("--dur", type=float, default=15.0, help="clip length in seconds (10 to 20 works best)")
    r.add_argument("--text", default=None, help="exact words in the clip (skip to auto-transcribe)")
    r.add_argument("--lang", default="en")
    r.add_argument("--whisper", default="small")
    r.add_argument("--voices", default=os.environ.get("VOICECLONE_VOICES", "voices"))
    r.set_defaults(fn=cmd_ref)

    def tone_args(x: argparse.ArgumentParser) -> None:
        x.add_argument("--pause", type=float, default=0.45, help="seconds between sentences")
        x.add_argument("--tone-db", type=float, default=-62.0, help="room tone level under the track")
        x.add_argument("--no-tone", action="store_true", help="leave digital silence in the pauses")
        x.add_argument("--max-chars", type=int, default=320, help="split longer lines at sentence ends")
        x.add_argument("--resume", action="store_true", help="skip takes that already exist")

    s = sub.add_parser("say", help="voice one line")
    s.add_argument("text")
    s.add_argument("--voice", required=True)
    s.add_argument("--out", "-o", default="out.wav")
    _add_engine_args(s)
    tone_args(s)
    s.set_defaults(fn=cmd_say)

    b = sub.add_parser("batch", help="voice a script, one line of speech per line")
    b.add_argument("--file", required=True, help="script: plain lines, or 'name: text' to switch voice")
    b.add_argument("--voice", required=True, help="default voice for lines with no 'name:' prefix")
    b.add_argument("--out", "-o", default="out", help="folder for the takes")
    b.add_argument("--join", default=None, help="also write one joined track here")
    b.add_argument("--speaker-pause", type=float, default=0.7, help="pause when the speaker changes")
    b.add_argument("--tone-file", default=None, help="wav of your real empty room to use as the bed")
    _add_engine_args(b)
    tone_args(b)
    b.set_defaults(fn=cmd_batch)

    q = sub.add_parser("qc", help="transcribe takes and flag mismatches")
    q.add_argument("--manifest", required=True)
    q.add_argument("--whisper", default="small")
    q.add_argument("--device", default="cpu", help="cpu or cuda")
    q.add_argument("--threshold", type=float, default=0.35)
    q.set_defaults(fn=cmd_qc)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Urdu text on a Windows console
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except SetupError as e:
        print(f"Setup problem: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
