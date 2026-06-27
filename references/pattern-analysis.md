# Prosodic Pattern Analysis

Use this reference when the task is not "summarize the whole voice memo" but
"show me the prosodic pattern."

## The Target Shift

Prosody Lens v0.2 was a whole-clip report: duration, pauses, rough pitch,
loudness, acoustic peaks, and playback. Speech/accent analysis often needs a
smaller unit: the recurring contour pattern inside the audio.

The useful object is not the waveform itself. The waveform is the raw pressure
trace. Pattern analysis should derive inspectable contours from it:

- pitch/F0 movement
- intensity/loudness movement
- pause boundaries and phrase timing
- duration and rhythm of phrase-like spans
- repeated contour families within a clip

## Two Workflows

### 1. Known Pattern Exemplar

Use when the analyst supplies a clip that is already known to contain a pattern.

Run:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/pattern.ogg \
  --out-dir ./analysis/prosody/known-pattern \
  --pattern-label "analyst supplied label" \
  --pattern-notes "why this clip matters"
```

What to preserve:

- the analyst's label
- the exact audio span
- candidate contour shapes surfaced by the analyzer
- limitations: the local fallback can visualize the contour, but should not
  rename or diagnose the pattern by itself

### 2. Unknown Pattern Discovery

Use when the analyst supplies a clip and wants candidate patterns found.

The bundled analyzer scans pause-bounded phrase spans and sliding phrase windows,
then emits:

- `pattern_analysis.summary`
- ranked `pattern_analysis.candidates`
- contour `family_id` groups when similar shapes repeat
- normalized pitch mini-contours
- normalized energy mini-contours
- pause-before and pause-after context

Use this language:

- "candidate contour"
- "possible family"
- "listen-first pattern"
- "similar shape repeats"

Do not say:

- "this is definitely X accent"
- "this proves Y emotion"
- "this is a phonological diagnosis"

## Visualization Options

Show more than the waveform. Good pattern artifacts can include:

1. **Contour Map** — mini-cards for each candidate pattern. Each card overlays
   normalized pitch and energy shape, with a click-to-seek timestamp.
2. **Motif Table** — ranked candidates with family IDs, start/end, contour
   label, pitch range, and energy range.
3. **Timeline Overlay** — candidate spans over the full audio timeline, so the
   analyst can see where patterns cluster.
4. **Future Recurrence Matrix** — a heatmap of similar contour windows. Useful
   once the project needs stronger repeated-pattern discovery.
5. **Future Aligned Transcript Lane** — words/phonemes under the contour. This
   needs WhisperX or Montreal Forced Aligner.

## Current Local Method

The dependency-light v0.3 method:

1. Convert audio to mono WAV.
2. Estimate RMS energy and rough pitch.
3. Detect pauses and phrase-like spans.
4. Split long spans into sliding phrase windows.
5. Resample pitch and energy inside each span.
6. Normalize contours so shape is visible independent of absolute pitch/loudness.
7. Label rough contour shapes:
   - rising contour
   - falling contour
   - rise-fall arc
   - fall-rise arc
   - wavy contour
   - energy build/taper
   - level/subtle contour
8. Group repeated candidates into loose contour families.

This is intentionally conservative. It is a discovery and visualization aid, not
a final speech-science classifier.

## Upgrade Path

For serious speech/accent analysis:

- Praat/Parselmouth for stronger F0/intensity extraction.
- WhisperX or Montreal Forced Aligner for word/phoneme alignment.
- Dynamic time warping for exemplar-vs-clip matching.
- Recurrence plots or motif clustering for repeated contour discovery.
- Analyst review loop where the expert accepts/rejects candidate families.
