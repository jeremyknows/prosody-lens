#!/usr/bin/env python3
"""
Dependency-light prosody analyzer.

Outputs:
- prosody.json
- report.md
- report.html
- audio.wav

This is a practical fallback analyzer. Use Praat/Parselmouth for serious
phonetics work.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")


def convert_to_wav(audio_path: Path, wav_path: Path, sample_rate: int = 16000) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required but was not found on PATH")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-vn",
            str(wav_path),
        ]
    )


def read_wav(wav_path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if channels != 1:
        raise RuntimeError("expected mono WAV after conversion")
    if sample_width != 2:
        raise RuntimeError("expected 16-bit PCM WAV after conversion")

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return sample_rate, samples


def frame_audio(samples: np.ndarray, sample_rate: int, frame_ms: float, hop_ms: float) -> tuple[np.ndarray, np.ndarray]:
    frame_len = int(sample_rate * frame_ms / 1000.0)
    hop_len = int(sample_rate * hop_ms / 1000.0)
    if len(samples) < frame_len:
        padded = np.pad(samples, (0, max(0, frame_len - len(samples))))
        return np.array([0.0]), padded.reshape(1, frame_len)

    starts = np.arange(0, len(samples) - frame_len + 1, hop_len)
    frames = np.stack([samples[start : start + frame_len] for start in starts])
    times = starts / sample_rate
    return times, frames


def rms_db(frames: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    return 20.0 * np.log10(rms + 1e-12)


def estimate_pitch_hz(frame: np.ndarray, sample_rate: int, min_hz: float = 75.0, max_hz: float = 400.0) -> tuple[float | None, float]:
    frame = frame - np.mean(frame)
    energy = float(np.sqrt(np.mean(frame * frame) + 1e-12))
    if energy < 0.01:
        return None, 0.0

    windowed = frame * np.hanning(len(frame))
    corr = np.correlate(windowed, windowed, mode="full")[len(windowed) - 1 :]
    if corr[0] <= 1e-9:
        return None, 0.0
    corr = corr / corr[0]

    min_lag = max(1, int(sample_rate / max_hz))
    max_lag = min(len(corr) - 1, int(sample_rate / min_hz))
    if max_lag <= min_lag:
        return None, 0.0

    search = corr[min_lag:max_lag]
    peak_index = int(np.argmax(search)) + min_lag
    peak_value = float(corr[peak_index])
    if peak_value < 0.28:
        return None, peak_value
    return float(sample_rate / peak_index), peak_value


def contiguous_regions(mask: np.ndarray, times: np.ndarray, hop_s: float, min_duration_s: float) -> list[dict[str, float]]:
    regions: list[dict[str, float]] = []
    start: float | None = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = float(times[i])
        elif not value and start is not None:
            end = float(times[i] + hop_s)
            if end - start >= min_duration_s:
                regions.append({"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)})
            start = None
    if start is not None and len(times):
        end = float(times[-1] + hop_s)
        if end - start >= min_duration_s:
            regions.append({"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)})
    return regions


def safe_percentile(values: np.ndarray, pct: float) -> float | None:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return None
    return float(np.percentile(finite, pct))


def summarize(values: np.ndarray) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {"min": None, "p10": None, "median": None, "p90": None, "max": None, "mean": None, "std": None}
    return {
        "min": round(float(np.min(finite)), 3),
        "p10": round(float(np.percentile(finite, 10)), 3),
        "median": round(float(np.median(finite)), 3),
        "p90": round(float(np.percentile(finite, 90)), 3),
        "max": round(float(np.max(finite)), 3),
        "mean": round(float(np.mean(finite)), 3),
        "std": round(float(np.std(finite)), 3),
    }


def load_transcript(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8").strip()


def count_words(transcript: str | None) -> int | None:
    if not transcript:
        return None
    return len([w for w in transcript.replace("\n", " ").split(" ") if w.strip()])


def downsample_pairs(times: np.ndarray, values: np.ndarray, max_points: int = 700) -> list[tuple[float, float | None]]:
    if len(times) == 0:
        return []
    step = max(1, math.ceil(len(times) / max_points))
    pairs: list[tuple[float, float | None]] = []
    for i in range(0, len(times), step):
        value = values[i]
        pairs.append((round(float(times[i]), 3), None if not np.isfinite(value) else round(float(value), 3)))
    return pairs


def svg_polyline(series: list[tuple[float, float | None]], width: int, height: int, color: str, ymin: float | None = None, ymax: float | None = None) -> str:
    valid = [(t, v) for t, v in series if v is not None and math.isfinite(v)]
    if not valid:
        return f'<text x="12" y="{height // 2}" fill="#666">no data</text>'
    t_min = min(t for t, _ in valid)
    t_max = max(t for t, _ in valid)
    values = [float(v) for _, v in valid]
    v_min = min(values) if ymin is None else ymin
    v_max = max(values) if ymax is None else ymax
    if abs(t_max - t_min) < 1e-9:
        t_max = t_min + 1.0
    if abs(v_max - v_min) < 1e-9:
        v_max = v_min + 1.0
    points = []
    for t, v in valid:
        x = 8 + (width - 16) * ((t - t_min) / (t_max - t_min))
        y = height - 8 - (height - 16) * ((float(v) - v_min) / (v_max - v_min))
        points.append(f"{x:.1f},{y:.1f}")
    return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}" />'


def pause_rects(pauses: list[dict[str, float]], duration: float, width: int, height: int) -> str:
    if duration <= 0:
        return ""
    rects = []
    for pause in pauses:
        x = 8 + (width - 16) * (pause["start"] / duration)
        w = max(1.0, (width - 16) * (pause["duration"] / duration))
        rects.append(f'<rect class="pause-band" x="{x:.1f}" y="4" width="{w:.1f}" height="{height - 8}" fill="#f6d47a" opacity="0.4" />')
    return "\n".join(rects)


def peak_markers(peaks: list[dict], duration: float, width: int, height: int) -> str:
    if duration <= 0:
        return ""
    markers = []
    for peak in peaks[:20]:
        x = 8 + (width - 16) * (float(peak["start"]) / duration)
        label = html.escape(f"#{peak.get('rank', '?')} {fmt_time(float(peak['start']))}")
        markers.append(
            f'<g class="peak-marker" data-marker-time="{float(peak["start"]):.3f}" data-marker-label="{label}">'
            f'<line x1="{x:.1f}" y1="6" x2="{x:.1f}" y2="{height - 20}" stroke="#e53546" stroke-width="2" opacity="0.88" />'
            f'<circle cx="{x:.1f}" cy="14" r="4" fill="#e53546" />'
            "</g>"
        )
    return "\n".join(markers)


def playhead_line(width: int, height: int) -> str:
    return f'<line class="playhead" x1="8" y1="0" x2="8" y2="{height}" stroke="#172c35" stroke-width="2" opacity="0.9" />'


def metric_card(label: str, value: str) -> str:
    return f'<div class="card"><div class="label">{html.escape(label)}</div><div class="value">{html.escape(value)}</div></div>'


def fmt(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:.2f}{suffix}"


def fmt_time(seconds: float | int | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = max(0, float(seconds))
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:04.1f}" if minutes else f"{remainder:.1f}s"


def duration_bucket(duration: float) -> str:
    if duration < 60:
        return "short"
    if duration < 240:
        return "medium"
    return "long"


def make_session_id(audio_path: Path, generated_at: str) -> str:
    seed = f"{audio_path.name}:{generated_at}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:12]


def finite_ratio(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    return round(float(np.sum(np.isfinite(values)) / len(values)), 4)


def semitone_std(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return None
    median = float(np.median(finite))
    if median <= 0:
        return None
    st = 12.0 * np.log2(finite / median)
    return round(float(np.std(st)), 3)


def semitone_iqr(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return None
    median = float(np.median(finite))
    if median <= 0:
        return None
    st = 12.0 * np.log2(finite / median)
    return round(float(np.percentile(st, 75) - np.percentile(st, 25)), 3)


def overlap_seconds(region_start: float, region_end: float, window_start: float, window_end: float) -> float:
    return max(0.0, min(region_end, window_end) - max(region_start, window_start))


def merge_regions(regions: list[dict[str, float]], max_gap_s: float) -> list[dict[str, float]]:
    if not regions:
        return []
    merged = [dict(regions[0])]
    for region in regions[1:]:
        current = merged[-1]
        if float(region["start"]) - float(current["end"]) <= max_gap_s:
            current["end"] = float(region["end"])
            current["duration"] = round(float(current["end"]) - float(current["start"]), 3)
        else:
            merged.append(dict(region))
    return merged


def score_acoustic_peaks(
    regions: list[dict[str, float]],
    times: np.ndarray,
    energy_db: np.ndarray,
    pitch_arr: np.ndarray,
    energy_threshold: float | None,
    pitch_threshold: float | None,
) -> list[dict[str, float | str | int]]:
    peaks: list[dict[str, float | str | int]] = []
    energy_ceiling = safe_percentile(energy_db, 99) or safe_percentile(energy_db, 90) or 0.0
    pitch_ceiling = safe_percentile(pitch_arr, 95) or safe_percentile(pitch_arr, 90) or 0.0
    for region in regions:
        start = float(region["start"])
        end = float(region["end"])
        mask = (times >= start) & (times <= end)
        if not np.any(mask):
            continue

        energy_slice = energy_db[mask]
        pitch_slice = pitch_arr[mask]
        energy_max = safe_percentile(energy_slice, 95)
        pitch_max = safe_percentile(pitch_slice, 95)

        energy_score = 0.0
        if energy_threshold is not None and energy_ceiling > energy_threshold and energy_max is not None:
            energy_score = max(0.0, min(1.0, (energy_max - energy_threshold) / (energy_ceiling - energy_threshold)))

        pitch_score = 0.0
        if pitch_threshold is not None and pitch_ceiling > pitch_threshold and pitch_max is not None:
            pitch_score = max(0.0, min(1.0, (pitch_max - pitch_threshold) / (pitch_ceiling - pitch_threshold)))

        score = round(float(energy_score + pitch_score + min(0.35, float(region["duration"]) / 2.0)), 3)
        if score <= 0:
            continue
        peaks.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(float(region["duration"]), 3),
                "score": score,
                "energy_db_p95": None if energy_max is None else round(float(energy_max), 3),
                "pitch_hz_p95": None if pitch_max is None else round(float(pitch_max), 3),
                "reason": "possible acoustic peak; rough pitch and/or loudness signal",
            }
        )

    ranked = sorted(peaks, key=lambda item: float(item["score"]), reverse=True)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def segment_summary(
    label: str,
    start: float,
    end: float,
    times: np.ndarray,
    energy_db: np.ndarray,
    pitch_arr: np.ndarray,
    pauses: list[dict[str, float]],
    peaks: list[dict[str, float | str | int]],
) -> dict:
    duration = max(0.001, end - start)
    mask = (times >= start) & (times < end)
    pause_total = sum(overlap_seconds(float(p["start"]), float(p["end"]), start, end) for p in pauses)
    peak_count = sum(1 for p in peaks if overlap_seconds(float(p["start"]), float(p["end"]), start, end) > 0)
    pitch_slice = pitch_arr[mask]
    energy_slice = energy_db[mask]
    pitch_summary = summarize(pitch_slice)
    energy_summary = summarize(energy_slice)
    return {
        "label": label,
        "start": round(start, 3),
        "end": round(end, 3),
        "duration_seconds": round(duration, 3),
        "pause_ratio": round(pause_total / duration, 4),
        "pause_seconds": round(pause_total, 3),
        "median_pitch_hz": pitch_summary["median"],
        "pitch_variability_semitones": semitone_std(pitch_slice),
        "median_intensity_db": energy_summary["median"],
        "acoustic_peak_count": peak_count,
    }


def build_progression(
    duration: float,
    times: np.ndarray,
    energy_db: np.ndarray,
    pitch_arr: np.ndarray,
    pauses: list[dict[str, float]],
    peaks: list[dict[str, float | str | int]],
) -> dict:
    if duration <= 0:
        return {"segments": [], "arc_summary": "No duration available."}

    cuts = [0.0, duration / 3.0, (2.0 * duration) / 3.0, duration]
    labels = ["opening", "middle", "closing"]
    segments = [
        segment_summary(labels[i], cuts[i], cuts[i + 1], times, energy_db, pitch_arr, pauses, peaks)
        for i in range(3)
    ]

    opening = segments[0]
    closing = segments[-1]
    pause_delta = round(float(closing["pause_ratio"] or 0.0) - float(opening["pause_ratio"] or 0.0), 4)
    intensity_delta = None
    if opening["median_intensity_db"] is not None and closing["median_intensity_db"] is not None:
        intensity_delta = round(float(closing["median_intensity_db"]) - float(opening["median_intensity_db"]), 3)
    pitch_var_delta = None
    if opening["pitch_variability_semitones"] is not None and closing["pitch_variability_semitones"] is not None:
        pitch_var_delta = round(float(closing["pitch_variability_semitones"]) - float(opening["pitch_variability_semitones"]), 3)

    pause_phrase = "more pause-heavy" if pause_delta > 0.025 else "less pause-heavy" if pause_delta < -0.025 else "similar in pause density"
    intensity_phrase = "similar intensity"
    if intensity_delta is not None:
        if intensity_delta > 2:
            intensity_phrase = "louder by the close"
        elif intensity_delta < -2:
            intensity_phrase = "quieter by the close"
    arc_summary = f"Closing third is {pause_phrase}; {intensity_phrase} versus the opening third."
    return {
        "segments": segments,
        "arc_summary": arc_summary,
        "opening_to_closing_delta": {
            "pause_ratio": pause_delta,
            "median_intensity_db": intensity_delta,
            "pitch_variability_semitones": pitch_var_delta,
        },
    }


def build_trend_metrics(
    duration: float,
    metrics: dict,
    pauses: list[dict[str, float]],
    peaks: list[dict[str, float | str | int]],
    pitch_arr: np.ndarray,
) -> dict:
    minutes = max(duration / 60.0, 0.001)
    pause_durations = [float(p["duration"]) for p in pauses]
    intensity = metrics["intensity_db"]
    intensity_range = None
    if intensity.get("min") is not None and intensity.get("max") is not None:
        intensity_range = round(float(intensity["max"]) - float(intensity["min"]), 3)
    return {
        "duration_seconds": metrics["duration_seconds"],
        "pause_ratio": metrics["pause_ratio"],
        "pause_count_per_minute": round(len(pauses) / minutes, 3),
        "long_pause_count_per_minute": round(sum(1 for p in pause_durations if p >= 0.7) / minutes, 3),
        "median_pause_seconds": round(float(np.median(pause_durations)), 3) if pause_durations else 0.0,
        "pitch_variability_semitones": metrics["pitch_variability_semitones"],
        "pitch_iqr_semitones": semitone_iqr(pitch_arr),
        "median_pitch_hz": metrics["pitch_hz"]["median"],
        "pitch_boundary_hit": bool((metrics["pitch_hz"].get("max") or 0) >= 399.0),
        "pitch_coverage_ratio": finite_ratio(pitch_arr),
        "intensity_std_db": metrics["intensity_db"]["std"],
        "intensity_range_db": intensity_range,
        "acoustic_peaks_per_minute": round(len(peaks) / minutes, 3),
        "speaking_rate_wpm": metrics["speaking_rate_wpm"],
        "coverage_flags": {
            "transcript_available": metrics["word_count"] is not None,
            "word_alignment_available": False,
            "pitch_fallback": True,
        },
    }


def build_synthesis(metrics: dict, trend_metrics: dict, progression: dict, peaks: list[dict]) -> dict:
    pause_ratio = metrics.get("pause_ratio") or 0.0
    pitch_var = metrics.get("pitch_variability_semitones")
    transcript_available = metrics.get("word_count") is not None

    if pause_ratio < 0.08:
        pacing = "mostly continuous pacing with limited low-energy pause time"
    elif pause_ratio < 0.16:
        pacing = "moderate pacing with clear pause structure"
    else:
        pacing = "pause-heavy pacing that may feel segmented"

    if pitch_var is None:
        variety = "rough pitch variety unavailable"
    elif pitch_var < 3:
        variety = "narrow rough pitch movement"
    elif pitch_var < 7:
        variety = "moderate rough pitch movement"
    else:
        variety = "wide rough pitch movement"

    strongest = "pause structure" if pause_ratio >= 0.12 else "vocal variety" if (pitch_var or 0) >= 5 else "steady pacing"
    listen = []
    for peak in peaks[:5]:
        listen.append(
            {
                "start": peak["start"],
                "end": peak["end"],
                "label": "Possible acoustic peak",
                "why": f"rank {peak.get('rank')} by rough loudness/pitch score",
            }
        )

    unavailable = []
    if not transcript_available:
        unavailable.extend(["speaking rate", "word-level emphasis", "phrase-level transcript alignment"])
    if trend_metrics.get("pitch_boundary_hit"):
        unavailable.append("precise pitch range; fallback tracker hit its upper boundary")

    return {
        "overall_pattern": f"{fmt(metrics['duration_seconds'], 's')} recording with {pacing}.",
        "strongest_delivery_signal": strongest,
        "pacing_and_pauses": f"{metrics['pause_count']} low-energy regions totaling {fmt(metrics['pause_total_seconds'], 's')} ({fmt(pause_ratio * 100, '%')} of the recording).",
        "vocal_variety": f"{variety}; treat pitch numbers as rough fallback estimates.",
        "progression_note": progression.get("arc_summary", "Progression unavailable."),
        "listen_first": listen,
        "recommended_experiment": "Record one comparable retake with the same goal, then compare pause ratio, rough pitch variety, and top acoustic peaks.",
        "unavailable_without_alignment": unavailable,
        "method_note": "Local fallback analyzer only; descriptive, not clinical or diagnostic.",
    }


def make_playback_audio(wav_path: Path, mp3_path: Path) -> Path:
    """Create a browser-friendly playback copy while preserving WAV for analysis."""
    try:
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "96k",
                str(mp3_path),
            ]
        )
        return mp3_path
    except RuntimeError:
        return wav_path


def audio_data_uri(audio_path: Path) -> tuple[str, str]:
    encoded = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    mime_type = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav"
    return f"data:{mime_type};base64,{encoded}", mime_type


def append_history(history_path: Path, data: dict) -> None:
    compact = {
        "schema_version": data["schema_version"],
        "generated_at": data["generated_at"],
        "session": data["session"],
        "comparability": data["comparability"],
        "trend_metrics": data["trend_metrics"],
        "synthesis": {
            "overall_pattern": data["synthesis"]["overall_pattern"],
            "strongest_delivery_signal": data["synthesis"]["strongest_delivery_signal"],
            "progression_note": data["synthesis"]["progression_note"],
        },
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(compact, sort_keys=True) + "\n")


def time_ticks(duration: float, width: int, height: int) -> str:
    if duration <= 0:
        return ""
    step = 15 if duration <= 180 else 30
    ticks = []
    t = 0.0
    while t <= duration + 0.001:
        x = 8 + (width - 16) * (t / duration)
        ticks.append(f'<line x1="{x:.1f}" y1="{height - 18}" x2="{x:.1f}" y2="{height - 8}" stroke="#b8afa1" stroke-width="1" />')
        ticks.append(f'<text x="{x:.1f}" y="{height - 2}" fill="#6b7280" font-size="10" text-anchor="middle">{html.escape(fmt_time(t))}</text>')
        t += step
    return "\n".join(ticks)


def write_report(out_dir: Path, data: dict, audio_name: str) -> None:
    metrics = data["metrics"]
    synthesis = data["synthesis"]
    peaks = data.get("acoustic_peak_candidates", data.get("emphasis_candidates", []))
    share = data["share"]
    lines = [
        "# Prosody Lens Report",
        "",
        f"Audio: `{audio_name}`",
        f"Generated: {data['generated_at']}",
        "",
        "## Delivery Summary",
        "",
        f"- Overall pattern: {synthesis['overall_pattern']}",
        f"- Strongest delivery signal: {synthesis['strongest_delivery_signal']}",
        f"- Pacing and pauses: {synthesis['pacing_and_pauses']}",
        f"- Vocal variety: {synthesis['vocal_variety']}",
        f"- Progression note: {synthesis['progression_note']}",
        f"- Recommended experiment: {synthesis['recommended_experiment']}",
        "",
        "## Listen First",
        "",
    ]
    if synthesis["listen_first"]:
        for item in synthesis["listen_first"]:
            lines.append(f"- {fmt_time(item['start'])} to {fmt_time(item['end'])}: {item['label']} ({item['why']})")
    else:
        lines.append("- No strong acoustic peaks detected by the fallback analyzer.")

    lines.extend(
        [
            "",
            "## Progression Snapshot",
            "",
            f"- Arc: {data['progression']['arc_summary']}",
        ]
    )
    for segment in data["progression"]["segments"]:
        lines.append(
            f"- {segment['label']}: pause ratio {fmt(segment['pause_ratio'] * 100, '%')}, "
            f"median intensity {fmt(segment['median_intensity_db'], ' dB')}, "
            f"acoustic peaks {segment['acoustic_peak_count']}"
        )

    lines.extend(
        [
            "",
            "## Availability",
            "",
        ]
    )
    if synthesis["unavailable_without_alignment"]:
        lines.append("- Unavailable without transcript/alignment: " + ", ".join(synthesis["unavailable_without_alignment"]) + ".")
    else:
        lines.append("- Transcript-dependent fields are available for this run.")
    if share["html_embeds_audio"]:
        lines.append("- Privacy: `report.html` embeds playable raw voice audio. Do not share it externally unless raw audio sharing is approved.")
    else:
        lines.append("- Privacy: share-safe mode omitted the audio player and raw audio copy.")

    lines.extend(
        [
            "",
        "## Summary Metrics",
        "",
        f"- Duration: {fmt(metrics['duration_seconds'], 's')}",
        f"- Pause count: {metrics['pause_count']}",
        f"- Total pause time: {fmt(metrics['pause_total_seconds'], 's')}",
        f"- Longest pause: {fmt(metrics['longest_pause_seconds'], 's')}",
        f"- Pause ratio: {fmt(metrics['pause_ratio'] * 100 if metrics['pause_ratio'] is not None else None, '%')}",
        f"- Rough median pitch: {fmt(metrics['pitch_hz']['median'], ' Hz')}",
        f"- Rough pitch P10-P90: {fmt(metrics['pitch_hz']['p10'], ' Hz')} to {fmt(metrics['pitch_hz']['p90'], ' Hz')}",
        f"- Pitch variability: {fmt(metrics['pitch_variability_semitones'], ' st')}",
        f"- Median intensity: {fmt(metrics['intensity_db']['median'], ' dB')}",
        f"- Intensity range: {fmt(metrics['intensity_db']['min'], ' dB')} to {fmt(metrics['intensity_db']['max'], ' dB')}",
        ]
    )
    if metrics.get("word_count") is not None:
        lines.append(f"- Word count: {metrics['word_count']}")
        lines.append(f"- Speaking rate: {fmt(metrics['speaking_rate_wpm'], ' WPM')}")

    lines.extend(
        [
            "",
            "## Possible Acoustic Peaks",
            "",
        ]
    )
    if peaks:
        for item in peaks[:12]:
            lines.append(f"- #{item['rank']} {fmt_time(item['start'])} to {fmt_time(item['end'])}: {item['reason']} (score {item['score']})")
    else:
        lines.append("- No strong acoustic peaks detected by the fallback analyzer.")

    lines.extend(
        [
            "",
            "## Pause Map",
            "",
        ]
    )
    if data["pauses"]:
        for pause in data["pauses"][:20]:
            lines.append(f"- {pause['start']:.2f}s to {pause['end']:.2f}s ({pause['duration']:.2f}s)")
    else:
        lines.append("- No pauses over threshold detected.")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Fallback pitch tracking uses autocorrelation, not Praat.",
            "- Acoustic peaks are time ranges, not confirmed emphasized words.",
            "- Without word-level alignment, speaking rate and word-level emphasis are unavailable.",
            "- Noise, room echo, multiple speakers, and music can distort metrics.",
            "- This report is descriptive, not clinical or diagnostic.",
            "",
            "Open `report.html` for the visual timeline and audio player.",
        ]
    )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(out_dir: Path, data: dict, playback_path: Path, include_audio: bool) -> None:
    duration = data["metrics"]["duration_seconds"]
    try:
        generated_dt = dt.datetime.fromisoformat(str(data["generated_at"]).replace("Z", "+00:00"))
        generated_label = generated_dt.strftime("%b %d, %Y %I:%M %p UTC").replace(" 0", " ")
    except ValueError:
        generated_label = str(data["generated_at"])
    width = 980
    track_h = 150
    waveform = data["series"]["waveform"]
    energy = data["series"]["energy_db"]
    pitch = data["series"]["pitch_hz"]
    pauses = data["pauses"]
    metrics = data["metrics"]
    synthesis = data["synthesis"]
    peaks = data.get("acoustic_peak_candidates", data.get("emphasis_candidates", []))

    cards = "\n".join(
        [
            metric_card("Duration", fmt(metrics["duration_seconds"], "s")),
            metric_card("Pauses", str(metrics["pause_count"])),
            metric_card("Pause Time", fmt(metrics["pause_total_seconds"], "s")),
            metric_card("Rough Pitch Median", fmt(metrics["pitch_hz"]["median"], " Hz")),
            metric_card("Rough Pitch Variety", fmt(metrics["pitch_variability_semitones"], " st")),
            metric_card("Intensity Median", fmt(metrics["intensity_db"]["median"], " dB")),
        ]
    )
    peak_rows = "\n".join(
        (
            f"<tr><td>#{item['rank']}</td>"
            f"<td><button class=\"seek\" data-seek=\"{float(item['start']):.3f}\" data-end=\"{float(item['end']):.3f}\">{html.escape(fmt_time(item['start']))}</button></td>"
            f"<td>{html.escape(fmt_time(item['end']))}</td>"
            f"<td>{html.escape(str(item['reason']))}</td>"
            f"<td>{html.escape(str(item['score']))}</td></tr>"
        )
        for item in peaks[:12]
    ) or '<tr><td colspan="5">No strong acoustic peaks detected.</td></tr>'

    listen_items = "\n".join(
        f"<li><button class=\"seek\" data-seek=\"{float(item['start']):.3f}\" data-end=\"{float(item['end']):.3f}\">{html.escape(fmt_time(item['start']))}</button> {html.escape(item['label'])}: {html.escape(item['why'])}</li>"
        for item in synthesis["listen_first"]
    ) or "<li>No strong acoustic peaks detected by the fallback analyzer.</li>"

    summary_items = "\n".join(
        [
            f"<li><strong>Overall:</strong> {html.escape(synthesis['overall_pattern'])}</li>",
            f"<li><strong>Signal:</strong> {html.escape(str(synthesis['strongest_delivery_signal']))}</li>",
            f"<li><strong>Pacing:</strong> {html.escape(synthesis['pacing_and_pauses'])}</li>",
            f"<li><strong>Variety:</strong> {html.escape(synthesis['vocal_variety'])}</li>",
            f"<li><strong>Progression:</strong> {html.escape(synthesis['progression_note'])}</li>",
            f"<li><strong>Experiment:</strong> {html.escape(synthesis['recommended_experiment'])}</li>",
        ]
    )

    progression_rows = "\n".join(
        (
            f"<tr><td>{html.escape(segment['label'])}</td>"
            f"<td>{html.escape(fmt(segment['pause_ratio'] * 100, '%'))}</td>"
            f"<td>{html.escape(fmt(segment['median_intensity_db'], ' dB'))}</td>"
            f"<td>{html.escape(fmt(segment['pitch_variability_semitones'], ' st'))}</td>"
            f"<td>{segment['acoustic_peak_count']}</td></tr>"
        )
        for segment in data["progression"]["segments"]
    )

    if include_audio:
        audio_src, audio_type = audio_data_uri(playback_path)
        audio_block = (
            f'<audio id="audio" controls preload="auto" style="width:100%; margin: 12px 0 12px;">'
            f'<source src="{audio_src}" type="{audio_type}" />'
            '</audio>'
            '<div class="notice warn">Privacy: this HTML embeds a playable copy of the raw voice audio. Do not share externally unless raw audio sharing is approved.</div>'
        )
        controls_block = f"""
