from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize


def main() -> int:
    parser = argparse.ArgumentParser(description="Create compact fixed-length training clips from downloaded recordings.")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--bitrate", default="96k")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    paths = ProjectPaths.discover(ROOT)
    paths.ensure()
    conn = connect(paths.db_path)
    initialize(conn)

    out_dir = paths.root / "data" / "processed" / "training_clips_20s"
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    rows = conn.execute(
        """
        SELECT r.id AS recording_id, r.species_id, r.audio_original_path, r.source_recording_id,
               r.sound_type, r.length_seconds, r.quality, s.difficulty
        FROM recordings r
        JOIN species s ON s.id = r.species_id
        WHERE r.audio_original_path IS NOT NULL AND r.audio_original_path != ''
        ORDER BY r.id
        """
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]

    processed = 0
    copied = 0
    skipped = 0
    with conn:
        conn.execute("DELETE FROM clips")
        for row in rows:
            src = paths.root / row["audio_original_path"]
            if not src.exists():
                skipped += 1
                continue
            safe_type = safe_name(row["sound_type"] or "audio")
            dest = out_dir / f"xc{row['source_recording_id']}_{safe_type}_20s.mp3"
            length = float(row["length_seconds"] or 0)
            duration = args.seconds if length <= 0 else min(args.seconds, length)
            start = choose_start(length, duration)
            if src.suffix.lower() == ".mp3" and length and length <= args.seconds + 0.5:
                shutil.copyfile(src, dest)
                copied += 1
            else:
                command = [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{start:.2f}",
                    "-t",
                    f"{duration:.2f}",
                    "-i",
                    str(src),
                    "-vn",
                    "-ac",
                    "1",
                    "-b:a",
                    args.bitrate,
                    str(dest),
                ]
                try:
                    subprocess.run(command, check=True)
                except subprocess.CalledProcessError:
                    skipped += 1
                    continue
                processed += 1

            conn.execute(
                """
                INSERT INTO clips (
                  recording_id, species_id, clip_path, start_seconds, end_seconds,
                  clip_type, difficulty, has_background_species
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    row["recording_id"],
                    row["species_id"],
                    str(dest.relative_to(paths.root)),
                    start,
                    start + duration,
                    row["sound_type"],
                    row["difficulty"] or 2,
                ),
            )
            conn.execute("UPDATE recordings SET audio_app_path = ?, usable_for_quiz = 1 WHERE id = ?", (str(dest.relative_to(paths.root)), row["recording_id"]))

    total_size = sum(path.stat().st_size for path in out_dir.glob("*.mp3"))
    print(f"created={processed} copied={copied} skipped={skipped} clips={processed + copied}")
    print(f"clip_dir={out_dir}")
    print(f"clip_size_mb={total_size / 1024 / 1024:.2f}")
    return 0


def choose_start(length: float, duration: float) -> float:
    if not length or length <= duration:
        return 0.0
    # Avoid the first few seconds when possible, but stay near the useful middle.
    middle_third = length / 3
    start = max(0.0, middle_third - duration / 2)
    return min(start, max(0.0, length - duration))


def safe_name(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-") or "audio"


if __name__ == "__main__":
    raise SystemExit(main())

