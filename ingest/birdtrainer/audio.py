from __future__ import annotations

import math
import shutil
import sqlite3
import struct
import subprocess
import wave
from pathlib import Path

from .license_policy import evaluate_license


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def normalize_audio(conn: sqlite3.Connection, root: Path, output_dir: Path, *, codec: str = "opus") -> dict[str, int | str | None]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"processed": 0, "skipped": 0, "error": "ffmpeg not found"}

    output_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    skipped = 0
    rows = conn.execute(
        """
        SELECT id, audio_original_path, source_recording_id, license_name, license_url
        FROM recordings
        WHERE audio_original_path IS NOT NULL AND audio_original_path != ''
        ORDER BY id
        """
    ).fetchall()
    for row in rows:
        decision = evaluate_license(row["license_name"], row["license_url"], derivative_required=True)
        if not decision.allowed:
            skipped += 1
            continue
        src = root / row["audio_original_path"]
        if not src.exists():
            skipped += 1
            continue
        ext = ".opus" if codec == "opus" else ".m4a"
        dest = output_dir / f"xc{row['source_recording_id']}{ext}"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-af",
            "loudnorm=I=-18:TP=-1.5:LRA=11",
            str(dest),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with conn:
            conn.execute(
                "UPDATE recordings SET audio_app_path = ?, usable_for_quiz = 1 WHERE id = ?",
                (str(dest.relative_to(root)), row["id"]),
            )
        processed += 1
    return {"processed": processed, "skipped": skipped, "error": None}


def segment_clips(conn: sqlite3.Connection, root: Path, clips_dir: Path, *, seconds: int = 10) -> dict[str, int | str | None]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"processed": 0, "skipped": 0, "error": "ffmpeg not found"}

    clips_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    skipped = 0
    rows = conn.execute(
        """
        SELECT r.id AS recording_id, r.species_id, r.audio_app_path, r.source_recording_id,
               r.sound_type, r.license_name, r.license_url, s.common_name
        FROM recordings r
        JOIN species s ON s.id = r.species_id
        WHERE r.audio_app_path IS NOT NULL AND r.audio_app_path != ''
        ORDER BY r.quality, r.id
        """
    ).fetchall()
    for row in rows:
        decision = evaluate_license(row["license_name"], row["license_url"], derivative_required=True)
        if not decision.allowed:
            skipped += 1
            continue
        src = root / row["audio_app_path"]
        if not src.exists():
            skipped += 1
            continue
        dest = clips_dir / f"xc{row['source_recording_id']}_clip.opus"
        command = [
            ffmpeg,
            "-y",
            "-ss",
            "0",
            "-t",
            str(seconds),
            "-i",
            str(src),
            "-ac",
            "1",
            str(dest),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with conn:
            conn.execute(
                """
                INSERT INTO clips (
                  recording_id, species_id, clip_path, start_seconds, end_seconds,
                  clip_type, difficulty, has_background_species
                )
                VALUES (?, ?, ?, 0, ?, ?, 2, 0)
                """,
                (row["recording_id"], row["species_id"], str(dest.relative_to(root)), seconds, row["sound_type"]),
            )
        processed += 1
    return {"processed": processed, "skipped": skipped, "error": None}


def write_fixture_wav(path: Path, *, pattern_seed: int, seconds: float = 7.5, sample_rate: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = int(seconds * sample_rate)
    frames = bytearray()
    base = 650 + (pattern_seed % 9) * 95
    pulse_gap = 0.22 + (pattern_seed % 5) * 0.035
    pulse_len = 0.08 + (pattern_seed % 4) * 0.025
    sweep = 120 + (pattern_seed % 6) * 40

    for i in range(total_frames):
        t = i / sample_rate
        pulse_position = t % pulse_gap
        envelope = 0.0
        if pulse_position < pulse_len:
            attack = min(1.0, pulse_position / 0.015)
            decay = max(0.0, 1.0 - (pulse_position / pulse_len))
            envelope = attack * decay
        phrase = 0.65 + 0.35 * math.sin(2 * math.pi * (0.18 + pattern_seed * 0.01) * t)
        freq = base + sweep * math.sin(2 * math.pi * (2.0 + (pattern_seed % 3)) * t)
        harmonic = 0.35 * math.sin(2 * math.pi * freq * 2.01 * t)
        sample = envelope * phrase * (math.sin(2 * math.pi * freq * t) + harmonic)
        sample += 0.015 * math.sin(2 * math.pi * 120 * t)
        value = max(-1.0, min(1.0, sample * 0.55))
        frames.extend(struct.pack("<h", int(value * 32767)))

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))

