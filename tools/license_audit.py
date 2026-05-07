from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("data/app/birdtrainer.sqlite3")
DEFAULT_OUT_DIR = Path("docs/audits")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bundled clips for paid-app use after trimming.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    rows = audit_rows(args.db)
    summary = build_summary(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "commercial-license-audit.csv", rows)
    write_json(args.out_dir / "commercial-license-audit.json", rows, summary)
    write_markdown(args.out_dir / "commercial-license-audit.md", rows, summary)

    print(f"Audited {summary['total_clips']} clips.")
    print(f"Paid trimmed app-safe clips: {summary['app_safe_clips']}")
    print(f"Needs replacement or permission: {summary['unsafe_clips']}")
    print(f"Wrote audit files to {args.out_dir}")


def audit_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        source_rows = conn.execute(
            """
            SELECT
              c.id AS clip_id,
              s.common_name,
              s.scientific_name,
              s.family,
              r.source_recording_id,
              r.recordist,
              r.source_url,
              r.license_name,
              r.license_url,
              r.length_seconds AS original_length_seconds,
              c.start_seconds,
              c.end_seconds,
              c.clip_path,
              c.clip_type
            FROM clips c
            JOIN species s ON s.id = c.species_id
            LEFT JOIN recordings r ON r.id = c.recording_id
            ORDER BY s.common_name COLLATE NOCASE, c.id
            """
        ).fetchall()
    finally:
        conn.close()

    rows: list[dict[str, Any]] = []
    for source in source_rows:
        clip_length = nullable_clip_length(source["start_seconds"], source["end_seconds"])
        classification = classify_license(
            source["license_name"] or "",
            source["license_url"] or "",
            modified=True,
        )
        rows.append(
            {
                "clip_id": source["clip_id"],
                "bird_name": source["common_name"],
                "scientific_name": source["scientific_name"],
                "family": source["family"] or "Unknown",
                "xeno_canto_recording_id": source["source_recording_id"] or "",
                "recordist": source["recordist"] or "Unknown recordist",
                "source_url": source["source_url"] or "",
                "license_name": source["license_name"] or "Unknown license",
                "license_url": source["license_url"] or "",
                "original_length_seconds": round_nullable(source["original_length_seconds"]),
                "clip_start_seconds": round_nullable(source["start_seconds"]),
                "clip_end_seconds": round_nullable(source["end_seconds"]),
                "clip_length_seconds": round_nullable(clip_length),
                "modified": "yes",
                "commercial_allowed": yes_no(classification["commercial_allowed"]),
                "derivatives_allowed": yes_no(classification["derivatives_allowed"]),
                "share_alike_required": yes_no(classification["share_alike_required"]),
                "app_safe": yes_no(classification["app_safe"]),
                "app_safe_reason": classification["reason"],
            }
        )
    return rows


