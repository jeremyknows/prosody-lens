# Prosody Lens

Prosody Lens analyzes voice memos and speech recordings, then produces a
readable delivery report plus an interactive HTML timeline.

It is local-first: no API key, cloud transcription, or paid service is required
for the bundled analyzer.

## What It Does

- Converts an input audio file into analysis-ready mono WAV.
- Measures pause structure, rough pitch movement, loudness/energy, possible
  acoustic peaks, and opening/middle/closing progression.
- Generates `prosody.json`, `report.md`, and an interactive `report.html`.
- Embeds browser-friendly MP3 playback in the HTML by default.
- Supports repeated-run trend records with `--history`.
- Keeps clinical and emotional interpretation out of scope.

## Requirements

Required:
- Python 3.11+
- `numpy`
- `ffmpeg`
- `ffprobe`

Optional:
- Praat/Parselmouth for higher-fidelity pitch and intensity analysis.
- WhisperX or Montreal Forced Aligner for transcript/word alignment.
- openSMILE for standardized acoustic feature extraction.
- librosa or Plotly for richer future visualizations.

No API key is required. Groq Whisper or other hosted transcription tools are
optional and should only be used with explicit approval for the specific file.

## Install

From a published GitHub repo:

```bash
npx skills add jeremyknows/prosody-lens
```

Manual local install:

```bash
git clone https://github.com/jeremyknows/prosody-lens.git ~/.codex/skills/prosody-lens
cd ~/.codex/skills/prosody-lens
python3 -m pip install -r requirements.txt
```

## Setup Check

Run these before the first analysis:

```bash
python3 --version
python3 - <<'PY'
import numpy
print("numpy", numpy.__version__)
PY
ffmpeg -version | head -1
ffprobe -version | head -1
python3 scripts/prosody_analyze.py --help
```

If `ffmpeg` is missing on macOS:

```bash
brew install ffmpeg
```

## Quick Start

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/audio.ogg \
  --out-dir ./analysis/prosody/sample \
  --speaker speaker-1 \
  --goal clarity \
  --take-label baseline \
  --history ./analysis/prosody/prosody-history.jsonl

open ./analysis/prosody/sample/report.html
```

With a transcript:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/audio.ogg \
  --transcript /absolute/path/to/transcript.txt \
  --out-dir ./analysis/prosody/sample-with-transcript
```

Share-safe report without embedded audio:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/audio.ogg \
  --out-dir ./analysis/prosody/share-safe \
  --share-safe
```

## Outputs

| File | Purpose |
| --- | --- |
| `prosody.json` | Structured metrics, synthesis, session metadata, trend metrics, progression, and time series. |
| `report.md` | Human-readable summary, listen-first moments, metrics, limitations, and pause map. |
| `report.html` | Standalone interactive report with audio playback, charts, controls, and visual summary. |
| `audio.wav` | Normalized mono WAV used for analysis unless `--share-safe` is used. |
| `audio.mp3` | Browser-friendly playback copy embedded in HTML when available. |
| `prosody-history.jsonl` | Optional compact trend records when `--history` is supplied. |

If MP3 encoding is unavailable in the local ffmpeg build, the HTML falls back to
embedded WAV playback.

## Natural Language Usage

Ask your agent:

- "Analyze this voice memo for prosody and give me practical delivery feedback."
- "Visualize the cadence and pauses in this narration take."
- "Compare these two takes for clarity and pacing."
- "Show progression over time across these recordings."

When audio is available, the agent should run the analyzer rather than relying on
transcript-only impressions.

## Privacy And Sharing

Default `report.html` embeds a playable copy of the raw voice audio. Treat it as
private audio, not just a metrics report. Use `--share-safe` when the report may
be shared without the underlying voice recording.

The bundled analyzer runs locally. Do not upload private audio to third-party
APIs unless the user explicitly approves the specific file, cost posture, and
data-handling tradeoff.

## Limitations

- The bundled pitch tracker is a practical fallback, not a replacement for
  Praat/Parselmouth.
- Possible acoustic peaks are ranked places to listen first, not confirmed
  emphasized words.
- Word-level emphasis and speaking rate need transcript/word alignment.
- Noise, music, multiple speakers, heavy compression, and echo can distort
  metrics.
- This skill is descriptive only. It must not diagnose medical conditions,
  personality, honesty, emotion, or intent.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ffmpeg is required but was not found` | ffmpeg is not installed or not on `PATH`. | Install ffmpeg and rerun `ffmpeg -version`. |
| `ModuleNotFoundError: numpy` | Python dependency missing. | Run `python3 -m pip install -r requirements.txt`. |
| HTML audio plays choppily | Browser dislikes the embedded playback format. | Regenerate with the latest skill; it embeds MP3 by default and falls back to WAV only if needed. |
| Pitch numbers look wrong | Fallback pitch tracker is low fidelity or audio is noisy. | Treat pitch as rough, or rerun with Praat/Parselmouth in a higher-fidelity pipeline. |
| Report should be shared but audio is private | Default HTML embeds raw voice audio. | Rerun with `--share-safe`. |

## Verification

Before publishing or sharing a new build:

```bash
npx skills-ref validate .
python3 scripts/prosody_analyze.py --help
python3 scripts/prosody_analyze.py /absolute/path/to/test-audio.ogg \
  --out-dir /tmp/prosody-lens-smoke
test -f /tmp/prosody-lens-smoke/report.html
test -f /tmp/prosody-lens-smoke/prosody.json
```

For UI changes, open `report.html` and verify audio playback, chart click-to-seek,
loop duration controls, mobile layout, and no console errors.