<section class="control-panel" aria-label="Audio inspection controls">
  <div class="transport">
    <button type="button" id="prevMoment">Prev moment</button>
    <button type="button" id="playPause">Play</button>
    <button type="button" id="nextMoment">Next moment</button>
    <input id="scrubber" type="range" min="0" max="{duration:.3f}" value="0" step="0.01" aria-label="Audio scrubber" />
    <span id="timeReadout">0.0s / {html.escape(fmt_time(duration))}</span>
  </div>
  <div class="control-row">
    <span class="control-label">Speed</span>
    <button type="button" class="speed" data-speed="0.75">0.75x</button>
    <button type="button" class="speed active" data-speed="1">1x</button>
    <button type="button" class="speed" data-speed="1.25">1.25x</button>
    <button type="button" class="speed" data-speed="1.5">1.5x</button>
    <span class="control-label">Loop</span>
    <input id="loopLength" type="number" min="0.1" max="30" value="1.0" step="0.1" aria-label="Loop length in seconds" />
    <span class="control-label">sec</span>
    <button type="button" id="setLoopHere">Set loop here</button>
    <button type="button" id="loopActive">Loop active: off</button>
  </div>
  <div class="control-row">
    <label><input id="togglePauses" type="checkbox" checked /> Pauses</label>
    <label><input id="togglePeaks" type="checkbox" checked /> Peaks</label>
    <span id="activeMoment">No active moment</span>
  </div>
