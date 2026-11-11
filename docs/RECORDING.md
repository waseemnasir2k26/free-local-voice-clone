# Recording a reference that clones well

The clone copies whatever is in the clip: your voice, and also your room, your microphone, your mood and your speed. Fifteen good seconds beat five mediocre minutes.

## The clip

- **Length:** 10 to 20 seconds. We use 15.
- **Content:** complete sentences in the language and energy you want back. If you want an upbeat tutorial voice, do not hand it a sleepy clip.
- **One speaker, no music, no laughter, no long pauses.**
- **Quiet room.** Soft furniture helps. A phone held 15 to 20 cm from your mouth is fine. A wardrobe full of clothes is a free vocal booth.
- **Start and end on silence**, not in the middle of a word.

## The transcript matters as much as the audio

The model is given the clip and the exact words in it. A wrong transcript teaches it the wrong sounds, and the clone starts looping or slurring.

`voiceclone ref` writes the transcript for you with Whisper. Open `voices/<name>.txt` and fix every word, including names and numbers, so it matches what you actually said.

## Picking the best 15 seconds

Record two or three minutes of yourself talking normally, then try three different cuts:

```bash
voiceclone ref --in talk.m4a --start 8  --dur 15 --name me_a
voiceclone ref --in talk.m4a --start 41 --dur 15 --name me_b
voiceclone ref --in talk.m4a --start 77 --dur 15 --name me_c

voiceclone say --voice me_a "The same test sentence for every candidate." -o a.wav
voiceclone say --voice me_b "The same test sentence for every candidate." -o b.wav
voiceclone say --voice me_c "The same test sentence for every candidate." -o c.wav
```

Keep the one that sounds most like you. In our own test the three candidates scored 0.89, 0.78 and 0.79 on speaker similarity: same person, same recording, very different clones. It is worth the three minutes.

## Several characters

Each voice is two files in `voices/`: `zoya.wav` and `zoya.txt`. Add as many as you like. If one character loops more than the others, give that voice its own seed by running its lines with `--seed 11`.

## Privacy

`voices/` is in `.gitignore` on purpose. Your reference clip is a key to your voice. Do not commit it, do not post it.
