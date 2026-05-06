from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def import_aba_checklist(
    conn: sqlite3.Connection,
    csv_path: Path,
    *,
    taxonomy_version: str = "ABA Checklist 8.19",
    region_scope: str = "ABA Area",
) -> int:
    rows = read_aba_rows(csv_path)
    with conn:
        conn.execute("DELETE FROM species_similarity")
        conn.execute("DELETE FROM clips")
        conn.execute("DELETE FROM recordings")
        conn.execute("DELETE FROM species")
        for row in rows:
            conn.execute(
                """
                INSERT INTO species (
                  common_name, scientific_name, ebird_code, family, order_name,
                  taxonomy_source, taxonomy_version, region_scope, range_notes, difficulty
                )
                VALUES (?, ?, ?, ?, ?, 'American Birding Association', ?, ?, ?, ?)
                """,
                (
                    row["common_name"],
                    row["scientific_name"],
                    row["alpha_code"],
                    row["family"],
                    None,
                    taxonomy_version,
                    region_scope,
                    f"ABA Checklist code {row['aba_code']}; {region_scope}.",
                    aba_code_to_difficulty(row["aba_code"]),
                ),
            )
    return len(rows)


def read_aba_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    family = "Unknown"
    with csv_path.open("r", encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle)
        for raw in reader:
            cells = [cell.strip() for cell in raw]
            if not any(cells):
                continue
            if cells[0].startswith("Provisional List"):
                break
            if cells[0] and not cells[1:2]:
                family = cells[0]
                continue
            if cells[0] and len(cells) > 1 and not cells[1]:
                family = cells[0]
                continue
            if len(cells) < 6:
                continue
            if cells[0] == "" and cells[1] and cells[3]:
                rows.append(
                    {
                        "family": family,
                        "common_name": normalize_common_name(cells[1]),
                        "scientific_name": cells[3],
                        "alpha_code": cells[4],
                        "aba_code": cells[5],
                    }
                )
    return rows


def normalize_common_name(value: str) -> str:
    return value.replace(" (", " (").strip()


def aba_code_to_difficulty(value: str) -> int:
    try:
        code = int(value)
    except ValueError:
        return 3
    if code <= 2:
        return 2
    if code == 3:
        return 3
    return 4
