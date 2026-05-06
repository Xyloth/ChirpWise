from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def write_coverage_report(conn: sqlite3.Connection, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT
          s.common_name,
          s.scientific_name,
          s.family,
          s.region_scope,
          COUNT(DISTINCT r.id) AS recordings,
          COUNT(DISTINCT c.id) AS clips,
          SUM(CASE WHEN lower(COALESCE(r.sound_type, '')) LIKE '%song%' THEN 1 ELSE 0 END) AS song_recordings,
          SUM(CASE WHEN lower(COALESCE(r.sound_type, '')) LIKE '%call%' THEN 1 ELSE 0 END) AS call_recordings,
          MIN(r.quality) AS best_quality
        FROM species s
        LEFT JOIN recordings r ON r.species_id = s.id
        LEFT JOIN clips c ON c.species_id = s.id
        GROUP BY s.id
        ORDER BY clips ASC, recordings ASC, s.common_name
        """
    ).fetchall()
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(rows[0].keys() if rows else ["common_name", "scientific_name", "family", "region_scope", "recordings", "clips"])
        for row in rows:
            writer.writerow([row[key] for key in row.keys()])
    return len(rows)

