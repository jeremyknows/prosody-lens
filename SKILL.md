---
name: prosody-lens
description: >
  Use when audio is available and the user asks about prosody, cadence, delivery,
  pacing, pauses, pitch, emphasis, speech maps, or comparing takes. Not for
  transcript-only feedback.
license: MIT
compatibility: >
  Requires Python 3.9+, numpy, ffmpeg, and ffprobe. No API key required.
  Optional higher-fidelity upgrades: Praat/Parselmouth, WhisperX or Montreal
  Forced Aligner, openSMILE, librosa, Plotly.
metadata:
  author: jeremyknows
  version: "0.9.0"
  category: Audio Analysis & Visualization
  status: EXPERIMENTAL
  last_improved: "2026-06-28"
---

# Prosody Lens

Tool-backed prosody analysis for voice memos. Prosody means the measurable
delivery layer of speech: pitch movement, loudness, rhythm, timing, pauses,
stress, emphasis, and phrase contour.

This is not a clinical or diagnostic tool. It can describe delivery patterns and
surface coaching observations, but it must not diagnose speech disorders,
medical conditions, emotional state, or intent.

## When To Use

Use this skill when the user:
- uploads an audio file and asks how the voice sounds
- asks for prosody, cadence, rhythm, pitch, emphasis, pauses, or vocal variety
- wants to identify or visualize prosodic patterns in speech/accent work
- provides a clip that is already known to contain a prosodic pattern
- wants a visual report of a voice memo
- wants to compare delivery across takes
- wants a repeatable process for speech, narration, teaching, presentation, or
  voice-coaching feedback

Do not use this skill for transcript-only writing feedback unless no audio is
available. Prosody analysis without acoustic data is mostly guesswork.

## Dependencies

Required local tools:
- Python 3.9+
- `numpy`
- `ffmpeg`
- `ffprobe`

Optional higher-fidelity tools:
- Praat/Parselmouth for serious pitch, intensity, duration, and spectrogram work
- WhisperX or Montreal Forced Aligner for word/phoneme alignment
- openSMILE for standardized acoustic feature sets
- librosa and Plotly for richer future visualization work

No API key is required for the bundled analyzer. Hosted transcription tools such
as Groq Whisper are optional and require explicit approval for the specific file.

Optional Praat setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements-praat.txt
```

## Modes

| Mode | Invocation | Output |
|------|------------|--------|
| Analyze | "analyze this voice memo" / `--analyze` | Markdown report + JSON metrics |
| Visualize | "visualize the prosody" / `--viz` | Interactive HTML report + Markdown; quiet-edge auto-focus when needed |
| Visual Export | "visual only" / "download just the image" | Toggle a low-text visual view, choose Map/Card/Library layouts, float sparse transcript words over arcs when available, and export the active PNG |
| Compare | "compare these two takes" / `--compare` | Run one report per take, then synthesize differences |
| Progression | "show progression over time" / `--progression` | Append/read trend records and compare stable metrics |
| Pattern Discovery | "find prosodic patterns" / `--patterns` | Candidate contour patterns, repeat families, and pattern visuals |
| Known Pattern | "visualize this known pattern" / `--pattern-label` | Label the exemplar, then show contour candidates and visual options |
| Pattern Library | "build/match the pattern library" / `--pattern-library` | Save analyst-approved exemplars and match future clips against them |
| Pattern Review | "review/approve/rename pattern candidates" | Use the HTML Pattern Review Workbench to export an approval/rejection JSON payload |
| High Fidelity | "use Praat/DTW" / `--pitch-method praat` + `--library-match-method dtw` | Praat/Parselmouth pitch/intensity plus DTW exemplar matching |
| Coach | "coach this delivery" / `--coach` | Analysis plus practical delivery suggestions |

Default mode is Analyze + Visualize when an audio file is present.

## Recommended Workflow

1. **Confirm input.** Identify the audio file path, the speaker goal if given,
   and whether the user supplied a script/transcript.
2. **Run the analyzer.**

```bash
python3 <skill-root>/scripts/prosody_analyze.py \
  /absolute/path/to/audio.ogg \
  --out-dir ./analysis/prosody/<slug> \
  --pitch-method auto \
  --speaker speaker-1 \
  --goal clarity \
  --take-label baseline \
  --history ./analysis/prosody/prosody-history.jsonl
