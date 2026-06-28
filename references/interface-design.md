# Interface Design Direction

Use this reference whenever Prosody Lens creates or modifies an HTML artifact.
The goal is a warm, approachable listening tool that still feels precise enough
for speech analysis.

## Visual Principles

- Make the audio and charts feel inspectable: obvious playback controls,
  click-to-seek charts, synced playhead, and readable time labels.
- Favor a calm editorial/workbench feel over a technical dashboard. The report
  should be comfortable to share with a non-technical collaborator.
- Include low-text visual snapshots for stakeholder review. They should stand on
  their own as images: `Map` for analysis, `Card` for sharing, and `Library` for
  pattern comparison.
- When a transcript is supplied, show sparse words as dot-on-arc,
  connector-line, translucent-card callouts above inflection arcs. Treat them as
  approximate visual anchors, not forced-aligned word timing.
- In low-text Map/Card/Library snapshots, draw pitch as a smoothed presentation
  contour. Keep raw frame-level pitch data available for metrics and JSON, but
  do not let jitter or octave-tracking artifacts dominate the stakeholder image.
- If long quiet leading/trailing audio is auto-focused, disclose that near the
  audio controls so the shorter playback duration is not surprising.
- Use cards only for individual metrics, summaries, or controls. Do not nest
  cards inside cards.
- Keep controls tactile: 40px minimum target height, clear hover/active states,
  and no layout shift when labels change.
- Use tabular numbers for time, percentages, pitch, pause counts, and WPM.
- Prefer plain language in visible labels. Avoid showing implementation terms
  unless the user asked for technical detail.

## Core Palette

Use these CSS custom properties as the default report theme:

```css
:root {
  --paper: #fef9ec;
  --surface: #fffdf5;
  --surface-strong: #fff8e8;
  --ink: #172c35;
  --ink-soft: #2b4650;
  --muted: #6f7771;
  --accent: #e53546;
  --accent-soft: #ffe1e4;
  --teal: #12313a;
  --teal-soft: #e5f0ef;
  --shadow-border:
    0 0 0 1px rgba(23, 44, 53, 0.07),
    0 12px 28px -18px rgba(23, 44, 53, 0.42),
    0 3px 10px -7px rgba(23, 44, 53, 0.28);
  --shadow-hover:
    0 0 0 1px rgba(23, 44, 53, 0.1),
    0 16px 34px -20px rgba(23, 44, 53, 0.48),
    0 5px 14px -8px rgba(23, 44, 53, 0.32);
}
```

Use `--accent` sparingly for important action states and key speech moments. Use
`--teal` for structure, control panels, table headers, and anchoring lines.

## CSS Baseline

```css
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body {
  margin: 0;
  color: var(--ink);
  background: linear-gradient(180deg, var(--paper) 0%, #fbf3df 58%, #f5ead2 100%);
  font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
}
main {
  max-width: 1080px;
  margin: 0 auto;
  padding: 30px 22px 56px;
}
h1 {
  margin: 0;
  color: var(--accent);
  font-family: "Avenir Next Condensed", "Arial Black", "Impact", sans-serif;
  font-size: clamp(44px, 8vw, 86px);
  line-height: 0.9;
  letter-spacing: 0.01em;
  text-transform: uppercase;
  text-wrap: balance;
}
h2 { color: var(--teal); text-wrap: balance; }
p, li, .caption, .summary { text-wrap: pretty; }
```

Do not use viewport-scaled body text. Keep normal copy readable and stable; save
large display type for the report title only.

## Layout Pattern

- First viewport: title, generation context, duration, privacy notice, audio
  player, and transport controls.
- Follow with summary cards, then charts, then listen-first moments and details.
- Charts should be full-width within the content column and never hidden inside a
  decorative preview frame.
- Tables must use `table-layout: fixed` plus `overflow-wrap: anywhere` so long
  labels cannot break mobile layouts.

## Controls

Required controls for interactive reports:

- Play/pause
- Scrubber
- Playback speed
- Previous/next listen-first moment
- Loop active on/off
- Loop duration input
- Set loop from playhead
- Pause and peak visibility toggles
- Click-to-seek on waveform, energy, and pitch charts
- Pattern Review Workbench controls when pattern candidates exist:
  review-candidate buttons, decision segmented control, analyst label, pattern
  ID, notes, copy JSON, and download JSON
- Visual-only controls:
  `Visual only` toggle, `Map`/`Card`/`Library` layout selector, `Download image`
  button, and local PNG export from the active embedded SVG visual snapshot

Buttons should use:

```css
button {
  min-height: 40px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  transition-property: transform, background-color, box-shadow, color;
  transition-duration: 150ms;
  transition-timing-function: cubic-bezier(0.2, 0, 0, 1);
}
button:active { transform: scale(0.96); }
```

Always include a reduced-motion override:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 1ms !important;
    animation-duration: 1ms !important;
  }
}
```

## Mobile Rules

- No horizontal overflow at 390px width.
- Keep controls wrap-friendly; use grid/flex with explicit gaps.
- Preserve 40px touch targets.
- Avoid long inline labels inside narrow controls. Move explanatory text below
  controls when needed.
- Validate the first viewport: the title, duration, audio player, and controls
  must not overlap.

## Quality Bar

Before sharing an HTML artifact, verify:

- Audio plays without skipping.
- All transport controls are wired.
- Chart click-to-seek works.
- Loop duration and set-loop-from-playhead work.
- Pause/peak toggles work.
- Pattern Review Workbench selects candidates, updates the decision state, and
  exports valid JSON without layout overflow.
- Visual only hides word-heavy sections while preserving charts/pattern visuals.
- Map/Card/Library layout switching updates the visible visual snapshot.
- Transcript word callouts render above pitch/contour arcs when transcript data
  is available, with readable card opacity and connectors back to the contour.
- Visual-only pitch contours are smoothed/downsampled enough to make phrase
  shape readable without changing raw analysis metrics.
- Download image exports a non-empty PNG locally from the active visual
  snapshot, not a hidden default layout.
- Active-audio focus trims long quiet edges on dead-air fixtures and discloses
  original/focused duration in the report.
- Desktop and mobile layouts have no incoherent overlap.
- Browser console has no errors.
