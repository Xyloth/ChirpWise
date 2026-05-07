from __future__ import annotations

import argparse
import array
import json
import math
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg


DEFAULT_DB = Path("data/app/birdtrainer.sqlite3")
DEFAULT_ASSETS = Path("android/app/src/main/assets")
WAVEFORM_BARS = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bundled Android quiz assets from the local bird database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--region", default="northeast")
    parser.add_argument("--pack-name", default="Northeast / Ohio Valley")
    parser.add_argument("--clip-seconds", type=int, default=20)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path.cwd()
    db_path = args.db
    assets_dir = args.assets
    audio_dir = assets_dir / "audio"

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    if args.clean and audio_dir.exists():
        shutil.rmtree(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(db_path, args.region)
    clips = []
    copied = 0
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    for row in rows:
        source = Path(row["clip_path"])
        if not source.is_absolute():
            source = project_root / source
        if not source.exists():
            continue

        target = audio_dir / source.name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
            copied += 1

        clips.append(
            {
                "clipId": row["clip_id"],
                "speciesId": row["species_id"],
                "commonName": row["common_name"],
                "scientificName": row["scientific_name"],
                "family": row["family"] or "Unknown",
                "clipType": row["clip_type"] or "audio",
                "difficulty": row["difficulty"] or 2,
                "audio": f"audio/{target.name}",
                "country": row["country"] or "",
                "location": row["location"] or "Unknown location",
                "recordist": row["recordist"] or "Unknown recordist",
                "licenseName": row["license_name"] or "Unknown license",
                "licenseUrl": row["license_url"] or "",
                "attribution": row["attribution_text"] or attribution(row),
                "sourceUrl": row["source_url"] or "",
                "waveform": waveform_peaks(source, ffmpeg),
            }
        )

    dataset = {
        "pack": args.pack_name,
        "region": args.region,
        "clipSeconds": args.clip_seconds,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "speciesCount": len({clip["speciesId"] for clip in clips}),
        "count": len(clips),
        "clips": clips,
    }
    (assets_dir / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(clips)} clips to {assets_dir} ({copied} audio files copied).")


def load_rows(db_path: Path, region: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT
              c.id AS clip_id,
              c.clip_path,
              c.clip_type,
              c.difficulty,
              s.id AS species_id,
              s.common_name,
              s.scientific_name,
              s.family,
              r.country,
              r.location,
              r.recordist,
              r.license_name,
              r.license_url,
              r.attribution_text,
              r.source_url
            FROM clips c
            JOIN species s ON s.id = c.species_id
            JOIN species_region_membership m ON m.species_id = s.id
            LEFT JOIN recordings r ON r.id = c.recording_id
            WHERE m.region_id = ?
            ORDER BY s.common_name COLLATE NOCASE
            """,
            (region,),
        ).fetchall()
    finally:
        conn.close()


def attribution(row: sqlite3.Row) -> str:
    source = row["source_url"] or "xeno-canto"
    recordist = row["recordist"] or "unknown recordist"
    license_name = row["license_name"] or "unknown license"
    return f"{row['common_name']} recording; recorded by {recordist}; licensed {license_name}; {source}"


def waveform_peaks(source: Path, ffmpeg: str) -> list[float]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vn",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "8000",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return []

    samples = array.array("h")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return []

    bin_size = max(1, math.ceil(len(samples) / WAVEFORM_BARS))
    peaks: list[float] = []
    for start in range(0, len(samples), bin_size):
        chunk = samples[start : min(start + bin_size, len(samples))]
        if not chunk:
            peaks.append(0.0)
            continue
        square_sum = sum(sample * sample for sample in chunk)
        peaks.append(math.sqrt(square_sum / len(chunk)) / 32768.0)
        if len(peaks) >= WAVEFORM_BARS:
            break

    while len(peaks) < WAVEFORM_BARS:
        peaks.append(0.0)

    maximum = max(peaks)
    if maximum <= 0:
        return peaks
    return [round(min(1.0, value / maximum), 3) for value in peaks]


if __name__ == "__main__":
    main()