```

If the user provides an audio clip already identified as a prosodic pattern:

```bash
python3 <skill-root>/scripts/prosody_analyze.py \
  /absolute/path/to/pattern-clip.ogg \
  --out-dir ./analysis/prosody/<slug> \
  --pattern-label "known rising terminal contour" \
  --pattern-notes "label supplied by analyst"
```

If the user wants to build or reuse a pattern library:

```bash
cp <skill-root>/references/pattern-library-starter.json ./analysis/prosody/pattern-library.json
python3 <skill-root>/scripts/prosody_analyze.py \
  /absolute/path/to/pattern-clip.ogg \
  --out-dir ./analysis/prosody/pattern-exemplar \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --save-pattern-label "analyst-approved contour label" \
  --save-pattern-rank 1
python3 <skill-root>/scripts/prosody_analyze.py \
  /absolute/path/to/new-clip.ogg \
  --out-dir ./analysis/prosody/new-clip \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --library-match-method hybrid
```

If the user supplied a transcript:

```bash
python3 <skill-root>/scripts/prosody_analyze.py \
  /absolute/path/to/audio.ogg \
  --transcript /absolute/path/to/transcript.txt \
  --out-dir ./analysis/prosody/<slug>
```

3. **Read the outputs.**
   - `report.md`: delivery summary, listen-first moments, metrics, guardrails
   - `report.html`: standalone visual report with embedded audio by default
   - `prosody.json`: schema v0.5 metrics, synthesis, session, analyzer method,
     trend metrics, pattern analysis, pattern-library matches, progression
     segments, and time series
   - `audio.wav`: normalized mono WAV used for analysis unless `--share-safe`
   - `audio.mp3`: browser-friendly playback copy embedded in `report.html`
     unless `--share-safe` is used
   - `prosody-history.jsonl`: optional compact longitudinal records when
     `--history` is supplied
4. **Answer in human terms.** Translate metrics into useful observations:
   "steady pacing with long pauses before key points", not "RMS variance 8.2 dB"
   unless the user asked for technical detail.
5. **State limitations.** Mention if pitch tracking was basic/fallback, if the
   audio was noisy, if no transcript was supplied, or if word-level alignment was
   unavailable.

### Pattern Review Workbench

When the request involves approving, rejecting, renaming, or building a pattern
library:

1. Open `report.html`.
2. Use `Pattern Lens` cards or the `Pattern Candidates` table to choose a
   candidate.
3. In `Pattern Review Workbench`, listen to the span, set the decision
   (`Approve`, `Needs review`, or `Reject`), edit the analyst label/pattern ID,
   and add notes.
4. Copy or download the JSON payload.
5. If approved, apply it with the included `suggested_cli` command or rerun the
   analyzer with `--pattern-library`, `--save-pattern-label`, and
   `--save-pattern-rank`.

The HTML is static and does not write to disk by itself. The exported payload is
the handoff object an agent can use to update `pattern-library.json` without
guessing which candidate the analyst meant.

### Visual-Only Sharing

When the user wants fewer words or a shareable visual:

1. Open `report.html`.
2. Click `Visual only` to hide summaries, tables, limitations, and review text.
3. Choose the visual layout: `Map` for analysis, `Card` for a shareable image,
   or `Library` for pattern comparison.
4. If a transcript is supplied, expect sparse words to float above the inflection
   arcs as approximate visual anchors, not word-level forced alignment.
5. Click `Download image` to export the active visual snapshot as a PNG.

The PNG export is generated locally from the report's embedded SVG; it does not
upload audio or call an external screenshot service.

## Report Shape

Use this structure when replying:

```markdown
## Prosody Readout
- Overall pattern:
- Strongest delivery signal:
- Pacing and pauses:
- Pitch and vocal variety:
- Emphasis:
- Visualization:
- Limitations:

