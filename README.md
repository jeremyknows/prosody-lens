# Prosody Lens

Prosody Lens analyzes voice memos and speech recordings, then produces a
readable delivery report plus an interactive HTML timeline.

It is local-first: no API key, cloud transcription, or paid service is required
for the bundled analyzer.

## What It Does

- Converts an input audio file into analysis-ready mono WAV.
- Measures pause structure, rough pitch movement, loudness/energy, possible
  acoustic peaks, and opening/middle/closing progression.
- Optionally uses Praat/Parselmouth for higher-fidelity pitch and intensity.
- Surfaces candidate prosodic contour patterns and loose repeat families.
- Saves analyst-approved pattern exemplars into a JSON library.
- Matches future clips against approved pattern-library examples with
  correlation, DTW, or hybrid scoring.
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

Optional Praat/Parselmouth install:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements-praat.txt
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
  --pitch-method auto \
  --speaker speaker-1 \
  --goal clarity \
  --take-label baseline \
  --history ./analysis/prosody/prosody-history.jsonl

open ./analysis/prosody/sample/report.html
```

Known pattern exemplar:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/pattern.ogg \
  --out-dir ./analysis/prosody/known-pattern \
  --pattern-label "analyst supplied label" \
  --pattern-notes "why this clip matters"
```

Build a reusable pattern library:

```bash
cp references/pattern-library-starter.json ./analysis/prosody/pattern-library.json

python3 scripts/prosody_analyze.py /absolute/path/to/pattern.ogg \
  --out-dir ./analysis/prosody/pattern-exemplar \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --save-pattern-label "analyst-approved contour label" \
  --save-pattern-rank 1 \
  --save-pattern-notes "Accepted after listening to candidate #1"

python3 scripts/prosody_analyze.py /absolute/path/to/new-clip.ogg \
  --out-dir ./analysis/prosody/new-clip \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --library-match-method hybrid \
  --library-match-threshold 0.62
```

High-fidelity local run when Praat/Parselmouth is installed:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/audio.ogg \
  --out-dir ./analysis/prosody/praat-run \
  --pitch-method praat \
  --pitch-floor 75 \
  --pitch-ceiling 400
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
| `prosody.json` | Structured metrics, synthesis, analyzer method, session metadata, pattern analysis, trend metrics, progression, and time series. |
| `report.md` | Human-readable summary, listen-first moments, metrics, limitations, and pause map. |
| `report.html` | Standalone interactive report with audio playback, charts, controls, and visual summary. |
| `pattern-library.json` | Optional analyst-reviewed library when `--pattern-library` and `--save-pattern-label` are used. |
| `audio.wav` | Normalized mono WAV used for analysis unless `--share-safe` is used. |
| `audio.mp3` | Browser-friendly playback copy embedded in HTML when available. |
| `prosody-history.jsonl` | Optional compact trend records when `--history` is supplied. |

If MP3 encoding is unavailable in the local ffmpeg build, the HTML falls back to
embedded WAV playback.

## Natural Language Usage

Ask your agent:

- "Analyze this voice memo for prosody and give me practical delivery feedback."
- "Find candidate prosodic patterns in this clip."
- "Visualize this known prosodic pattern exemplar."
- "Save this as an approved pattern and use it to match future clips."
- "Visualize the cadence and pauses in this narration take."
- "Compare these two takes for clarity and pacing."
- "Show progression over time across these recordings."

When audio is available, the agent should run the analyzer rather than relying on
transcript-only impressions.

## Interface Design Direction

Prosody Lens includes explicit HTML/CSS direction for generated artifacts in
`references/interface-design.md`. Agents should use it when creating or editing
`report.html`: warm cream paper, red accent, deep teal structure, tactile
controls, click-to-seek charts, tabular metrics, mobile-safe wrapping, and
reduced-motion support.

## Pattern Library Workflow

The library workflow is the serious path for speech-pattern work:

1. Start from `references/pattern-library-starter.json`.
2. Run a report on a known or suspected pattern clip.
3. Listen to the top candidate cards in `report.html`.
4. Save the accepted candidate with `--save-pattern-label`.
5. Run future clips with the same `--pattern-library`.
6. Review `Pattern Library Matches` in the HTML report and `prosody.json`.
7. Use `--library-match-method dtw` or `hybrid` when contour timing varies
   across examples.

Seed patterns are vocabulary only. They become matchable only after approved
examples are saved. This keeps the analyzer honest: it reports contour
similarity to known examples, not unsupported accent diagnoses.

## Privacy And Sharing

Default `report.html` embeds a playable copy of the raw voice audio. Treat it as
private audio, not just a metrics report. Use `--share-safe` when the report may
be shared without the underlying voice recording.

The bundled analyzer runs locally. Do not upload private audio to third-party
APIs unless the user explicitly approves the specific file, cost posture, and
data-handling tradeoff.

## Limitations

- Praat/Parselmouth is optional. Without it, the analyzer uses a practical
  fallback pitch tracker.
- Pattern labels are descriptive contour sketches, not accent diagnoses.
- Pattern-library matching is contour similarity against approved examples. DTW
  helps compare variable-speed contours, but it is not a final phonological
  classifier.
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
| `Praat/Parselmouth requested but unavailable` | Optional Praat dependency is not installed in the active Python environment. | Create a venv and install `-r requirements.txt -r requirements-praat.txt`, or rerun with `--pitch-method fallback`. |
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
python3 scripts/prosody_analyze.py /absolute/path/to/test-audio.ogg \
  --out-dir /tmp/prosody-lens-library-smoke \
  --pattern-library /tmp/prosody-lens-pattern-library.json \
  --save-pattern-label "smoke test contour" \
  --library-match-method hybrid
test -f /tmp/prosody-lens-smoke/report.html
test -f /tmp/prosody-lens-smoke/prosody.json
test -f /tmp/prosody-lens-pattern-library.json
```

For UI changes, open `report.html` and verify audio playback, chart click-to-seek,
loop duration controls, mobile layout, and no console errors.
