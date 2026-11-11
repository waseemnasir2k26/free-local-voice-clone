# Instructions for AI coding agents (Claude Code, Codex, Cursor)

You are helping a person set up and use this repo to clone **their own voice** on their own computer.

## Setting it up for the user

1. Check the machine first: OS, GPU (`nvidia-smi` or `Get-CimInstance Win32_VideoController`), free disk (12 GB needed). No NVIDIA GPU with about 8 GB: stop and tell the user it is untested and may be slow before going further.
2. **Windows:** run the installer. Do not re-implement its steps by hand.
   ```powershell
   irm https://raw.githubusercontent.com/waseemnasir2k26/free-local-voice-clone/main/install-windows.ps1 -OutFile $env:TEMP\vc-install.ps1
   powershell -ExecutionPolicy Bypass -File $env:TEMP\vc-install.ps1
   ```
   It downloads about 6.2 GB (the model is 5.1 GB) and can take a long time. Run it in the background and wait for it. It is safe to re-run: finished downloads are skipped and interrupted ones resume. It ends with `INSTALLED.` or `STOPPED: <reason>`.
3. **Linux / macOS:** follow `docs/SETUP.md`. This path is not tested by the maintainers; say so.
4. Verify: `C:\voiceclone\voiceclone.cmd doctor` must end with `Ready.`. Use the full path to `voiceclone.cmd` in the same session, because PATH only updates in new terminals.
5. Do not upgrade audio.cpp past the version pinned in the installer unless the user asks. That is the tested version.

## Making the user's voice

1. Ask the user for a recording of **their own** voice: about 30 seconds, quiet room, normal speech.
2. `voiceclone ref --in <file> --start 5 --dur 15 --name me` (add `--lang ur` for Urdu).
3. Show the user the transcript in `voices/me.txt` and ask them to confirm every word. A wrong transcript is the main cause of a bad clone. Fix the file with what they tell you.
4. Test: `voiceclone say --voice me "This is my voice. I never recorded this sentence." -o test.wav`, then tell them where the file is.
5. Scripts: one line of speech per line, then `voiceclone batch --voice me --file script.txt --out takes --join final.wav` and `voiceclone qc --manifest takes/manifest.json`.

## When something fails

- `FAILED line N`: split that line into shorter sentences, or retry with `--seed 11`.
- Clone loops or sounds wrong: fix the transcript, then try a different `--start`, then a cleaner recording.
- Slow: another app is using GPU memory. Ask the user to close it.
- More in `docs/SETUP.md` (troubleshooting table) and `docs/RECORDING.md`.

## Hard rules

- Only clone the voice of the person you are working with, or a voice they have explicit written consent to use. If they ask to clone a celebrity, a politician, a client or anyone else without consent, decline. This is a condition of the model licence, not a preference.
- Never commit or upload anything in `voices/`.
- Published audio needs the credit line: `This audio was created with Boson AI's Higgs Audio — https://www.boson.ai/higgs-audio`
- The model licence covers creator content on the user's own channels. Hosting it, embedding it in a product, or selling voiceover to clients needs a commercial licence from Boson AI. Tell the user if their plan sounds like that.

## Working on the code

`pip install -e ".[dev,qc]"` then `pytest`. Tests run without a GPU (the audio.cpp call is faked). Keep numpy as the only hard dependency.