## Practical Notes
1. ...
2. ...
3. ...
```

For chat surfaces, default to summarizing `report.md`. Before attaching or
linking `report.html` outside the local machine, state whether it embeds raw
voice audio and confirm that sharing the audio is approved. Use `--share-safe`
when the user wants a report that omits the audio player and raw audio copy.

## Interpretation Rules

- Treat pitch, intensity, and pause metrics as evidence, not verdicts.
- Treat pattern labels as descriptive contour sketches, not phonological or
  accent diagnoses.
- If the user or analyst supplies a known pattern label, preserve that label as
  analyst input and do not "correct" it from fallback metrics alone.
- If the user asks the agent to discover patterns, surface candidates and
  families with confidence language: "candidate", "possible", "listen here",
  "similar contour family".
- Do not infer emotion, honesty, confidence, pathology, or personality from
  prosody alone.
- If the user wants coaching, frame suggestions as experiments:
  "try a shorter pause before the second sentence" rather than "you sound wrong."
- If comparing two takes, normalize around the user's stated goal. A "better"
  take depends on purpose: warmth, clarity, authority, story tension, speed, or
  calm.
- If the audio contains multiple speakers, warn that the bundled analyzer is
  single-speaker oriented and needs diarization before strong conclusions.

## Visualization Guidance

Read `references/interface-design.md` before creating, editing, or reviewing
HTML artifacts. The report should feel like a polished listening instrument, not
a generic data dump. The bundled `report.html` generator is the reference
implementation for palette, spacing, controls, and responsive behavior.
Read `references/pattern-analysis.md` when the request is about identifying,
matching, or visualizing prosodic patterns.
Read `references/pattern-library.md` when the request is about building a
reusable pattern library, saving approved exemplars, or matching future clips to
known examples.

Prefer an interactive HTML report for v1:
- audio player
- active-audio focus that trims long quiet leading/trailing edges from the
  analysis/playback copy while preserving the original input
- waveform
- energy/loudness contour
- pitch contour
- pause bands
- summary cards
- delivery summary
- warm approachable visual theme with clear hierarchy, generous hit targets,
  tabular numbers, balanced headings, and tactile control states
- visual snapshot SVG built from the real waveform, pitch, loudness, pause, and
  top-pattern data
- visual layout selector with `Map`, `Card`, and `Library` views
- sparse transcript word overlays above inflection arcs when `--transcript` is
  supplied
- Visual only toggle that hides word-heavy sections for stakeholder review
- Download image button that exports the active visual snapshot PNG
- top "listen first" moments
- progression snapshot across opening/middle/closing thirds
- pattern lens with normalized contour mini-maps for candidate prosodic shapes
- pattern library status, saved exemplar notes, and nearest approved-example
  matches when `--pattern-library` is supplied
- Pattern Review Workbench for selecting, approving/rejecting, renaming,
  annotating, and exporting candidate review JSON
- pattern candidate table with family IDs and click-to-seek controls
- click-to-seek on waveform, energy, and pitch charts
- synchronized playhead across charts
- scrubber, playback speed, previous/next moment, active-moment looping,
  custom loop duration, and set-loop-from-playhead control
- pause/peak visibility toggles
- review candidate buttons, decision segmented control, label/ID fields, notes,
  copy JSON, and download JSON controls
- visual-only and image-download controls in the main toolbar
- active visual layout controls near the visual snapshot

Static PNG is useful for sharing, but less useful for inspection. Animation is a
later enhancement only if it clarifies timing; do not build animation for theater.

## Progression Over Time

For repeated speech analysis, label each run with `--speaker`, `--goal`,
`--memo-type`, and `--take-label`, and append compact trend records with
`--history`.

Stable trend metrics for v0.5:
- pause ratio
- pause count per minute
- long pause count per minute
- rough pitch variability in semitones
- rough pitch IQR in semitones
- pitch coverage ratio
- intensity standard deviation
- possible acoustic peaks per minute
- speaking rate WPM only when transcript/alignment exists

Compare only like with like. A calm instructional memo should not be judged
against a hype/storytelling take without noting the goal mismatch.

## Toolchain Reference

Read `references/toolchain.md` when:
- the user asks how the analysis works
- the fallback analyzer is not enough
- you need word-level alignment, phoneme-level timing, emotion feature sets, or
  publication-quality visualizations
- the user asks for Praat/Parselmouth or DTW matching
Read `references/pattern-analysis.md` when:
- the user asks for speech/accent pattern discovery
- a known prosodic pattern exemplar is supplied
- you need to explain the difference between waveform, pitch contour, intensity
  contour, rhythm, and pattern families
Read `references/pattern-library.md` when:
- the user wants to build a reusable pattern library
- an analyst accepts/rejects/renames a candidate pattern
- future clips should be matched to approved exemplars

High-fidelity path:
- Praat/Parselmouth for pitch, intensity, duration, spectrogram, jitter/shimmer
- DTW matching for variable-speed contour similarity against approved examples
- WhisperX or Montreal Forced Aligner for word/phoneme timing
- openSMILE for standardized acoustic feature sets
- librosa + Plotly for richer visual reports

Praat/Parselmouth is optional. The bundled script still runs with only Python,
numpy, ffmpeg, and ffprobe; `--pitch-method auto` uses Praat when installed and
falls back otherwise.

## Output Scorecard

Read `references/output-scorecard.md` before reviewing publish-quality outputs.
Minimum acceptable report quality is 14/15, with these mandatory:
- analyzer ran on the actual audio
- JSON, Markdown, and HTML artifacts exist
- pattern requests include `pattern_analysis` in `prosody.json`
- pattern-library or review requests include a usable Pattern Review Workbench
  in `report.html`
- visual-sharing requests include working `Visual only` and `Download image`
  controls, plus `Map`, `Card`, and `Library` visual layouts
- transcript-backed visual requests include sparse word overlays on visual arcs
- long dead-air heads/tails are auto-focused and disclosed in `active_audio`
- limitations are stated
- no claims are made about medical conditions, honesty, personality, emotion, or
  intent

## Verification

Before claiming a run is complete:

```bash
python3 <skill-root>/scripts/prosody_analyze.py --help
python3 <skill-root>/scripts/prosody_analyze.py /absolute/path/to/test-audio.ogg \
  --out-dir /tmp/prosody-lens-smoke