</section>
"""
    else:
        audio_block = '<div class="notice">Share-safe report: audio player and raw voice audio omitted.</div>'
        controls_block = ""

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="icon" href="data:," />
<title>Prosody Lens Report</title>
<style>
:root {{
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
  --shadow-border: 0 0 0 1px rgba(23, 44, 53, 0.07), 0 12px 28px -18px rgba(23, 44, 53, 0.42), 0 3px 10px -7px rgba(23, 44, 53, 0.28);
  --shadow-hover: 0 0 0 1px rgba(23, 44, 53, 0.1), 0 16px 34px -20px rgba(23, 44, 53, 0.48), 0 5px 14px -8px rgba(23, 44, 53, 0.32);
}}
*, *::before, *::after {{ box-sizing: border-box; }}
html {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
body {{ font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif; margin: 0; color: var(--ink); background: linear-gradient(180deg, var(--paper) 0%, #fbf3df 58%, #f5ead2 100%); }}
main {{ max-width: 1080px; margin: 0 auto; padding: 30px 22px 56px; }}
h1 {{ margin: 0; font-family: "Avenir Next Condensed", "Arial Black", "Impact", sans-serif; font-size: clamp(44px, 8vw, 86px); line-height: 0.9; letter-spacing: 0.01em; color: var(--accent); text-transform: uppercase; text-wrap: balance; }}
h2 {{ margin-top: 34px; color: var(--teal); letter-spacing: 0.01em; text-wrap: balance; }}
p, li, .caption, .summary {{ text-wrap: pretty; }}
.report-hero {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: end; padding: 24px 0 18px; border-bottom: 4px solid var(--teal); margin-bottom: 18px; }}
.eyebrow {{ margin: 0 0 8px; color: var(--teal); font-size: 12px; font-weight: 800; letter-spacing: 0.18em; text-transform: uppercase; }}
.sub {{ color: var(--muted); margin: 10px 0 0; max-width: 680px; }}
.hero-stat {{ min-width: 136px; border-radius: 22px; padding: 12px 14px; background: var(--teal); color: var(--paper); box-shadow: var(--shadow-border); text-align: right; }}
.hero-stat .label {{ color: rgba(254, 249, 236, 0.72); }}
.hero-stat .value {{ color: var(--paper); font-size: 28px; }}
audio {{ filter: drop-shadow(0 8px 22px rgba(23, 44, 53, 0.12)); }}
.summary {{ background: var(--surface); box-shadow: var(--shadow-border); border-radius: 18px; padding: 18px 20px; margin: 18px 0; }}
.summary ul {{ margin: 0; padding-left: 20px; }}
.summary li {{ margin: 8px 0; }}
.notice {{ background: var(--surface-strong); box-shadow: var(--shadow-border); border-radius: 16px; padding: 11px 13px; margin: 10px 0 18px; color: var(--ink-soft); }}
.notice.warn {{ background: #fff1d2; }}
.control-panel {{ background: var(--teal); color: #f8fafc; border-radius: 24px; padding: 14px; margin: 14px 0 22px; box-shadow: 0 0 0 1px rgba(255,255,255,0.08), 0 18px 42px -24px rgba(18,49,58,0.65); }}
.transport {{ display: grid; grid-template-columns: auto auto auto minmax(180px, 1fr) auto; gap: 10px; align-items: center; }}
.control-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 10px; }}
.control-panel button {{ appearance: none; min-height: 40px; border: 0; border-radius: 10px; background: rgba(254, 249, 236, 0.12); color: #f8fafc; padding: 8px 12px; cursor: pointer; font: inherit; box-shadow: inset 0 0 0 1px rgba(254,249,236,0.17); transition-property: transform, background-color, box-shadow, color; transition-duration: 150ms; transition-timing-function: cubic-bezier(0.2, 0, 0, 1); }}
.control-panel button:hover, .control-panel button.active {{ background: var(--accent); color: white; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22), 0 8px 18px -12px rgba(229,53,70,0.9); }}
.control-panel button:active, .seek:active {{ transform: scale(0.96); }}
.control-panel input[type="range"] {{ width: 100%; min-height: 40px; accent-color: var(--accent); }}
.control-panel input[type="number"] {{ width: 78px; min-height: 40px; border: 0; border-radius: 10px; background: rgba(254, 249, 236, 0.1); color: #f8fafc; padding: 8px; font: inherit; box-shadow: inset 0 0 0 1px rgba(254,249,236,0.17); }}
.control-panel label {{ display: inline-flex; align-items: center; gap: 6px; }}
.control-label, #timeReadout, #activeMoment {{ color: rgba(254, 249, 236, 0.76); font-size: 13px; font-variant-numeric: tabular-nums; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }}
.card {{ background: var(--surface); box-shadow: var(--shadow-border); border-radius: 16px; padding: 15px; transition-property: box-shadow, transform; transition-duration: 160ms; transition-timing-function: cubic-bezier(0.2, 0, 0, 1); }}
.card:hover, .summary:hover, .track:hover {{ box-shadow: var(--shadow-hover); }}
.label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 800; }}
.value {{ font-size: 22px; margin-top: 4px; font-weight: 750; font-variant-numeric: tabular-nums; color: var(--teal); }}
.track {{ background: var(--surface); box-shadow: var(--shadow-border); border-radius: 18px; margin: 12px 0 20px; padding: 12px; overflow-x: auto; }}
svg {{ width: 100%; min-width: 0; height: auto; display: block; }}
svg[data-track] {{ cursor: crosshair; }}
.axis {{ stroke: rgba(23,44,53,0.18); stroke-width: 1; }}
.playhead {{ pointer-events: none; }}
.peak-marker {{ cursor: pointer; }}
.hide-pauses .pause-band, .hide-peaks .peak-marker {{ display: none; }}
.caption {{ color: var(--muted); font-size: 13px; margin-top: 6px; }}
table {{ width: 100%; table-layout: fixed; border-collapse: collapse; background: var(--surface); box-shadow: var(--shadow-border); border-radius: 18px; overflow: hidden; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; vertical-align: top; padding: 11px; border-bottom: 1px solid rgba(23,44,53,0.09); overflow-wrap: anywhere; }}
th {{ background: var(--teal-soft); color: var(--teal); }}
code {{ background: var(--teal-soft); padding: 2px 5px; border-radius: 5px; }}
.seek {{ appearance: none; min-height: 40px; border: 0; border-radius: 10px; background: var(--accent-soft); color: var(--teal); padding: 6px 10px; cursor: pointer; font: inherit; font-variant-numeric: tabular-nums; box-shadow: inset 0 0 0 1px rgba(229,53,70,0.22); transition-property: transform, background-color, box-shadow, color; transition-duration: 150ms; transition-timing-function: cubic-bezier(0.2, 0, 0, 1); }}
.seek:hover, .seek.active {{ background: var(--accent); color: white; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.18), 0 8px 18px -12px rgba(229,53,70,0.9); }}
.chart-tip {{ position: fixed; z-index: 20; background: #111827; color: white; padding: 6px 8px; border-radius: 6px; font-size: 12px; pointer-events: none; box-shadow: 0 4px 14px rgba(0,0,0,0.22); }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ transition-duration: 1ms !important; animation-duration: 1ms !important; }}
}}
@media (max-width: 720px) {{
  main {{ padding: 28px 22px 48px; }}
  .report-hero {{ grid-template-columns: 1fr; gap: 14px; align-items: start; }}
  .hero-stat {{ width: max-content; min-width: 128px; text-align: left; }}
  .transport {{ grid-template-columns: 1fr 1fr 1fr; }}
  .transport input, #timeReadout {{ grid-column: 1 / -1; }}
}}
</style>
</head>
<body>
<main data-duration="{duration:.3f}">
<header class="report-hero">
  <div>
    <p class="eyebrow">Voice Delivery Map</p>
    <h1>Prosody Lens</h1>
    <div class="sub">Generated {html.escape(generated_label)}. Fallback analyzer, descriptive only.</div>
  </div>
  <div class="hero-stat">
    <div class="label">Duration</div>
    <div class="value">{html.escape(fmt(duration, 's'))}</div>
  </div>
</header>
{audio_block}
{controls_block}

<h2>Delivery Summary</h2>
<div class="summary"><ul>{summary_items}</ul></div>

<h2>Listen First</h2>
<div class="summary"><ul>{listen_items}</ul></div>

<div class="cards">{cards}</div>

<h2>Waveform</h2>
<div class="track">
<svg data-track="waveform" viewBox="0 0 {width} {track_h}" role="img" aria-label="Waveform">
{pause_rects(pauses, duration, width, track_h)}
<line class="axis" x1="8" y1="{track_h/2}" x2="{width-8}" y2="{track_h/2}" />
{svg_polyline(waveform, width, track_h, "#172c35", -1.0, 1.0)}
{peak_markers(peaks, duration, width, track_h)}
{time_ticks(duration, width, track_h)}
{playhead_line(width, track_h)}
</svg>
<div class="caption">Yellow bands mark detected pauses. Click the chart to jump the audio.</div>
</div>

<h2>Energy / Loudness</h2>
<div class="track">
<svg data-track="energy" viewBox="0 0 {width} {track_h}" role="img" aria-label="Energy">
{pause_rects(pauses, duration, width, track_h)}
{svg_polyline(energy, width, track_h, "#e53546")}
{peak_markers(peaks, duration, width, track_h)}
{time_ticks(duration, width, track_h)}
{playhead_line(width, track_h)}
</svg>
</div>

<h2>Pitch Contour</h2>
<div class="track">
<svg data-track="pitch" viewBox="0 0 {width} {track_h}" role="img" aria-label="Pitch">
{pause_rects(pauses, duration, width, track_h)}
{svg_polyline(pitch, width, track_h, "#0f6772")}
{peak_markers(peaks, duration, width, track_h)}
{time_ticks(duration, width, track_h)}
{playhead_line(width, track_h)}
</svg>
<div class="caption">Gaps indicate unvoiced or low-confidence pitch frames.</div>
</div>

<h2>Progression Snapshot</h2>
<table>
<thead><tr><th>Segment</th><th>Pause Ratio</th><th>Median Intensity</th><th>Pitch Variety</th><th>Peaks</th></tr></thead>
<tbody>{progression_rows}</tbody>
</table>

<h2>Possible Acoustic Peaks</h2>
<table>
<thead><tr><th>Rank</th><th>Start</th><th>End</th><th>Reason</th><th>Score</th></tr></thead>
<tbody>{peak_rows}</tbody>
</table>

<h2>Limitations</h2>
<p>This report uses a dependency-light fallback analyzer. Use Praat/Parselmouth
and word-level alignment for higher-fidelity phonetic analysis. Acoustic peaks are
not confirmed emphasized words. Do not treat this as clinical or diagnostic output.</p>
</main>
<div id="chartTip" class="chart-tip" hidden></div>
<script>
const audio = document.getElementById("audio");
const duration = Number(document.querySelector("main").dataset.duration) || 0;
const scrubber = document.getElementById("scrubber");
const timeReadout = document.getElementById("timeReadout");
const playPause = document.getElementById("playPause");
const activeMoment = document.getElementById("activeMoment");
const loopButton = document.getElementById("loopActive");
const loopLengthInput = document.getElementById("loopLength");
const setLoopHere = document.getElementById("setLoopHere");
const chartTip = document.getElementById("chartTip");
const markerButtons = Array.from(document.querySelectorAll("[data-seek]"));
const markers = Array.from(new Map(markerButtons.map((button) => {{
  const start = Number(button.dataset.seek) || 0;
  const end = Number(button.dataset.end) || Math.min(duration, start + 1);
  return [start.toFixed(3), {{ start, end }}];
}})).values()).sort((a, b) => a.start - b.start);
let activeRange = null;
let activeMarkerIndex = -1;
let loopEnabled = false;

function formatTime(seconds) {{
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const rest = value - minutes * 60;
  return minutes ? `${{minutes}}:${{rest.toFixed(1).padStart(4, "0")}}` : `${{rest.toFixed(1)}}s`;
}}

function xForTime(seconds) {{
  if (!duration) return 8;
  return 8 + (980 - 16) * Math.max(0, Math.min(1, seconds / duration));
}}

function updatePlayhead() {{
  if (!audio) return;
  const x = xForTime(audio.currentTime);
  document.querySelectorAll(".playhead").forEach((line) => {{
    line.setAttribute("x1", x.toFixed(1));
    line.setAttribute("x2", x.toFixed(1));
  }});
  if (scrubber) scrubber.value = String(audio.currentTime);
  if (timeReadout) timeReadout.textContent = `${{formatTime(audio.currentTime)}} / ${{formatTime(duration)}}`;
  if (loopEnabled && activeRange && audio.currentTime >= activeRange.end) {{
    audio.currentTime = activeRange.start;
    audio.play();
  }}
}}

function disableLoop() {{
  loopEnabled = false;
  if (loopButton) {{
    loopButton.textContent = "Loop active: off";
    loopButton.classList.remove("active");
  }}
}}

function getLoopLength(fallback = 1) {{
  const value = Number(loopLengthInput?.value);
  return Math.max(0.1, Math.min(30, Number.isFinite(value) && value > 0 ? value : fallback));
}}

function syncLoopLength(seconds) {{
  if (!loopLengthInput || !Number.isFinite(seconds)) return;
  loopLengthInput.value = Math.max(0.1, Math.min(30, seconds)).toFixed(1);
}}

function setActiveMomentText() {{
  if (!activeMoment) return;
  if (!activeRange) activeMoment.textContent = "No active moment";
  else activeMoment.textContent = `Active: ${{formatTime(activeRange.start)}} to ${{formatTime(activeRange.end)}}`;
}}

function clearActiveSelection() {{
  markerButtons.forEach((item) => item.classList.remove("active"));
  activeRange = null;
  activeMarkerIndex = -1;
  setActiveMomentText();
}}

function setActiveRange(button) {{
  const start = Number(button.dataset.seek) || 0;
  const end = Number(button.dataset.end) || Math.min(duration, start + 1);
  markerButtons.forEach((item) => {{
    const itemStart = Number(item.dataset.seek) || 0;
    item.classList.toggle("active", Math.abs(itemStart - start) < 0.001);
  }});
  activeRange = {{ start, end }};
  activeMarkerIndex = markers.findIndex((marker) => Math.abs(marker.start - start) < 0.001);
  syncLoopLength(end - start);
  setActiveMomentText();
}}

function setCustomLoopAt(startSeconds) {{
  if (!audio) return;
  const start = Math.max(0, Math.min(duration, Number(startSeconds) || 0));
  const end = Math.max(start + 0.1, Math.min(duration, start + getLoopLength()));
  markerButtons.forEach((item) => item.classList.remove("active"));
  activeRange = {{ start, end }};
  activeMarkerIndex = -1;
  syncLoopLength(end - start);
  setActiveMomentText();
  seekTo(start, false);
}}

function markerButtonForIndex(index) {{
  const marker = markers[index];
  if (!marker) return null;
  return markerButtons.find((button) => Math.abs((Number(button.dataset.seek) || 0) - marker.start) < 0.001) || null;
}}

function selectMarkerByIndex(index, shouldPlay = true) {{
  if (!markers.length) return;
  const wrapped = ((index % markers.length) + markers.length) % markers.length;
  const button = markerButtonForIndex(wrapped);
  const marker = markers[wrapped];
  if (button) setActiveRange(button);
  else {{
    activeRange = {{ start: marker.start, end: marker.end }};
    activeMarkerIndex = wrapped;
    syncLoopLength(marker.end - marker.start);
    setActiveMomentText();
  }}
  seekTo(marker.start, shouldPlay);
}}

function seekTo(seconds, shouldPlay = true, clearLoop = false, clearSelection = false) {{
  if (!audio) return;
  if (clearLoop) disableLoop();
  if (clearSelection) clearActiveSelection();
  audio.currentTime = Math.max(0, Math.min(duration, Number(seconds) || 0));
  updatePlayhead();
  if (shouldPlay) audio.play();
}}

markerButtons.forEach((button) => {{
  button.addEventListener("click", () => {{
    setActiveRange(button);
    seekTo(button.dataset.seek);
  }});
}});

document.querySelectorAll("svg[data-track]").forEach((svg) => {{
  svg.addEventListener("click", (event) => {{
    const rect = svg.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    seekTo(ratio * duration, true, true, true);
  }});
  svg.addEventListener("mousemove", (event) => {{
    const rect = svg.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    chartTip.hidden = false;
    chartTip.textContent = `${{svg.dataset.track}} - ${{formatTime(ratio * duration)}}`;
    chartTip.style.left = `${{event.clientX + 12}}px`;
    chartTip.style.top = `${{event.clientY + 12}}px`;
  }});
  svg.addEventListener("mouseleave", () => {{
    chartTip.hidden = true;
  }});
}});

if (audio) {{
  audio.addEventListener("timeupdate", updatePlayhead);
  audio.addEventListener("loadedmetadata", updatePlayhead);
  audio.addEventListener("play", () => {{ if (playPause) playPause.textContent = "Pause"; }});
  audio.addEventListener("pause", () => {{ if (playPause) playPause.textContent = "Play"; }});
}}

if (playPause) {{
  playPause.addEventListener("click", () => {{
    if (!audio) return;
    if (audio.paused) audio.play();
    else audio.pause();
  }});
}}

if (scrubber) {{
  scrubber.addEventListener("input", () => seekTo(scrubber.value, false, true, true));
  scrubber.addEventListener("change", () => seekTo(scrubber.value, false, true, true));
}}

if (loopLengthInput) {{
  loopLengthInput.addEventListener("change", () => {{
    const length = getLoopLength(activeRange ? activeRange.end - activeRange.start : 1);
    syncLoopLength(length);
    if (activeRange) {{
      activeRange.end = Math.max(activeRange.start + 0.1, Math.min(duration, activeRange.start + length));
      setActiveMomentText();
    }}
  }});
}}

if (setLoopHere) {{
  setLoopHere.addEventListener("click", () => {{
    disableLoop();
    setCustomLoopAt(audio ? audio.currentTime : 0);
  }});
}}

document.querySelectorAll("[data-speed]").forEach((button) => {{
  button.addEventListener("click", () => {{
    if (!audio) return;
    audio.playbackRate = Number(button.dataset.speed) || 1;
    document.querySelectorAll("[data-speed]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  }});
}});

const prevMoment = document.getElementById("prevMoment");
const nextMoment = document.getElementById("nextMoment");
function jumpMoment(direction) {{
  if (!markers.length || !audio) return;
  if (activeMarkerIndex >= 0) {{
    selectMarkerByIndex(activeMarkerIndex + direction);
    return;
  }}
  const current = audio.currentTime;
  let targetIndex = -1;
  if (direction > 0) {{
    targetIndex = markers.findIndex((marker) => marker.start > current + 0.05);
  }} else {{
    for (let index = markers.length - 1; index >= 0; index -= 1) {{
      if (markers[index].start < current - 0.05) {{
        targetIndex = index;
        break;
      }}
    }}
  }}
  selectMarkerByIndex(targetIndex >= 0 ? targetIndex : (direction > 0 ? 0 : markers.length - 1));
}}
if (prevMoment) prevMoment.addEventListener("click", () => jumpMoment(-1));
if (nextMoment) nextMoment.addEventListener("click", () => jumpMoment(1));

if (loopButton) {{
  loopButton.addEventListener("click", () => {{
    if (!activeRange && audio) {{
      setCustomLoopAt(audio.currentTime);
    }}
    if (!activeRange) return;
    loopEnabled = !loopEnabled;
    loopButton.textContent = `Loop active: ${{loopEnabled ? "on" : "off"}}`;
    loopButton.classList.toggle("active", loopEnabled);
  }});
}}

const togglePauses = document.getElementById("togglePauses");
const togglePeaks = document.getElementById("togglePeaks");
if (togglePauses) {{
  togglePauses.addEventListener("change", () => document.body.classList.toggle("hide-pauses", !togglePauses.checked));
}}
if (togglePeaks) {{
  togglePeaks.addEventListener("change", () => document.body.classList.toggle("hide-peaks", !togglePeaks.checked));
}}

updatePlayhead();
</script>
</body>
</html>
"""
    (out_dir / "report.html").write_text(doc, encoding="utf-8")


