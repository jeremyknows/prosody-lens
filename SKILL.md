---
name: prosody-lens
description: >
  Use when audio is available and the user asks about prosody, cadence, delivery,
  pacing, pauses, pitch, emphasis, speech maps, or comparing takes. Not for
  transcript-only feedback.
license: MIT
compatibility: >
  Requires Python 3.11+, numpy, ffmpeg, and ffprobe. No API key required.
  Optional higher-fidelity upgrades: Praat/Parselmouth, WhisperX or Montreal
  Forced Aligner, openSMILE, librosa, Plotly.
metadata:
  author: jeremyknows
  version: "0.2.4"
  category: Audio Analysis & Visualization
  status: EXPERIMENTAL
  last_improved: "2026-06-27"
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
- wants a visual report of a voice memo
- wants to compare delivery across takes
- wants a repeatable process for speech, narration, teaching, presentation, or
  voice-coaching feedback

Do not use this skill for transcript-only writing feedback unless no audio is
available. Prosody analysis without acoustic data is mostly guesswork.

## Dependencies

Required local tools:
- Python 3.11+
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

## Modes

| Mode | Invocation | Output |
|------|------------|--------|
| Analyze | "analyze this voice memo" / `--analyze` | Markdown report + JSON metrics |
| Visualize | "visualize the prosody" / `--viz` | Interactive HTML report + Markdown |
| Compare | "compare these two takes" / `--compare` | Run one report per take, then synthesize differences |
| Progression | "show progression over time" / `--progression` | Append/read trend records and compare stable metrics |
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
  --speaker jeremy \
  --goal clarity \
  --take-label baseline \
  --history ./analysis/prosody/prosody-history.jsonl
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
   - `prosody.json`: schema v0.2 metrics, synthesis, session, trend metrics,
     progression segments, and time series
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

Prefer an interactive HTML report for v1:
- audio player
- waveform
- energy/loudness contour
- pitch contour
- pause bands
- summary cards
- delivery summary
- warm approachable visual theme with clear hierarchy, generous hit targets,
  tabular numbers, balanced headings, and tactile control states
- top "listen first" moments
- progression snapshot across opening/middle/closing thirds
- click-to-seek on waveform, energy, and pitch charts
- synchronized playhead across charts
- scrubber, playback speed, previous/next moment, active-moment looping,
  custom loop duration, and set-loop-from-playhead control
- pause/peak visibility toggles

Static PNG is useful for sharing, but less useful for inspection. Animation is a
later enhancement only if it clarifies timing; do not build animation for theater.

## Progression Over Time

For repeated speech analysis, label each run with `--speaker`, `--goal`,
`--memo-type`, and `--take-label`, and append compact trend records with
`--history`.

Stable trend metrics for v0.2:
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

High-fidelity path:
- Praat/Parselmouth for pitch, intensity, duration, spectrogram, jitter/shimmer
- WhisperX or Montreal Forced Aligner for word/phoneme timing
- openSMILE for standardized acoustic feature sets
- librosa + Plotly for richer visual reports

Ask before installing new dependencies. The bundled script intentionally stays
limited to Python, numpy, ffmpeg, and ffprobe.

## Output Scorecard

Read `references/output-scorecard.md` before reviewing publish-quality outputs.
Minimum acceptable report quality is 7/8, with these mandatory:
- analyzer ran on the actual audio
- JSON, Markdown, and HTML artifacts exist
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
- mobile layout has no horizontal overflow
- browser console has no errors

## Cost Posture

Default to local-only analysis. Do not call paid or pay-as-you-go APIs without
explicit operator approval.

Groq Whisper can be used as an optional transcription helper when an existing
free/available Groq key is configured, but it is not required for v0 prosody
metrics. If Groq is unavailable, run the bundled analyzer anyway and report that
word-level emphasis and speaking-rate metrics need transcript/alignment to
improve.

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
