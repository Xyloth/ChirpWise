from __future__ import annotations

import argparse
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.build import build_license_manifest, record_dataset_build
from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize
from ingest.birdtrainer.reports import write_coverage_report
from ingest.birdtrainer.xeno import (
    XenoQueryOptions,
    attach_originals_as_clips,
    download_audio,
    ingest_xeno_metadata,
    query_species,
    remove_fixture_audio,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch real Xeno-canto audio into the local trainer dataset.")
    parser.add_argument("--key", help="Xeno-canto API key. Prefer XENO_CANTO_API_KEY.")
    parser.add_argument("--limit-species", type=int, default=12)
    parser.add_argument("--country", action="append", default=["United States", "Canada"])
    parser.add_argument("--quality", action="append", default=["A", "B"])
    parser.add_argument("--sound-type", action="append", default=["song", "call"])
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--keep-fixtures", action="store_true")
    parser.add_argument("--commercial-build", action="store_true")
    parser.add_argument("--exclude-nc", action="store_true")
    args = parser.parse_args()

    paths = ProjectPaths.discover(ROOT)
    paths.ensure()
    conn = connect(paths.db_path)
    initialize(conn)

    options = XenoQueryOptions(
        countries=tuple(args.country),
        qualities=tuple(args.quality),
        sound_types=tuple(args.sound_type),
        max_pages=args.max_pages,
        per_page=args.per_page,
        allow_noncommercial=not args.exclude_nc,
        commercial_build=args.commercial_build,
        api_key=args.key,
    )
    print("Querying Xeno-canto API v3 metadata...")
    metadata_files = query_species(conn, metadata_dir=paths.xeno_metadata_dir, limit_species=args.limit_species, options=options)
    print(f"Wrote metadata files for {metadata_files} species")

    metadata_rows = ingest_xeno_metadata(conn, paths.xeno_metadata_dir)
    print(f"Imported/updated {metadata_rows} Xeno-canto recording rows")

    downloaded = download_audio(conn, paths.original_audio_dir, api_key=args.key)
    print(f"Downloaded {downloaded} real audio files")

    attached = attach_originals_as_clips(conn)
    print(f"Attached {attached} original recordings as playable quiz clips")

    if attached and not args.keep_fixtures:
        removed = remove_fixture_audio(conn)
        print(f"Removed {removed} generated fixture recordings")

    record_dataset_build(
        conn,
        taxonomy_source="fixture species list + Xeno-canto",
        taxonomy_version="demo-2026.05",
        region_scope="US+Canada",
        license_policy="Xeno-canto API v3; originals attached as quiz audio; per-recording CC metadata preserved",
    )
    coverage_rows = write_coverage_report(conn, paths.manifests_dir / "coverage_report.csv")
    license_rows = build_license_manifest(conn, paths.manifests_dir / "license_manifest.json")
    print(f"Wrote coverage report for {coverage_rows} species")
    print(f"Wrote license manifest for {license_rows} recordings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