test -f /tmp/prosody-lens-smoke/report.html
test -f /tmp/prosody-lens-smoke/prosody.json
```

For HTML/UI changes, open `report.html` and verify:
- audio playback advances without stalls
- seek buttons and chart click-to-seek work
- loop duration and set-loop-from-playhead work
- pause/peak toggles work
- Pattern Review Workbench selects candidates, switches decision state,
  generates valid JSON with `signature`, `sequence`, and `suggested_cli`, and
  copy/download controls are wired
- Visual only hides word-heavy sections without breaking charts, and Download
  image produces a non-empty PNG from the active `Map`, `Card`, or `Library`
  visual snapshot
- transcript word overlays render on visual arcs when a transcript is supplied
- long quiet leading/trailing audio is focused out when it would otherwise squash
  the chart, and `active_audio` records the original/focused durations
- mobile layout has no horizontal overflow
- browser console has no errors

## Cost Posture

Default to local-only analysis. Do not call paid or pay-as-you-go APIs without
explicit operator approval.

Groq Whisper can be used as an optional transcription helper when an existing
free/available Groq key is configured, but it is not required for the bundled
prosody metrics. If Groq is unavailable, run the bundled analyzer anyway and
report that word-level emphasis and speaking-rate metrics need
transcript/alignment to improve.

Before relying on any external API, get explicit per-run approval for this file,
then verify the current free tier, file-size limits, rate limits, and
data-handling posture. Treat hosted transcription as an optional convenience, not
the core engine.

## Known Limitations & Gotchas

1. The bundled pitch tracker is a practical fallback, not a replacement for
   Praat. Use Praat/Parselmouth for serious phonetics work.
2. Without transcript alignment, the report can identify time ranges but cannot
   say which exact word received emphasis.
3. Noise, music, multiple speakers, heavy compression, and room echo can distort
   pitch and energy metrics.
4. Prosody is goal-dependent. The same contour can be effective for storytelling
   and wrong for a calm instructional memo.
5. Clinical interpretation belongs to a qualified speech-language professional.
6. Possible acoustic peaks are not confirmed emphasis; they are ranked places to
   listen first.