def classify_license(license_name: str, license_url: str, modified: bool) -> dict[str, Any]:
    text = f"{license_name} {license_url}".upper()
    is_known_cc = "CC" in text or "CREATIVECOMMONS.ORG" in text
    is_cc0 = "CC0" in text or "PUBLICDOMAIN/ZERO" in text
    has_nc = "BY-NC" in text or "/BY-NC" in text or "-NC" in text
    has_nd = "BY-ND" in text or "NC-ND" in text or "-ND" in text
    has_sa = "BY-SA" in text or "NC-SA" in text or "-SA" in text

    commercial_allowed = is_cc0 or (is_known_cc and not has_nc)
    derivatives_allowed = is_cc0 or (is_known_cc and not has_nd)
    share_alike_required = (not is_cc0) and has_sa

    if not is_known_cc and not is_cc0:
        app_safe = False
        reason = "Unknown or missing license; do not use in paid build without permission."
    elif not commercial_allowed:
        app_safe = False
        reason = "NonCommercial license; exclude from paid app unless the recordist grants permission."
    elif modified and not derivatives_allowed:
        app_safe = False
        reason = "NoDerivatives license; exclude because the app distributes a trimmed clip."
    elif share_alike_required:
        app_safe = True
        reason = "Commercial derivatives allowed, but the trimmed clip must remain under the same ShareAlike license."
    else:
        app_safe = True
        reason = "Commercial derivatives allowed with attribution."

    return {
        "commercial_allowed": commercial_allowed,
        "derivatives_allowed": derivatives_allowed,
        "share_alike_required": share_alike_required,
        "app_safe": app_safe,
        "reason": reason,
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_license = Counter(row["license_name"] for row in rows)
    safe_rows = [row for row in rows if row["app_safe"] == "yes"]
    unsafe_rows = [row for row in rows if row["app_safe"] == "no"]
    safe_species = {row["bird_name"] for row in safe_rows}
    unsafe_species = {row["bird_name"] for row in unsafe_rows}
    replacement_species = unsafe_species - safe_species

    safe_by_license = defaultdict(lambda: {"safe": 0, "unsafe": 0})
    for row in rows:
        bucket = "safe" if row["app_safe"] == "yes" else "unsafe"
        safe_by_license[row["license_name"]][bucket] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_clips": len(rows),
        "app_safe_clips": len(safe_rows),
        "unsafe_clips": len(unsafe_rows),
        "app_safe_species": len(safe_species),
        "species_needing_replacement_or_permission": len(replacement_species),
        "license_counts": dict(sorted(by_license.items(), key=lambda item: (-item[1], item[0]))),
        "safe_by_license": {
            key: safe_by_license[key]
            for key in sorted(safe_by_license.keys(), key=lambda item: (-by_license[item], item))
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    payload = {"summary": summary, "clips": rows}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# ChirpWise Commercial License Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "This audit treats ChirpWise as a paid app and treats every bundled practice sound as a modified/adapted clip because the pipeline trims recordings for quiz use.",
        "",
        "This is an engineering triage report, not legal advice. It is meant to decide which clips should ship in a paid build, which clips require recordist permission, and which birds need replacement audio.",
        "",
        "## Result",
        "",
        f"- Total bundled clips audited: {summary['total_clips']}",
        f"- Paid trimmed app-safe clips: {summary['app_safe_clips']}",
        f"- Clips needing replacement or recordist permission: {summary['unsafe_clips']}",
        f"- App-safe species represented: {summary['app_safe_species']}",
        f"- Species needing replacement or permission: {summary['species_needing_replacement_or_permission']}",
        "",
        "## License Counts",
        "",
        "| License | Clips | Paid trimmed app-safe | Not app-safe |",
        "| --- | ---: | ---: | ---: |",
    ]
    for license_name, count in summary["license_counts"].items():
        status = summary["safe_by_license"][license_name]
        lines.append(f"| {license_name} | {count} | {status['safe']} | {status['unsafe']} |")

    lines.extend(
        [
            "",
            "## Rule Used",
            "",
            "| License family | Paid app | Trimmed clip | Audit decision |",
            "| --- | --- | --- | --- |",
            "| CC0 / public domain | yes | yes | app-safe |",
            "| CC BY | yes | yes | app-safe with attribution |",
            "| CC BY-SA | yes | yes | app-safe, ShareAlike required for the adapted clip |",
            "| CC BY-NC / CC BY-NC-SA | no | maybe | exclude from paid app unless permission is granted |",
            "| CC BY-ND / CC BY-NC-ND | mixed | no | exclude because ChirpWise ships trimmed clips |",
            "",
            "## Attribution Fields Required In App",
            "",
            "For every clip shown to a user, preserve:",
            "",
            "- Species name",
            "- Xeno-canto recording ID",
            "- Recordist",
            "- Exact source URL",
            "- License name and URL",
            "- Change note, e.g. `Trimmed to 20 seconds for quiz use`",
            "",
            "## Files",
            "",
            "- `commercial-license-audit.csv`: row-by-row spreadsheet audit",
            "- `commercial-license-audit.json`: same audit with machine-readable summary",
            "",
            "## Source Notes",
            "",
            "- Creative Commons license deeds and FAQ were used for NC, ND, BY, SA, CC0, commercial-use, derivative/adaptation, and attribution rules.",
            "- Xeno-canto API metadata supplies `rec`, `lic`, `url`, and recording IDs; the local database preserves those fields per clip.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def nullable_clip_length(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, float(end) - float(start))


def round_nullable(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    main()
