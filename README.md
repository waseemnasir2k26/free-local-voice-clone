# Free Local Voice Clone: clone your own voice on your own laptop

**Free local voice cloning and text to speech for your own content. Clone your voice from 15 to 20 seconds of audio, voice complete scripts, and run the whole voiceover pipeline on your own computer. No subscription, no per-character bill, and your voice is never uploaded.**

A small Python tool that turns [Higgs Audio v3](https://huggingface.co/bosonai/higgs-tts-3-4b) and [audio.cpp](https://github.com/0xShug0/audio.cpp) into a voiceover pipeline you can actually run a channel on: whole scripts in one command, several cloned voices in one episode, automatic retries when the model misbehaves, and a Whisper check that tells you which lines to re-listen to.

![License: MIT](https://img.shields.io/badge/code-MIT-green) ![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![Generation runs on your device](https://img.shields.io/badge/generation-on%20your%20device-black) ![Tested on RTX 4060 8 GB](https://img.shields.io/badge/tested-RTX%204060%208%20GB-orange)

## Hear it first

Same person, same laptop. The first clip is real. The second was typed, not spoken.

| | |
|---|---|
| 🎙️ [Real voice, 15 seconds](demo/1-real-voice-15s.mp3) | The only audio the model was given |
| 🤖 [Cloned voice](demo/2-cloned-voice.mp3) | He never said these words. First take, no edits |

The voice is the author's own, shared with his consent. Details in [demo/](demo/README.md). This audio was created with Boson AI's Higgs Audio — https://www.boson.ai/higgs-audio

## Three commands

```bash
voiceclone ref   --in my-recording.m4a --start 8 --dur 15 --name me
voiceclone say   --voice me "This is my voice. I never recorded this sentence."
voiceclone batch --voice me --file script.txt --out takes --join episode.wav
```

This is the voice pipeline we run at [SkynetLabs](https://skynetjoe.com) for two things: **AI Baithak**, an Urdu AI talk show with six recurring character voices, and our **Claude Code course** narration in the founder's own cloned voice. Seven episodes, about 2,000 lines and 230 minutes of audio, were voiced on one RTX 4060 laptop in roughly three hours.

---

## Why bother running it locally

- **No per-character bill.** No monthly plan, no character quota, no "you ran out of credits on line 1,400". The limits are your hardware and the model licence.
- **Your voice never leaves your machine.** The reference clip and every script stay on your disk. Nothing is uploaded anywhere.
- **Unlimited retakes.** Change one word, re-voice the line, pay nothing. This changes how you write: you stop rationing edits.
- **Many voices, one show.** Write `zoya: ...` and `chacha: ...` in a script and each line is voiced by the right clone.
- **Works where cards do not.** No international card, no dollar subscription, no payment gateway. Built by a team in Pakistan and Bali for people in the same spot.
- **English, Urdu and Roman Urdu are tested in production**, mixed in the same sentence. The model card lists about 100 languages; we have not tested the others.

## Is this a real ElevenLabs alternative?

For recorded voiceover on your own channels: yes, that is exactly what we replaced. For everything else, be honest with yourself. This table is.

|                                              | local-voice-clone                                                                     | ElevenLabs (hosted)               |
| -------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------- |
| Cost                                         | Free to run                                                                           | Subscription with monthly credits |
| Where your voice data lives                  | Your disk                                                                             | Their servers                     |
| Usage limit                                  | Your GPU and your patience                                                            | Your plan                         |
| Setup                                        | About 20 minutes, 5 GB download                                                       | Sign up and go                    |
| Hardware                                     | A GPU with 8 GB helps a lot                                                           | Any device with a browser         |
| Speed                                        | About 0.7x real time on an RTX 4060, after a 40 s model load                          | Near instant                      |
| Real-time agents, phone bots, streaming      | No                                                                                    | Yes                               |
| Polish (apps, dubbing studio, voice library) | A command line                                                                        | A full product                    |
| Commercial terms                             | Free for your own channels with a credit line, see [Licence](#licence-in-plain-words) | Per their plan                    |

Short version: if you publish videos, podcasts, courses or reels and you own a gaming laptop, you probably do not need a voice subscription. If you are building a product with voices in it, or you need real-time speech, a hosted service (or a commercial licence from Boson AI) is the right call.

This project is not affiliated with ElevenLabs or Boson AI.

## Quick start

### Windows, one step (recommended)

Open PowerShell and paste these two lines. It downloads everything (about 6.2 GB) into `C:oiceclone`, sets it up, and runs a self-check. Internet is needed for this setup only; generation afterwards runs on your device.

```powershell
irm https://raw.githubusercontent.com/waseemnasir2k26/free-local-voice-clone/main/install-windows.ps1 -OutFile $env:TEMPc-install.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMPc-install.ps1
```

Then open a new PowerShell window and jump to "make a voice" below.

### Manual setup (Linux, macOS, or if you prefer)

You need Python 3.10+, about 12 GB of free disk during setup, and ideally an NVIDIA GPU with 8 GB. Full walkthrough with download links: [docs/SETUP.md](docs/SETUP.md).

```bash
# 1. this tool
git clone https://github.com/waseemnasir2k26/free-local-voice-clone
cd free-local-voice-clone
pip install -e ".[qc]"

# 2. the runtime: download the audio.cpp release for your system, unzip it
#    https://github.com/0xShug0/audio.cpp/releases

# 3. the model (5.1 GB)
hf download audio-cpp/audio.cpp-gguf Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf --local-dir models

# 4. tell the tool where they are
export AUDIOCPP_CLI=/full/path/to/audiocpp_cli
export HIGGS_GGUF=/full/path/to/models/Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf

# 5. check
voiceclone doctor
```

Then make a voice and use it:

```bash
# Cut 15 clean seconds out of any recording of YOUR voice. The transcript is written for you: read it and fix it.
voiceclone ref --in my-recording.m4a --start 8 --dur 15 --name me

voiceclone say --voice me "If you can copy and paste, you can build this." -o test.wav
```

How to record a reference that clones well: [docs/RECORDING.md](docs/RECORDING.md).

## Voice a whole script

One line of speech per line. Lines can switch speaker with `name:`.

```text
# episode-01.txt
me: Welcome back. Today we are building a lead form that replies in twelve seconds.
me: You do not need to code. You need n8n and ten minutes.
zoya: Sir jee, ek sawaal. Yeh free mein chalega?
me: Free. That is the whole point.
```

```bash
voiceclone batch --voice me --file episode-01.txt --out takes --join episode-01.wav
voiceclone qc --manifest takes/manifest.json
```

You get one WAV per line (so you can swap a single take later), one joined track, and a QC report.

## What this adds on top of the raw model

The model is the hard part and it is not ours. What we add is the boring layer we needed after voicing thousands of lines:

- **Runaway-line recovery.** Every so often the model never stops generating a line, and inside a batch that kills every line after it. The tool keeps the good takes, re-voices only the culprit with a new seed, and puts the rest back in the queue. This is the difference between "works in a demo" and "voiced 2,000 lines overnight".
- **Length gate.** Every take is checked against how long that sentence should take to say. Clipped and looping takes are thrown out and retried.
- **One model load per voice.** Lines are batched so the 5 GB model loads once, not once per sentence.
- **Whisper QC.** Each take is transcribed and compared with the script. You listen to the three flagged lines, not all 300.
- **Joins that do not sound like AI.** Edge trim and a short fade on every take, natural pauses, a longer pause on speaker change, and quiet room tone under the track. Pure digital silence between sentences is the fastest way to get caught.
- **Pronunciation table.** `n8n` becomes "N, eight, N" before the model sees it. Add your own brand names in a JSON file.
- **Polite to your laptop.** Runs at below-normal priority with three threads, so you can keep working while it voices.

## Numbers, measured

One speaker, one laptop (RTX 4060 Laptop, 8 GB). Your results will differ.

| What                                                                | Result                                                       |
| ------------------------------------------------------------------- | ------------------------------------------------------------ |
| Reference audio needed                                              | 15 to 20 seconds                                             |
| Speaker similarity to real held-out recordings (Resemblyzer cosine) | 0.89 for the clone, 0.53 for a stock TTS voice               |
| Words wrong on English test lines (Whisper small.en)                | about 8 in 100, mostly numbers and names written differently |
| Speed on a long batch                                               | about 0.7 s of compute per second of audio                   |
| Model load                                                          | about 40 s, once per voice per batch                         |
| Largest run so far                                                  | about 2,000 lines, 230 minutes of audio, roughly 3 hours     |

## Urdu and Roman Urdu

This is why we picked Higgs over the usual open models, most of which do not speak Urdu at all. Notes from production in [docs/URDU.md](docs/URDU.md): everyday Urdu mixed with English works best, write numbers above ten as English words, and expect the QC score to be unreliable on Roman Urdu.

## Licence in plain words

Two different licences apply. Read this before you plan a business on it.

- **This repository** (the Python code) is MIT. Do what you like with it.
- **The runtime**, audio.cpp, is Apache 2.0, from ShugoAI.
- **The model**, Higgs TTS 3, is from Boson AI under the _Boson Higgs TTS 3 Research and Non-Commercial License_. This repo does not contain or redistribute it. You download it yourself and accept their terms. What matters in practice:
  - **Creators can publish and monetize for free** on channels they own or control (YouTube, podcasts, courses, social), as long as they credit it visibly, for example in the description: `This audio was created with Boson AI's Higgs Audio — https://www.boson.ai/higgs-audio`
  - **Not covered without a commercial licence from Boson:** hosting it as an API or app, putting it inside a product or service, or reselling it. Voiceover sold to clients for their channels is outside the creator grant as we read it. Ask Boson.
  - **Cloning needs consent.** The licence forbids cloning any real person without their explicit, verifiable consent.

The full text is the only authority: [LICENSE on Hugging Face](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/LICENSE). This section is our reading, not legal advice.

Built with Higgs TTS 3 licensed from Boson AI USA, Inc.

## Use it on your own voice

Clone yourself. Clone a colleague who signed off in writing. Design a fictional voice. Do not clone anyone else: not a celebrity, not a politician, not your client "for a quick test". More in [docs/ETHICS.md](docs/ETHICS.md).

## FAQ

**Is it really free?** The code and the runtime are free and open source. The model is free for research, personal use, and creator content on your own channels with a credit line.

**Can I run it without a GPU?** Yes with `--backend cpu`, but it is slow. An 8 GB NVIDIA card is the comfortable minimum. audio.cpp also ships Vulkan and Apple Metal builds; we have only tested Windows with CUDA.

**How much audio do I need to clone a voice?** 15 to 20 clean seconds plus the exact words spoken in it. More audio does not help this method; a cleaner clip does.

**Does it work in my language?** The model lists about 100 languages. We have used English, Urdu and Roman Urdu in production.

**Is this a free ElevenLabs alternative for YouTube voiceover?** For pre-recorded narration on your own channel, yes. For real-time voice agents, no.

**Is the output watermarked or detectable?** Assume yes and disclose AI voice where your platform asks you to. Never use it to pretend to be someone else.

**Why not XTTS, F5-TTS or Fish?** Check each licence and language list. When we chose, those had either a non-commercial licence with no creator exception, a paid licence, or no Urdu.

**A line keeps failing.** Shorten it, split it at a comma, or pass a different `--seed`.

## Project layout

```text
voiceclone/engine.py   audio.cpp runner, batching, runaway-line retries
voiceclone/text.py     respelling, chunking, script parsing, length estimates
voiceclone/audio.py    trim, fades, joins, room tone
voiceclone/qc.py       Whisper transcription check, Urdu-aware
voiceclone/cli.py      doctor, ref, say, batch, qc
tests/                 16 tests, no GPU needed (pytest)
```

## Contributing

Issues and pull requests are welcome, especially: test reports on Linux, macOS and AMD cards, pronunciation tables for other languages, and better room tone. Run `pytest` before you open a PR.

## Need a custom AI workflow?

We build AI automation systems and content production workflows at [SkynetLabs](https://skynetjoe.com). The MIT licence on this code does not grant commercial rights to the model; that is between you and Boson AI.

## Credits

- [Boson AI](https://www.boson.ai/) for Higgs Audio.
- [ShugoAI / audio.cpp](https://github.com/0xShug0/audio.cpp) for the runtime that makes it fit on a laptop.
- Built and used in production by [Waseem Nasir](https://github.com/waseemnasir2k26) at [SkynetLabs](https://skynetjoe.com), an AI automation agency.

If this saved you a subscription, a star helps other creators find it.

<sub>Keywords: free voice cloning, local voice clone, open source text to speech, ElevenLabs alternative, offline TTS, Higgs Audio v3, audio.cpp, GGUF TTS, Urdu text to speech, Roman Urdu TTS, AI voiceover for YouTube, faceless channel voiceover, clone my voice free, voice cloning on 8 GB GPU.</sub>
