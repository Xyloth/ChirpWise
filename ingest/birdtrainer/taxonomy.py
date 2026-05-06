from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path


FIELD_ALIASES = {
    "common_name": ["common_name", "common name", "english name", "primary common name", "species"],
    "scientific_name": ["scientific_name", "scientific name", "sci_name", "latin name"],
    "ebird_code": ["ebird_code", "species_code", "species code", "taxon code"],
    "family": ["family", "family_name", "family name"],
    "order_name": ["order", "order_name", "order name"],
    "range_notes": ["range", "range_notes", "range notes", "breeding range", "nonbreeding range"],
}


@dataclass(frozen=True)
class Taxon:
    common_name: str
    scientific_name: str
    ebird_code: str | None = None
    family: str | None = None
    order_name: str | None = None
    range_notes: str | None = None


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace("-", " ").replace("_", " ")


def _field_lookup(headers: list[str]) -> dict[str, str]:
    normalized = {_normalize_header(header): header for header in headers}
    lookup: dict[str, str] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            key = _normalize_header(alias)
            if key in normalized:
                lookup[canonical] = normalized[key]
                break
    return lookup


def read_taxonomy_csv(path: Path) -> list[Taxon]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Taxonomy CSV has no header: {path}")
        lookup = _field_lookup(reader.fieldnames)
        required = ["common_name", "scientific_name"]
        missing = [field for field in required if field not in lookup]
        if missing:
            raise ValueError(f"Taxonomy CSV is missing required fields: {', '.join(missing)}")

        taxa: list[Taxon] = []
        for row in reader:
            common = (row.get(lookup["common_name"]) or "").strip()
            scientific = (row.get(lookup["scientific_name"]) or "").strip()
            if not common or not scientific:
                continue
            taxa.append(
                Taxon(
                    common_name=common,
                    scientific_name=scientific,
                    ebird_code=(row.get(lookup.get("ebird_code", "")) or "").strip() or None,
                    family=(row.get(lookup.get("family", "")) or "").strip() or None,
                    order_name=(row.get(lookup.get("order_name", "")) or "").strip() or None,
                    range_notes=(row.get(lookup.get("range_notes", "")) or "").strip() or None,
                )
            )
    return taxa


def import_taxonomy(
    conn: sqlite3.Connection,
    csv_path: Path,
    *,
    taxonomy_source: str = "eBird/Clements",
    taxonomy_version: str = "unknown",
    region_scope: str = "unspecified",
) -> int:
    taxa = read_taxonomy_csv(csv_path)
    with conn:
        for taxon in taxa:
            conn.execute(
                """
                INSERT INTO species (
                  common_name, scientific_name, ebird_code, family, order_name,
                  taxonomy_source, taxonomy_version, region_scope, range_notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scientific_name, region_scope) DO UPDATE SET
                  common_name = excluded.common_name,
                  ebird_code = excluded.ebird_code,
                  family = excluded.family,
                  order_name = excluded.order_name,
                  taxonomy_source = excluded.taxonomy_source,
                  taxonomy_version = excluded.taxonomy_version,
                  range_notes = excluded.range_notes
                """,
                (
                    taxon.common_name,
                    taxon.scientific_name,
                    taxon.ebird_code,
                    taxon.family,
                    taxon.order_name,
                    taxonomy_source,
                    taxonomy_version,
                    region_scope,
                    taxon.range_notes,
                ),
            )
    return len(taxa)

