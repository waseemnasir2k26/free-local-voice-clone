# Demo: real voice vs clone

Both clips are the repo author's own voice, published with his consent.

| File | What it is |
|---|---|
| [1-real-voice-15s.mp3](1-real-voice-15s.mp3) | The real recording. These 15 seconds are the only audio the model was given. |
| [2-cloned-voice.mp3](2-cloned-voice.mp3) | Generated on an RTX 4060 laptop. He never said these words. First take, no edits. |

Text of the cloned clip:

> This is not a recording. I typed this sentence, and my laptop said it in my voice. No subscription. No upload. Fifteen seconds of audio was all it needed. The tool is free on GitHub, and you should only ever use it on your own voice.

Made with:

```bash
voiceclone ref --in recording.wav --start 0 --dur 15 --name waseem
voiceclone say --voice waseem "This is not a recording. ..." -o clone.wav
```

This audio was created with Boson AI's Higgs Audio — https://www.boson.ai/higgs-audio

Do not use these clips to clone this voice. That needs his consent, and you do not have it.
