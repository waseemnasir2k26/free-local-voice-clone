# Urdu and Roman Urdu notes

Learned while voicing an Urdu talk show (AI Baithak) with six character voices.

## What works

- **Everyday Urdu mixed with English.** Write the way people actually talk. Heavy literary Urdu sounds stiff and gets more mistakes.
- **English for tech words.** Write `GitHub`, `workflow`, `email` in English inside an Urdu line. The model switches cleanly.
- **Numbers above ten in English words.** "twenty five" is read more reliably than "25" or "pachees".
- **Roman Urdu works.** `Agar aap copy paste kar sakte hain, toh aap yeh bhi kar sakte hain.` is voiced correctly. If a long Roman Urdu line loops, split it at the comma into two lines.
- **Reference clip in the same language** you plan to generate. An Urdu clip gives better Urdu.

## Pacing

Pass `--lang ur` for Urdu-script lines. It only changes two things: the expected length of a line (Urdu runs a little slower per character) and the language Whisper listens for in QC.

## QC on Urdu

- **Urdu script lines:** QC works. English words inside the line come back in Latin letters and raise the score, so treat a flag as "listen to this one".
- **Roman Urdu lines:** the score is not meaningful. Whisper writes Urdu script, or translates to English, and neither matches your Roman text. The length gate still catches clipped and looping takes. Spot-check by ear.

## Pronunciation table

Names the model gets wrong go in a JSON file:

```json
{
  "n8n": "N, eight, N",
  "SkynetLabs": "Sky net labs"
}
```

```bash
voiceclone batch --voice me --file script.txt --respell my-words.json --out takes
```
