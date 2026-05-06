from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def record_dataset_build(
    conn: sqlite3.Connection,
    *,
    taxonomy_source: str,
    taxonomy_version: str,
    region_scope: str,
    license_policy: str,
) -> int:
    species_count = conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
    recording_count = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    clip_count = conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
    coverage = {
        "species_total": species_count,
        "species_with_recordings": conn.execute("SELECT COUNT(DISTINCT species_id) FROM recordings").fetchone()[0],
        "species_with_clips": conn.execute("SELECT COUNT(DISTINCT species_id) FROM clips").fetchone()[0],
    }
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO dataset_builds (
              taxonomy_source, taxonomy_version, region_scope, license_policy,
              species_count, recording_count, clip_count, coverage_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                taxonomy_source,
                taxonomy_version,
                region_scope,
                license_policy,
                species_count,
                recording_count,
                clip_count,
                json.dumps(coverage, sort_keys=True),
            ),
        )
    return int(cursor.lastrowid)


def build_license_manifest(conn: sqlite3.Connection, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT s.common_name, s.scientific_name, r.source, r.source_recording_id,
               r.source_url, r.recordist, r.license_name, r.license_url, r.attribution_text
        FROM recordings r
        JOIN species s ON s.id = r.species_id
        ORDER BY s.common_name, r.source_recording_id
        """
    ).fetchall()
    data = [dict(row) for row in rows]
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    return len(data)

