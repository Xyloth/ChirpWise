from __future__ import annotations

import argparse
from pathlib import Path

from .aba import import_aba_checklist
from .audio import normalize_audio, segment_clips
from .build import build_license_manifest, record_dataset_build
from .config import ProjectPaths
from .db import connect, initialize
from .reports import write_coverage_report
from .region_packs import rebuild_region_memberships
from .seed import create_seed_dataset
from .taxonomy import import_taxonomy
from .xeno import XenoQueryOptions, attach_originals_as_clips, download_audio, ingest_xeno_metadata, query_species, remove_fixture_audio


def main(argv: list[str] | None = None) -> int:
    paths = ProjectPaths.discover()
    paths.ensure()

    parser = argparse.ArgumentParser(prog="birdtrainer")
    parser.add_argument("--db", type=Path, default=paths.db_path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")

    seed_parser = sub.add_parser("seed")
    seed_parser.add_argument("--force", action="store_true", help="Replace existing fixture rows")

    tax_parser = sub.add_parser("import-taxonomy")
    tax_parser.add_argument("csv_path", type=Path)
    tax_parser.add_argument("--source", default="eBird/Clements")
    tax_parser.add_argument("--version", default="unknown")
    tax_parser.add_argument("--scope", default="US+Canada")

    aba_parser = sub.add_parser("import-aba")
    aba_parser.add_argument("csv_path", type=Path)
    aba_parser.add_argument("--version", default="ABA Checklist 8.19")
    aba_parser.add_argument("--scope", default="ABA Area")

    query_parser = sub.add_parser("query-xeno")
    query_parser.add_argument("--limit-species", type=int)
    query_parser.add_argument("--country", action="append", default=[])
    query_parser.add_argument("--quality", action="append", default=["A", "B"])
    query_parser.add_argument("--sound-type", action="append", default=["song", "call"])
    query_parser.add_argument("--max-pages", type=int, default=2)
    query_parser.add_argument("--per-page", type=int, default=100)
    query_parser.add_argument("--max-recordings-per-species", type=int, default=2)
    query_parser.add_argument("--polite-delay", type=float, default=0.35)
    query_parser.add_argument("--key", help="Xeno-canto API key. Prefer XENO_CANTO_API_KEY so it is not saved in shell history.")
    query_parser.add_argument("--commercial-build", action="store_true")
    query_parser.add_argument("--exclude-nc", action="store_true")

    sub.add_parser("ingest-xeno-metadata")

    download_parser = sub.add_parser("download-audio")
    download_parser.add_argument("--limit", type=int)
    download_parser.add_argument("--key", help="Xeno-canto API key. Prefer XENO_CANTO_API_KEY.")

    sub.add_parser("attach-original-clips")
    sub.add_parser("remove-fixture-audio")

    normalize_parser = sub.add_parser("normalize-audio")
    normalize_parser.add_argument("--codec", default="opus", choices=["opus", "m4a"])

    clip_parser = sub.add_parser("segment-clips")
    clip_parser.add_argument("--seconds", type=int, default=10)

    build_parser = sub.add_parser("build-database")
    build_parser.add_argument("--taxonomy-source", default="eBird/Clements")
    build_parser.add_argument("--taxonomy-version", default="unknown")
    build_parser.add_argument("--scope", default="US+Canada")
    build_parser.add_argument("--license-policy", default="per-recording Creative Commons")

    sub.add_parser("coverage-report")
    sub.add_parser("license-manifest")
    sub.add_parser("rebuild-regions")

    args = parser.parse_args(argv)
    conn = connect(args.db)
    initialize(conn)

    if args.command == "init-db":
        print(f"Initialized {args.db}")
        return 0
    if args.command == "seed":
        create_seed_dataset(conn, paths.root)
        print(f"Seeded fixture dataset at {args.db}")
        return 0
    if args.command == "import-taxonomy":
        count = import_taxonomy(
            conn,
            args.csv_path,
            taxonomy_source=args.source,
            taxonomy_version=args.version,
            region_scope=args.scope,
        )
        print(f"Imported {count} taxa")
        return 0
    if args.command == "import-aba":
        count = import_aba_checklist(conn, args.csv_path, taxonomy_version=args.version, region_scope=args.scope)
        print(f"Imported {count} ABA checklist species")
        return 0
    if args.command == "query-xeno":
        countries = tuple(args.country or ["United States", "Canada"])
        options = XenoQueryOptions(
            countries=countries,
            qualities=tuple(args.quality),
            sound_types=tuple(args.sound_type),
            max_pages=args.max_pages,
            per_page=args.per_page,
            polite_delay=args.polite_delay,
            allow_noncommercial=not args.exclude_nc,
            commercial_build=args.commercial_build,
            api_key=args.key,
            max_recordings_per_species=args.max_recordings_per_species,
        )
        count = query_species(conn, metadata_dir=paths.xeno_metadata_dir, limit_species=args.limit_species, options=options)
        print(f"Wrote metadata for {count} species")
        return 0
    if args.command == "ingest-xeno-metadata":
        count = ingest_xeno_metadata(conn, paths.xeno_metadata_dir)
        print(f"Imported {count} Xeno-canto recording rows")
        return 0
    if args.command == "download-audio":
        count = download_audio(conn, paths.original_audio_dir, limit=args.limit, api_key=args.key)
        print(f"Downloaded {count} original recordings")
        return 0
    if args.command == "attach-original-clips":
        count = attach_originals_as_clips(conn)
        print(f"Attached {count} original recordings as quiz clips")
        return 0
    if args.command == "remove-fixture-audio":
        count = remove_fixture_audio(conn)
        print(f"Removed {count} fixture recordings")
        return 0
    if args.command == "normalize-audio":
        result = normalize_audio(conn, paths.root, paths.app_audio_dir, codec=args.codec)
        print(result)
        return 0 if not result.get("error") else 2
    if args.command == "segment-clips":
        result = segment_clips(conn, paths.root, paths.clips_dir, seconds=args.seconds)
        print(result)
        return 0 if not result.get("error") else 2
    if args.command == "build-database":
        build_id = record_dataset_build(
            conn,
            taxonomy_source=args.taxonomy_source,
            taxonomy_version=args.taxonomy_version,
            region_scope=args.scope,
            license_policy=args.license_policy,
        )
        print(f"Recorded dataset build {build_id}")
        return 0
    if args.command == "coverage-report":
        count = write_coverage_report(conn, paths.manifests_dir / "coverage_report.csv")
        print(f"Wrote coverage for {count} species")
        return 0
    if args.command == "license-manifest":
        count = build_license_manifest(conn, paths.manifests_dir / "license_manifest.json")
        print(f"Wrote {count} attribution rows")
        return 0
    if args.command == "rebuild-regions":
        rebuild_region_memberships(conn)
        print("Rebuilt species region memberships")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
