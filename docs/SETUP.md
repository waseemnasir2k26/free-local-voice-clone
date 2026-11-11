# Setup

Tested by us on Windows 11, RTX 4060 Laptop (8 GB), audio.cpp 0.9.2 with the CUDA 12.4 build. Linux and macOS builds of audio.cpp exist and should work the same way; if you try one, please open an issue with what happened.

## 1. Install this tool

```bash
git clone https://github.com/waseemnasir2k26/free-local-voice-clone
cd free-local-voice-clone
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[qc]"
```

`[qc]` adds faster-whisper for the transcript check and for auto-transcribing your reference clip. Leave it off if you only want to generate audio.

## 2. Get audio.cpp

Go to the releases page: https://github.com/0xShug0/audio.cpp/releases

Download the `bin` archive for your system. On Windows with an NVIDIA card you need two files with matching CUDA versions, both unzipped into the **same folder**:

- `audio-vX.Y.Z-bin-windows-x64-cuda12.4.zip`
- `audio-vX.Y.Z-cudart-windows-x64-cuda12.4.zip`

No NVIDIA card? Take the `vulkan` build (AMD, Intel) or the `metal` build (Mac), or `cpu` as a slow last resort.

Check it runs:

```bash
/path/to/audiocpp_cli --version
```

## 3. Get the model

5.1 GB. By downloading it you accept the [Boson Higgs TTS 3 licence](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/LICENSE).

```bash
pip install -U huggingface_hub
hf download audio-cpp/audio.cpp-gguf Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf --local-dir models
```

Slow connection that throttles single downloads? `pip install hf_transfer` and set `HF_HUB_ENABLE_HF_TRANSFER=1` for parallel chunks.

## 4. Point the tool at both

Windows (PowerShell, permanent):

```powershell
setx AUDIOCPP_CLI "C:\tools\audiocpp\audiocpp_cli.exe"
setx HIGGS_GGUF "C:\tools\models\Higgs-Audio-v3-TTS-4B-GGUF\higgs-audio-v3-tts-4b-q8_0.gguf"
```

Open a new terminal afterwards.

Linux / macOS (add to `~/.bashrc` or `~/.zshrc`):

```bash
export AUDIOCPP_CLI="$HOME/tools/audiocpp/audiocpp_cli"
export HIGGS_GGUF="$HOME/tools/models/Higgs-Audio-v3-TTS-4B-GGUF/higgs-audio-v3-tts-4b-q8_0.gguf"
```

Or pass `--cli` and `--model` on any command.

## 5. Check

```bash
voiceclone doctor
```

You want `Ready.` at the bottom. ffmpeg is only needed for `voiceclone ref`.

## Troubleshooting

| Problem                        | Fix                                                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `MISS audio.cpp CLI`           | `AUDIOCPP_CLI` must be the full path to the executable, not the folder                                             |
| Every line fails at once       | Run the CLI by hand with `--list-devices`. Usually the cudart archive is missing or the CUDA versions do not match |
| Very slow, GPU usage low       | Another app holds VRAM and the model spilled into shared memory. Close games, browsers with video, other AI tools  |
| One line keeps failing         | Shorten it, split it at a comma, or change `--seed`                                                                |
| A voice loops or babbles often | The reference clip or its transcript is off. Re-cut it: see RECORDING.md. Then try another `--seed`                |
| Out of memory                  | Lower `--batch-size`, close other GPU apps                                                                         |
| QC crashes on `--device cuda`  | Use the default CPU device. It is fast enough with the `small` model                                               |
