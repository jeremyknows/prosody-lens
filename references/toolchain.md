# Prosody Lens Toolchain Reference

This reference explains the tool choices behind Prosody Lens.

## What Prosody Measures

Prosody is the delivery layer of speech:
- pitch and intonation
- loudness and intensity
- stress and emphasis
- rhythm and phrase timing
- pause placement and duration
- speaking rate and articulation rate
- voice quality signals such as jitter/shimmer when measured with proper tools

Prosody is not a single score. Treat it as a set of contours and timing patterns
that need interpretation against a goal.

## Recommended Tool Stack

### Praat / Parselmouth

Use for serious acoustic analysis:
- F0/pitch contour
- intensity contour
- spectrogram
- formants
- jitter/shimmer
- TextGrid-style annotation workflows

Parselmouth exposes Praat from Python, which makes it the best high-fidelity
upgrade for this skill.

### WhisperX

Use when the user supplies audio but no transcript. WhisperX can produce
transcription plus word-level timestamps via forced alignment. This enables
word-level emphasis maps.

### Montreal Forced Aligner

Use when the transcript/script is known and accuracy matters. MFA is heavier to
install and configure, but better for word and phoneme alignment workflows.

### openSMILE

Use for standardized acoustic feature extraction, especially if the project
needs comparable feature sets across many recordings. Avoid presenting
openSMILE features directly to nontechnical users; summarize them.

### librosa + Plotly

Use for richer visualization:
- spectrograms
- waveform overlays
- pitch/intensity traces
- interactive zoom/hover HTML reports

## Minimum Viable Analyzer

The bundled `scripts/prosody_analyze.py` is intentionally dependency-light:
- ffmpeg converts input audio to mono WAV
- Python stdlib reads WAV samples
- numpy computes waveform, RMS energy, pauses, and a basic autocorrelation
  pitch estimate
- optional Praat/Parselmouth extracts higher-fidelity F0 and intensity when
  installed and selected with `--pitch-method auto` or `--pitch-method praat`
- the script emits JSON, Markdown, and standalone HTML

This is enough to prove the skill shape and create useful first-pass reports.
It is not enough for clinical phonetics, precise word emphasis, or noisy audio.

## Output Metrics

Recommended JSON/report fields:
- duration seconds
- voiced duration seconds
- pause count
- pause total seconds
- longest pause seconds
- pause ratio
- median pitch Hz
- pitch range Hz
- pitch variability in semitones
- median intensity dB
- intensity range dB
- speaking rate WPM when transcript is supplied
- possible acoustic peak time ranges
- session metadata for repeated runs
- compact trend metrics for longitudinal comparison
- opening/middle/closing progression segments
- candidate prosodic contour patterns
- loose repeated contour families
- optional pattern-library status, saved exemplar metadata, and approved-example
  match scores, including correlation and DTW components when available

## Visualization Design

Recommended v1 visual report:
- audio player
- low-text Map/Card/Library visual snapshots with local PNG download for
  stakeholder review
- waveform track
- pitch contour track
- intensity contour track
- pause bands
- metric cards
- delivery summary
- "listen first" acoustic peak moments
- progression snapshot
- pattern contour cards and motif table
- visual-only toggle for hiding word-heavy sections
- active-layout PNG export from the selected Map, Card, or Library snapshot
- pattern library match table when `--pattern-library` is supplied

Recommended v2:
- word-level transcript lane
- hover over a word to see pitch/intensity/duration
- compare two takes with aligned phrase timing
- stronger exemplar matching with dynamic time warping
- recurrence/heatmap view for repeated contour shapes

## Pattern Library

The bundled analyzer supports a portable JSON pattern library. Use it before
training any model:

- seed vocabulary lives in `references/pattern-library-starter.json`
- analyst-approved examples are saved with `--save-pattern-label`
- future clips are matched with `--pattern-library`
- match scores compare normalized pitch and energy contour signatures
- `--library-match-method correlation` uses flat contour correlation
- `--library-match-method dtw` uses dynamic time warping over pitch/energy
  contour sequences
- `--library-match-method hybrid` accepts the stronger of correlation and DTW

This gives the project a reviewable dataset: which labels were accepted, where
in the audio they occurred, what contour was saved, and which future candidates
resembled them.

## Optional Praat/Parselmouth

Use a virtual environment; do not force this dependency on every install:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements-praat.txt
```

Run:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/audio.ogg \
  --out-dir ./analysis/prosody/praat-run \
  --pitch-method praat
```

`--pitch-method auto` uses Praat when `parselmouth` imports successfully and
falls back to the bundled autocorrelation method otherwise. `--pitch-method
praat` fails loudly if Praat cannot be used.

Avoid v1 animation unless timing is otherwise hard to understand.

## Safety And Privacy

- Do not upload private audio to third-party APIs unless the user approves.
- Default to local-only analysis. Avoid paid or pay-as-you-go APIs unless the
  operator explicitly approves the cost and data-handling tradeoff.
- Groq Whisper may be acceptable for lightweight transcription when an existing
  free/available key is configured, but verify current limits before depending
  on it.
- Standalone HTML can embed raw voice audio. Treat it as private audio, not just
  a metrics report. Use share-safe output when audio should not travel.
- Do not infer medical conditions, identity traits, honesty, or emotion from
  prosody alone.
- Keep raw audio local unless the user explicitly asks to share or publish.
