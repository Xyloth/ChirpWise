from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize
from ingest.birdtrainer.xeno import (
    XenoQueryOptions,
    api_key_from_env_or_option,
    collect_recordings_for_query,
    download_audio,
    ingest_xeno_metadata,
    slugify,
)


REGION_BOXES = {
    "northeast": "36,-90,48.5,-66",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill regional Xeno-canto recordings for species without clips.")
    parser.add_argument("--region", default="northeast", choices=sorted(REGION_BOXES))
    parser.add_argument("--limit-species", type=int)
    parser.add_argument("--quality", action="append", default=["A", "B"])
    parser.add_argument("--sound-type", action="append", default=["song", "call"])
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--polite-delay", type=float, default=0.35)
    parser.add_argument("--key", help="Xeno-canto API key. Prefer XENO_CANTO_API_KEY or .env.local.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.discover(ROOT)
    paths.ensure()
    conn = connect(paths.db_path)
    initialize(conn)
    key = api_key_from_env_or_option(args.key)
    metadata_dir = paths.xeno_metadata_dir / f"{args.region}_backfill"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    rows = species_without_clips(conn, args.region)
    if args.limit_species:
        rows = rows[: args.limit_species]

    options = XenoQueryOptions(
        countries=(),
        qualities=tuple(args.quality),
        sound_types=tuple(args.sound_type),
        max_pages=1,
        per_page=args.per_page,
        polite_delay=args.polite_delay,
        api_key=key,
        max_recordings_per_species=1,
    )

    written = 0
    for row in rows:
        payload = {
            "species_id": row["id"],
            "common_name": row["common_name"],
            "scientific_name": row["scientific_name"],
            "api": "xeno-canto v3",
            "queries": [],
            "recordings": [],
        }
        seen_ids: set[str] = set()
        for query in regional_queries(row["scientific_name"], REGION_BOXES[args.region], args.quality, args.sound_type):
            collect_recordings_for_query(key, query, payload, seen_ids, options)
            if payload["recordings"]:
                break
            time.sleep(args.polite_delay)

        if payload["recordings"]:
            out_path = metadata_dir / f"{row['id']:05d}_{slugify(row['common_name'])}.json"
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
            written += 1

    ingested = ingest_xeno_metadata(conn, metadata_dir)
    downloaded = download_audio(conn, paths.original_audio_dir, api_key=key)
    print(f"Regional no-clip species: {len(rows)}")
    print(f"Wrote metadata for {written}; ingested {ingested}; downloaded {downloaded}.")
    return 0


def species_without_clips(conn, region_id: str):
    return conn.execute(
        """
        SELECT s.id, s.common_name, s.scientific_name
        FROM species s
        JOIN species_region_membership m ON m.species_id = s.id
        WHERE m.region_id = ?
          AND NOT EXISTS (SELECT 1 FROM clips c WHERE c.species_id = s.id)
        ORDER BY s.common_name COLLATE NOCASE
        """,
        (region_id,),
    ).fetchall()


def regional_queries(scientific_name: str, box: str, qualities: list[str], sound_types: list[str]) -> list[str]:
    queries: list[str] = []
    for quality in qualities:
        for sound_type in [*sound_types, None]:
            parts = [f'sp:"{scientific_name}"', "grp:birds", f"q:{quality}", f"box:{box}", 'len:"<180"']
            if sound_type:
                parts.append(f"type:{sound_type}")
            queries.append(" ".join(parts))
    return queries


if __name__ == "__main__":
    raise SystemExit(main())
