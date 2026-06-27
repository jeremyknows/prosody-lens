# Prosodic Pattern Library

Use this reference when the goal is to build a reusable body of known prosodic
patterns, not just inspect one clip.

## Opinionated Shape

Do not train a model first. Build an analyst-reviewed pattern library first.
The library should separate three things:

1. **Seed vocabulary**: useful names for contour families.
2. **Approved exemplars**: audio spans a human analyst has accepted as examples.
3. **Machine matches**: similarity scores from new clips to approved exemplars.

The bundled analyzer only trusts item 2 as matching evidence. Seed vocabulary is
there to make labeling faster, not to pretend an empty pattern is a classifier.

## Setup

Copy the starter library into the project or analysis folder:

```bash
cp references/pattern-library-starter.json ./analysis/prosody/pattern-library.json
```

Then save an approved exemplar from the best candidate:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/pattern.ogg \
  --out-dir ./analysis/prosody/pattern-exemplar \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --save-pattern-label "analyst-approved rising terminal contour" \
  --save-pattern-rank 1 \
  --save-pattern-notes "Accepted after listening to the top contour candidate"
```

Then match a future clip against the approved examples:

```bash
python3 scripts/prosody_analyze.py /absolute/path/to/new-clip.ogg \
  --out-dir ./analysis/prosody/new-clip \
  --pattern-library ./analysis/prosody/pattern-library.json \
  --library-match-method hybrid \
  --library-match-threshold 0.62
```

## JSON Schema

The current library schema is intentionally simple:

```json
{
  "schema_version": "0.1",
  "patterns": [
    {
      "id": "rising-terminal-contour",
      "label": "Rising terminal contour",
      "status": "approved",
      "basis": "analyst-approved exemplar",
      "description": "A reviewed contour family.",
      "examples": [
        {
          "example_id": "abc123",
          "source_audio": "pattern.ogg",
          "start": 1.24,
          "end": 2.18,
          "pitch_points_st": [],
          "energy_points_z": [],
          "signature": [],
          "sequence": [],
          "notes": "Why this example matters"
        }
      ]
    }
  ]
}
```

By default, saved examples store the source audio filename, not an absolute local
path. Absolute paths are included only when the run uses `--include-local-paths`.

## Matching Method

For each candidate contour, the analyzer:

1. Resamples pitch and energy into comparable point arrays.
2. Normalizes pitch and energy into a compact signature.
3. Stores a two-channel pitch/energy sequence for DTW matching.
4. Compares the candidate to every approved example.
5. Reports matches above `--library-match-threshold`.

Match methods:

- `correlation`: flat normalized contour signature similarity.
- `dtw`: dynamic time warping over pitch/energy contour sequences.
- `hybrid`: accepts the stronger of correlation and DTW.

A high score means "this shape resembles this approved example." It does not
mean the clip has a confirmed accent feature, emotional state, or clinical
trait.

## Analyst Review Loop

Use this loop with a speech coach or analyst:

1. Run the report.
2. Listen to the top candidates using click-to-seek.
3. Accept, reject, or rename the candidate.
4. Save accepted examples with `--save-pattern-label`.
5. Rerun future clips against the same library.
6. Review false positives and raise the threshold or split patterns when needed.

## When To Upgrade

The JSON library is enough for a portable v1. Upgrade when the work needs:

- Praat/Parselmouth F0 and intensity extraction.
- Word or phoneme alignment via WhisperX or Montreal Forced Aligner.
- A review UI for accept/reject/rename instead of CLI flags.
- Separate train/validation/test folders once there are enough examples.
