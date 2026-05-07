from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize
from ingest.birdtrainer.xeno import api_key_from_env_or_option, fetch_recordings


@dataclass(frozen=True)
class RegionBox:
    name: str
    box: str


REGION_BOXES = {
    "northeast": RegionBox("Northeast / Ohio Valley", "36,-90,48.5,-66"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update regional species membership from Xeno-canto recording geography.")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--region", default="northeast", choices=sorted(REGION_BOXES))
    parser.add_argument("--quality", action="append", default=["A", "B"])
    parser.add_argument("--per-page", type=int, default=500)
    parser.add_argument("--polite-delay", type=float, default=0.2)
    parser.add_argument("--key", help="Xeno-canto API key. Prefer XENO_CANTO_API_KEY or .env.local.")
    parser.add_argument("--keep-existing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = ProjectPaths.discover(ROOT)
    paths.ensure()
    db_path = args.db or paths.db_path
    key = api_key_from_env_or_option(args.key)
    region = REGION_BOXES[args.region]

    species = fetch_region_species(key, region.box, args.quality, args.per_page, args.polite_delay)
    conn = connect(db_path)
    initialize(conn)
    try:
        matched, unmatched = update_membership(conn, args.region, species, keep_existing=args.keep_existing)
    finally:
        conn.close()

    print(f"Fetched {len(species)} regional species from Xeno-canto {region.name}.")
    print(f"Matched {matched} local taxonomy species; {len(unmatched)} unmatched.")
    if unmatched:
        print("Unmatched examples: " + ", ".join(sorted(unmatched)[:12]))
    return 0


def fetch_region_species(
    key: str,
    box: str,
    qualities: list[str],
    per_page: int,
    polite_delay: float,
) -> set[tuple[str, str]]:
    species: set[tuple[str, str]] = set()
    for quality in qualities:
        query = f"grp:birds q:{quality} box:{box}"
        page = 1
        while True:
            payload = fetch_recordings(query, key=key, page=page, per_page=per_page)
            for recording in payload.get("recordings", []):
                gen = (recording.get("gen") or "").strip()
                sp = (recording.get("sp") or "").strip()
                common = (recording.get("en") or "").strip()
                if gen and sp:
                    species.add((f"{gen} {sp}".lower(), common.lower()))
            num_pages = int(payload.get("numPages") or 1)
            if page >= num_pages:
                break
            page += 1
            time.sleep(polite_delay)
    return species


def update_membership(
    conn,
    region_id: str,
    species: set[tuple[str, str]],
    *,
    keep_existing: bool,
) -> tuple[int, set[str]]:
    if not keep_existing:
        conn.execute("DELETE FROM species_region_membership WHERE region_id = ?", (region_id,))

    matched = 0
    unmatched: set[str] = set()
    with conn:
        for scientific_name, common_name in sorted(species):
            row = conn.execute(
                """
                SELECT id FROM species
                WHERE lower(scientific_name) = ?
                   OR lower(common_name) = ?
                LIMIT 1
                """,
                (scientific_name, common_name),
            ).fetchone()
            if row is None:
                unmatched.add(scientific_name)
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO species_region_membership (species_id, region_id, reason)
                VALUES (?, ?, ?)
                """,
                (row["id"], region_id, "Xeno-canto A/B recording inside regional bounding box"),
            )
            matched += 1
    return matched, unmatched


if __name__ == "__main__":
    raise SystemExit(main())