def analyze(args: argparse.Namespace) -> dict:
    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    out_dir = Path(args.out_dir or f"./tmp/prosody-lens-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / "audio.wav"
    playback_path = out_dir / "audio.mp3"
    generated_at = dt.datetime.now(dt.UTC).isoformat()
    convert_to_wav(audio_path, wav_path)
    if not args.share_safe:
        playback_path = make_playback_audio(wav_path, playback_path)
    sample_rate, samples = read_wav(wav_path)

    duration = float(len(samples) / sample_rate) if sample_rate else 0.0
    times, frames = frame_audio(samples, sample_rate, frame_ms=30.0, hop_ms=10.0)
    hop_s = 0.010
    energy_db = rms_db(frames)
    energy_floor = safe_percentile(energy_db, 15)
    energy_med = safe_percentile(energy_db, 50)
    if energy_floor is None or energy_med is None:
        silence_threshold = -45.0
    else:
        silence_threshold = min(energy_med - 18.0, energy_floor + 3.0)
    silence_mask = energy_db < silence_threshold
    pauses = contiguous_regions(silence_mask, times, hop_s, min_duration_s=args.min_pause)

    pitches: list[float] = []
    pitch_quality: list[float] = []
    for frame in frames:
        pitch, quality = estimate_pitch_hz(frame, sample_rate)
        pitches.append(float("nan") if pitch is None else pitch)
        pitch_quality.append(quality)
    pitch_arr = np.array(pitches, dtype=np.float64)
    pitch_summary = summarize(pitch_arr)

    finite_pitch = pitch_arr[np.isfinite(pitch_arr)]
    if len(finite_pitch) > 0:
        median_pitch = float(np.median(finite_pitch))
        st = 12.0 * np.log2(finite_pitch / median_pitch)
        pitch_variability = round(float(np.std(st)), 3)
    else:
        pitch_variability = None

    pause_total = round(sum(float(p["duration"]) for p in pauses), 3)
    speech_duration = max(0.001, duration - pause_total)
    transcript = load_transcript(Path(args.transcript).expanduser().resolve() if args.transcript else None)
    words = count_words(transcript)
    wpm = round(words / (speech_duration / 60.0), 2) if words is not None else None

    intensity_summary = summarize(energy_db)
    energy_p90 = safe_percentile(energy_db, 90)
    pitch_p90 = safe_percentile(pitch_arr, 90)
    peak_mask = np.zeros(len(times), dtype=bool)
    if energy_p90 is not None:
        peak_mask |= energy_db >= energy_p90
    if pitch_p90 is not None:
        peak_mask |= np.isfinite(pitch_arr) & (pitch_arr >= pitch_p90)
    peak_mask &= ~silence_mask
    raw_peak_regions = contiguous_regions(peak_mask, times, hop_s, min_duration_s=0.12)
    acoustic_peaks = score_acoustic_peaks(
        merge_regions(raw_peak_regions, max_gap_s=0.12),
        times,
        energy_db,
        pitch_arr,
        energy_p90,
        pitch_p90,
    )[:50]

    waveform_step = max(1, math.ceil(len(samples) / 900))
    waveform_times = np.arange(0, len(samples), waveform_step) / sample_rate
    waveform_values = samples[::waveform_step]

    metrics = {
        "duration_seconds": round(duration, 3),
        "speech_duration_seconds": round(speech_duration, 3),
        "pause_count": len(pauses),
        "pause_total_seconds": pause_total,
        "longest_pause_seconds": round(max([p["duration"] for p in pauses], default=0.0), 3),
        "pause_ratio": round(pause_total / duration, 4) if duration > 0 else None,
        "pitch_hz": pitch_summary,
        "pitch_variability_semitones": pitch_variability,
        "intensity_db": intensity_summary,
        "word_count": words,
        "speaking_rate_wpm": wpm,
    }
    trend_metrics = build_trend_metrics(duration, metrics, pauses, acoustic_peaks, pitch_arr)
    progression = build_progression(duration, times, energy_db, pitch_arr, pauses, acoustic_peaks)
    synthesis = build_synthesis(metrics, trend_metrics, progression, acoustic_peaks)
    source_audio = str(audio_path) if args.include_local_paths else audio_path.name
    outputs_dir = str(out_dir) if args.include_local_paths else out_dir.name

    data = {
        "schema_version": "0.2",
        "generated_at": generated_at,
        "source_audio": source_audio,
        "input_audio": source_audio,
        "outputs_dir": outputs_dir,
        "session": {
            "session_id": make_session_id(audio_path, generated_at),
            "recorded_at": args.recorded_at or generated_at,
            "speaker_id": args.speaker,
            "operator": args.operator,
            "goal": args.goal,
            "memo_type": args.memo_type,
            "take_label": args.take_label,
            "transcript_source": "manual" if transcript else "none",
        },
        "comparability": {
            "duration_bucket": duration_bucket(duration),
            "same_script": None,
            "audio_quality_flag": "review_needed" if (intensity_summary.get("std") or 0) > 30 else "ok",
            "pitch_method": "autocorrelation fallback",
            "pause_threshold_seconds": args.min_pause,
        },
        "analyzer": {
            "name": "prosody-lens-basic",
            "pitch_method": "autocorrelation fallback",
            "sample_rate": sample_rate,
            "min_pause_seconds": args.min_pause,
        },
        "metrics": metrics,
        "trend_metrics": trend_metrics,
        "progression": progression,
        "synthesis": synthesis,
        "pauses": pauses,
        "acoustic_peak_candidates": acoustic_peaks,
        "emphasis_candidates": acoustic_peaks,
        "raw_acoustic_peak_count": len(raw_peak_regions),
        "series": {
            "waveform": downsample_pairs(waveform_times, waveform_values),
            "energy_db": downsample_pairs(times, energy_db),
            "pitch_hz": downsample_pairs(times, pitch_arr),
        },
        "share": {
            "html_embeds_audio": not args.share_safe,
            "raw_audio_file": None if args.share_safe else "audio.wav",
            "playback_audio_file": None if args.share_safe else playback_path.name,
            "local_paths_included": bool(args.include_local_paths),
        },
        "transcript": transcript,
        "limitations": [
            "Fallback pitch tracking uses autocorrelation, not Praat.",
            "Acoustic peaks are not confirmed emphasized words without alignment.",
            "No speaking-rate or word-level emphasis without transcript/alignment.",
            "Multiple speakers, music, noise, or echo can distort results.",
            "Descriptive only; not clinical or diagnostic.",
        ],
    }
    if args.include_local_paths:
        data["local_paths"] = {"input_audio": str(audio_path), "outputs_dir": str(out_dir)}

    (out_dir / "prosody.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_report(out_dir, data, audio_path.name)
    write_html(out_dir, data, playback_path, include_audio=not args.share_safe)
    if args.share_safe and wav_path.exists():
        wav_path.unlink()
    if args.share_safe and playback_path.exists():
        playback_path.unlink()
    if args.history:
        append_history(Path(args.history).expanduser().resolve(), data)
    data["_runtime_outputs_dir"] = str(out_dir)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze and visualize speech prosody from an audio file.")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument("--transcript", help="Optional transcript text file")
    parser.add_argument("--out-dir", help="Output directory")
    parser.add_argument("--min-pause", type=float, default=0.25, help="Minimum pause duration in seconds")
    parser.add_argument("--speaker", default=None, help="Stable speaker id for longitudinal comparison")
    parser.add_argument("--operator", default="watson", help="Agent/operator running the analysis")
    parser.add_argument("--goal", default=None, help="Speech goal, such as clarity, pacing, warmth, authority, or storytelling")
    parser.add_argument("--memo-type", default="voice_memo", help="Recording type, such as voice_memo, narration, presentation, or coaching_take")
    parser.add_argument("--take-label", default=None, help="Human label for this take, such as baseline or retake_after_feedback")
    parser.add_argument("--recorded-at", default=None, help="ISO-8601 recording timestamp, if known")
    parser.add_argument("--history", help="Optional JSONL file to append compact trend records")
    parser.add_argument("--share-safe", action="store_true", help="Omit embedded audio and delete audio.wav from the output folder")
    parser.add_argument("--include-local-paths", action="store_true", help="Include absolute local paths in JSON for debugging")
    args = parser.parse_args()

    try:
        data = analyze(args)
    except Exception as exc:
        print(f"prosody_analyze.py: error: {exc}", file=sys.stderr)
        return 1

    runtime_outputs_dir = data.get("_runtime_outputs_dir", data["outputs_dir"])
    print(runtime_outputs_dir)
    print(f"report: {runtime_outputs_dir}/report.md")
    print(f"html:   {runtime_outputs_dir}/report.html")
    if args.history:
        print(f"history: {Path(args.history).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
