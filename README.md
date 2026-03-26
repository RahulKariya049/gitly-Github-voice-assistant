# Gitly-Github-voice-assistant

A voice-controlled Git assistant. Speak your Git commands, Gitly runs them.

Project is being built. But the core is real and the architecture is being written.

---

## What it does

- Wake word detection — say a trigger phrase, Gitly activates
- Natural language Git commands — "commit recent changes with message fix navbar" just works
- Handles push, pull, commit, add, checkout, merge, status, init, remote
- Fuzzy intent matching — understands typos, casual phrasing, filler words
- Session memory — remembers which repo you're working in
- Caches recent repositories — switch between projects by name
- TTS feedback — Gitly talks back
- Post-execution error parsing — detects merge conflicts and failures from stderr

---

## What's not finished

- **STT is mocked** — voice input currently uses `input()` instead of a real microphone. The full audio pipeline (Butterworth bandpass filter, noise reduction, normalization, Google STT + Vosk) is written and was working but offline STT accuracy wasn't good enough to be usable. Whisper was too RAM heavy for CPU-only. This is the one unsolved piece.
- **Repo path resolution** — being reworked. Currently being simplified to `input()` based path paste instead of voice-guided filesystem navigation.
- **No tests** — written fast, tested manually.

---

## Architecture

```
Wake Word Detection (fuzzy match)
        ↓
GitlySession — runtime state, active repo, entities
        ↓
recognize_speech() — audio pipeline (mocked with input() for now)
        ↓
process_command() — main brain
        ↓
    NLP Pipeline (intent.py)
    normalize → fuzzy synonym translation → regex rewrite → intent detection → entity extraction
        ↓
    Path / Repo Resolution (path.py)
        ↓
    Executor (executor.py)
    subprocess git commands → stderr parsing → error handler
        ↓
TTS feedback + cache dump
        ↓
Gitly sleeps, waits for next wake word
```

---

## Stack

- Python 3.13
- `rapidfuzz` — fuzzy matching for intent and repo names
- `SpeechRecognition` + `vosk` — STT backends (currently mocked)
- `scipy` + `noisereduce` — audio preprocessing
- `subprocess` — git command execution
- JSON — session cache

---

## How to run

```bash
git clone https://github.com/RahulKariya049/gitly-Github-voice-assistant
cd gitly
pip install -r requirements.txt
python main.py
```

Then type your commands when prompted (voice input is mocked for now).

Wake word examples:
- `activate voice assistant`
- `launch my assistant`
- `open command centre`

---

## Why I built this

Wanted a hands-free Git workflow. Ended up going deep into NLP pipeline design, audio signal processing, and modular Python architecture. Hit a real wall with offline STT — every option was either too inaccurate, too heavy, or behind a paid API. Shelved it mid-development, coming back to fix the STT piece.

---

## Status

**Work in progress.** Core NLP pipeline and executor are functional. STT and repo resolution are being fixed. Not ready for daily use yet.