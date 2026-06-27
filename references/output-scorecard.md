# Prosody Lens Output Scorecard

Use this checklist when reviewing a generated Prosody Lens report.

Score each item yes/no:

1. The analyzer was run on the audio file; the response is not transcript-only.
2. `prosody.json`, `report.md`, and `report.html` were generated.
3. The summary covers pacing/pauses, rough pitch movement, loudness/energy, and
   possible acoustic peaks.
4. The report states limitations for fallback pitch tracking and missing
   transcript/alignment when relevant.
5. The HTML report plays audio or the run was explicitly `--share-safe`.
6. Interactive controls work: play/pause, scrubber, chart click-to-seek,
   previous/next moment, loop duration, and pause/peak toggles.
7. If comparing or tracking progression, each run includes speaker, goal, memo
   type, take label, and/or history metadata.
8. The interpretation avoids claims about medical conditions, honesty,
   personality, emotion, or intent.
9. If a pattern library is supplied, the report shows library status, saved
   exemplar metadata when relevant, and nearest approved-example matches.

Passing threshold for publish-quality outputs: 8/9, with items 1, 2, 4, 8, and 9
required.
