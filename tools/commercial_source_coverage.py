from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.xeno import api_key_from_env_or_option, fetch_recordings, license_name_from_url


DEFAULT_DB = Path("data/app/birdtrainer.sqlite3")
DEFAULT_OUT_DIR = Path("docs/audits")
DEFAULT_CACHE_DIR = Path("data/manifests/source_coverage_cache")

SAFE_XC_LICENSES = ("BY-SA", "BY", "PD")
SAFE_LICENSE_MARKERS = ("CC0", "PUBLICDOMAIN/ZERO", "CC BY ", "CC-BY", "BY-SA", "CC BY-SA")
UNSAFE_LICENSE_MARKERS = ("NC", "ND", "NONCOMMERCIAL", "NO DERIVATIVES")
INAT_SAFE_LICENSES = "cc0,cc-by,cc-by-sa"


@dataclass(frozen=True)
class Species:
    species_id: int
    common_name: str
    scientific_name: str
    family: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map commercial-safe audio source coverage for the North America bird list.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--skip-commons", action="store_true")
    parser.add_argument("--skip-inat", action="store_true")
    parser.add_argument("--polite-delay", type=float, default=0.15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    species = load_species(args.db)
    rows = [empty_row(item) for item in species]
    by_scientific = {item.scientific_name.lower(): item for item in species}
    row_by_id = {row["species_id"]: row for row in rows}

    print(f"Mapping {len(species)} North America taxonomy species.")
    xeno_americas = load_xeno_safe_index(args.cache_dir, scope="americas", query_scope="area:america")
    xeno_global = load_xeno_safe_index(args.cache_dir, scope="global", query_scope="")

    apply_xeno(rows, by_scientific, xeno_americas, "xeno-canto", "americas")
    apply_xeno(rows, by_scientific, xeno_global, "xeno-canto", "global")
    print(f"Xeno-canto mapped {count_covered(rows)} species with commercial-safe exact scientific-name matches.")

    apply_nps(rows)
    print(f"After NPS public-domain official clips: {count_covered(rows)} species covered.")

    if not args.skip_commons:
        map_commons(rows, args.cache_dir, args.polite_delay)
        print(f"After Wikimedia Commons exact-match safe audio: {count_covered(rows)} species covered.")

    if not args.skip_inat:
        map_inaturalist(rows, args.cache_dir, args.polite_delay)
        print(f"After iNaturalist research-grade safe-sound candidates: {count_covered(rows)} species covered.")

    summary = build_summary(rows)
    write_outputs(args.out_dir, rows, summary)
    print_summary(summary)


def load_species(db_path: Path) -> list[Species]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [
            Species(
                species_id=row["id"],
                common_name=row["common_name"],
                scientific_name=row["scientific_name"],
                family=row["family"] or "Unknown",
            )
            for row in conn.execute(
                "SELECT id, common_name, scientific_name, family FROM species ORDER BY common_name COLLATE NOCASE"
            )
        ]
    finally:
        conn.close()


def empty_row(species: Species) -> dict[str, Any]:
    return {
        "species_id": species.species_id,
        "common_name": species.common_name,
        "scientific_name": species.scientific_name,
        "family": species.family,
        "covered": "no",
        "coverage_tier": "missing",
        "primary_source": "",
        "source_scope": "",
        "source_recording_id": "",
        "source_url": "",
        "audio_url": "",
        "license_name": "",
        "license_url": "",
        "quality": "",
        "recordist": "",
        "sound_type": "",
        "commercial_allowed": "",
        "derivatives_allowed": "",
        "requires_share_alike": "",
        "manual_qc_required": "",
        "confidence": "",
        "notes": "",
        "candidate_count": 0,
    }


def load_xeno_safe_index(cache_dir: Path, *, scope: str, query_scope: str) -> dict[str, list[dict[str, Any]]]:
    cache_path = cache_dir / f"xeno_{scope}_safe.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    key = api_key_from_env_or_option(None)
    index: dict[str, list[dict[str, Any]]] = {}
    for license_tag in SAFE_XC_LICENSES:
        query = " ".join(part for part in ["grp:birds", query_scope, f"lic:{license_tag}"] if part)
        first = fetch_recordings(query, key=key, page=1, per_page=500)
        pages = int(first.get("numPages") or 1)
        print(f"Fetching XC {scope} {license_tag}: {first.get('numRecordings')} recordings, {pages} pages.")
        for page in range(1, pages + 1):
            payload = first if page == 1 else fetch_recordings(query, key=key, page=page, per_page=500)
            for rec in payload.get("recordings", []):
                sci = f"{rec.get('gen') or ''} {rec.get('sp') or ''}".strip().lower()
                if not sci:
                    continue
                index.setdefault(sci, []).append(rec)
            time.sleep(0.15)

    cache_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def apply_xeno(
    rows: list[dict[str, Any]],
    by_scientific: dict[str, Species],
    xeno_index: dict[str, list[dict[str, Any]]],
    source: str,
    scope: str,
) -> None:
    row_by_species_id = {row["species_id"]: row for row in rows}
    for sci, records in xeno_index.items():
        species = by_scientific.get(sci)
        if not species:
            continue
        row = row_by_species_id[species.species_id]
        best = choose_xeno_record(records)
        current_rank = tier_rank(row["coverage_tier"])
        tier = "strict_safe_ab" if best.get("q") in ("A", "B") else "strict_safe_any_quality"
        if scope == "global" and current_rank <= tier_rank(tier):
            continue
        set_covered(
            row,
            tier=tier,
            source=source,
            source_scope=scope,
            source_recording_id=f"XC{best.get('id', '')}",
            source_url=normalize_url(best.get("url")) or f"https://xeno-canto.org/{best.get('id')}",
            audio_url=normalize_url(best.get("file")) or "",
            license_url=normalize_url(best.get("lic")) or "",
            license_name=license_name_from_url(normalize_url(best.get("lic"))) or "Unknown license",
            quality=best.get("q") or "",
            recordist=best.get("rec") or "",
            sound_type=best.get("type") or "",
            manual_qc_required="no",
            confidence="high",
            notes="Exact scientific-name match from Xeno-canto with commercial-safe Creative Commons license.",
            candidate_count=len(records),
        )


def choose_xeno_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    def key(rec: dict[str, Any]) -> tuple[int, int, int, int]:
        quality = rec.get("q") or "Z"
        quality_rank = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(quality, 5)
        sound_type = (rec.get("type") or "").lower()
        type_rank = 0 if "song" in sound_type else 1 if "call" in sound_type else 2
        license_url = (rec.get("lic") or "").lower()
        license_rank = 0 if "publicdomain/zero" in license_url else 1 if "/by/" in license_url else 2
        length = parse_length_seconds(rec.get("length"))
        length_rank = 0 if 8 <= length <= 180 else 1
        return quality_rank, type_rank, license_rank, length_rank

    return sorted(records, key=key)[0]


def apply_nps(rows: list[dict[str, Any]]) -> None:
    nps_names = {
        "Alder Flycatcher": "https://www.nps.gov/subjects/sound/gallery.htm",
        "American Coot": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "American Dipper": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "American Robin": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Anhinga": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Bald Eagle": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Black-billed Magpie": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Canada Goose": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Clark's Nutcracker": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Common Loon": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Common Poorwill": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Common Raven": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Common Yellowthroat": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Hermit Thrush": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Killdeer": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Lazuli Bunting": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Mountain Bluebird": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Northern Flicker": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Olive-sided Flycatcher": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Osprey": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Red-breasted Nuthatch": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Red-winged Blackbird": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Ruffed Grouse": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Sandhill Crane": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Savannah Sparrow": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Spotted Owl": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Steller's Jay": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Townsend's Solitaire": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Ua'u (Hawaiian Petrel)": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Warbling Vireo": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Western Gull": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Western Meadowlark": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "White-crowned Sparrow": "https://www.nps.gov/subjects/sound/gallery.htm",
        "Wilson's Snipe": "https://www.nps.gov/yell/learn/photosmultimedia/soundlibrary.htm",
        "Yellow-rumped Warbler": "https://www.nps.gov/subjects/sound/gallery.htm",
    }
    rows_by_common = {normalize_common(row["common_name"]): row for row in rows}
    for common_name, url in nps_names.items():
        row = rows_by_common.get(normalize_common(common_name))
        if not row or tier_rank(row["coverage_tier"]) <= tier_rank("strict_safe_public_domain"):
            continue
        set_covered(
            row,
            tier="strict_safe_public_domain",
            source="National Park Service",
            source_scope="official public-domain page",
            source_recording_id="",
            source_url=url,
            audio_url="",
            license_url="https://www.nps.gov/subjects/sound/gallery.htm",
            license_name="Public domain / NPS credit requested",
            quality="official",
            recordist="National Park Service",
            sound_type="bird sound",
            manual_qc_required="no",
            confidence="high",
            notes="Official NPS public-domain sound listing; exact/common-name normalized match.",
            candidate_count=1,
        )


def map_commons(rows: list[dict[str, Any]], cache_dir: Path, polite_delay: float) -> None:
    for index, row in enumerate(rows, start=1):
        if row["covered"] == "yes":
            continue
        cache_path = cache_dir / "commons" / f"{row['species_id']:05d}.json"
        payload = load_or_fetch(cache_path, lambda: fetch_commons(row["scientific_name"]))
        candidate = choose_commons_candidate(payload, row["scientific_name"])
        if candidate:
            meta = candidate["imageinfo"][0]["extmetadata"]
            set_covered(
                row,
                tier="strict_safe_commons_exact",
                source="Wikimedia Commons",
                source_scope="exact scientific-name audio search",
                source_recording_id=str(candidate.get("pageid") or ""),
                source_url=candidate["imageinfo"][0].get("descriptionurl", ""),
                audio_url=candidate["imageinfo"][0].get("url", ""),
                license_url=metadata_value(meta, "LicenseUrl"),
                license_name=metadata_value(meta, "LicenseShortName") or metadata_value(meta, "UsageTerms"),
                quality="metadata exact",
                recordist=strip_html(metadata_value(meta, "Artist")),
                sound_type="bird sound",
                manual_qc_required="no",
                confidence="medium-high",
                notes="Commons audio result with exact scientific-name match and commercial-safe license metadata.",
                candidate_count=len((payload.get("query") or {}).get("pages") or []),
            )
        if index % 100 == 0:
            print(f"Commons checked {index}/{len(rows)} species.")
        time.sleep(polite_delay)


def fetch_commons(scientific_name: str) -> dict[str, Any]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f'filetype:audio "{scientific_name}"',
        "gsrlimit": "10",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "formatversion": "2",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return fetch_json(url, user_agent="ChirpWiseCoverage/0.1 (founder@xyflowinnovations.com)")


def choose_commons_candidate(payload: dict[str, Any], scientific_name: str) -> dict[str, Any] | None:
    pages = (payload.get("query") or {}).get("pages") or []
    sci = scientific_name.lower()
    for page in pages:
        imageinfo = page.get("imageinfo") or []
        if not imageinfo:
            continue
        meta = imageinfo[0].get("extmetadata") or {}
        haystack = " ".join(
            [
                page.get("title") or "",
                metadata_value(meta, "ObjectName"),
                metadata_value(meta, "ImageDescription"),
                metadata_value(meta, "Categories"),
            ]
        ).lower()
        if sci not in haystack:
            continue
        license_name = f"{metadata_value(meta, 'LicenseShortName')} {metadata_value(meta, 'UsageTerms')} {metadata_value(meta, 'LicenseUrl')}"
        if is_safe_license_text(license_name):
            return page
    return None


def map_inaturalist(rows: list[dict[str, Any]], cache_dir: Path, polite_delay: float) -> None:
    for index, row in enumerate(rows, start=1):
        if row["covered"] == "yes":
            continue
        cache_path = cache_dir / "inat" / f"{row['species_id']:05d}.json"
        payload = load_or_fetch(cache_path, lambda: fetch_inaturalist(row["scientific_name"]))
        candidate = choose_inaturalist_candidate(payload, row["scientific_name"])
        if candidate:
            sound = candidate["sounds"][0]
            set_covered(
                row,
                tier="candidate_safe_research_grade",
                source="iNaturalist",
                source_scope="research-grade exact taxon sound",
                source_recording_id=f"iNat observation {candidate.get('id')} / sound {sound.get('id')}",
                source_url=candidate.get("uri") or f"https://www.inaturalist.org/observations/{candidate.get('id')}",
                audio_url=sound.get("file_url") or "",
                license_url=inat_license_url(sound.get("license_code") or ""),
                license_name=(sound.get("license_code") or "").upper(),
                quality="research-grade",
                recordist=sound.get("attribution") or candidate.get("user", {}).get("login") or "",
                sound_type=sound.get("subtype") or "bird sound",
                manual_qc_required="yes",
                confidence="candidate",
                notes="License-safe iNaturalist research-grade observation with exact taxon match; listen before shipping.",
                candidate_count=int(payload.get("total_results") or 0),
            )
        if index % 100 == 0:
            print(f"iNaturalist checked {index}/{len(rows)} species.")
        time.sleep(polite_delay)


def fetch_inaturalist(scientific_name: str) -> dict[str, Any]:
    params = {
        "taxon_name": scientific_name,
        "sounds": "true",
        "quality_grade": "research",
        "sound_license": INAT_SAFE_LICENSES,
        "per_page": "10",
        "order_by": "created_at",
        "order": "desc",
    }
    url = "https://api.inaturalist.org/v1/observations?" + urllib.parse.urlencode(params)
    return fetch_json(url, user_agent="ChirpWiseCoverage/0.1")


def choose_inaturalist_candidate(payload: dict[str, Any], scientific_name: str) -> dict[str, Any] | None:
    sci = scientific_name.lower()
    for observation in payload.get("results") or []:
        taxon = observation.get("taxon") or {}
        if (taxon.get("name") or "").lower() != sci:
            continue
        sounds = [
            sound
            for sound in observation.get("sounds") or []
            if is_safe_inat_license(sound.get("license_code") or "") and sound.get("file_url")
        ]
        if sounds:
            observation = dict(observation)
            observation["sounds"] = sounds
            return observation
    return None


def set_covered(row: dict[str, Any], **values: Any) -> None:
    row["covered"] = "yes"
    row["coverage_tier"] = values["tier"]
    row["primary_source"] = values["source"]
    row["source_scope"] = values["source_scope"]
    row["source_recording_id"] = values["source_recording_id"]
    row["source_url"] = values["source_url"]
    row["audio_url"] = values["audio_url"]
    row["license_name"] = values["license_name"]
    row["license_url"] = values["license_url"]
    row["quality"] = values["quality"]
    row["recordist"] = values["recordist"]
    row["sound_type"] = values["sound_type"]
    row["commercial_allowed"] = "yes"
    row["derivatives_allowed"] = "yes"
    row["requires_share_alike"] = "yes" if is_share_alike(values["license_name"], values["license_url"]) else "no"
    row["manual_qc_required"] = values["manual_qc_required"]
    row["confidence"] = values["confidence"]
    row["notes"] = values["notes"]
    row["candidate_count"] = values["candidate_count"]


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    covered = [row for row in rows if row["covered"] == "yes"]
    strict = [row for row in covered if row["manual_qc_required"] == "no"]
    candidates = [row for row in covered if row["manual_qc_required"] == "yes"]
    by_source = Counter(row["primary_source"] or "missing" for row in rows)
    by_tier = Counter(row["coverage_tier"] for row in rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_species": total,
        "strict_safe_species": len(strict),
        "strict_safe_percent": round(len(strict) / total * 100, 2),
        "safe_with_manual_qc_species": len(covered),
        "safe_with_manual_qc_percent": round(len(covered) / total * 100, 2),
        "manual_qc_candidate_species": len(candidates),
        "missing_species": total - len(covered),
        "missing_percent": round((total - len(covered)) / total * 100, 2),
        "by_source": dict(by_source),
        "by_tier": dict(by_tier),
    }


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    csv_path = out_dir / "commercial-source-coverage.csv"
    json_path = out_dir / "commercial-source-coverage.json"
    md_path = out_dir / "commercial-source-coverage.md"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps({"summary": summary, "species": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown_report(summary), encoding="utf-8")


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# ChirpWise Commercial Source Coverage",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "Scope: current North America/ABA taxonomy table in `data/app/birdtrainer.sqlite3`.",
        "",
        "Rule: count only no-email/no-new-license sources whose metadata says commercial use and derivatives are allowed. Xeno-canto, NPS, and Commons exact metadata matches are treated as strict candidates. iNaturalist research-grade exact taxon matches are counted separately because audio should still be manually listened to before shipping.",
        "",
        "## Summary",
        "",
        f"- Total species: {summary['total_species']}",
        f"- Strict no-email commercial-safe species: {summary['strict_safe_species']} ({summary['strict_safe_percent']}%)",
        f"- Species covered if manual-QC iNaturalist candidates are accepted: {summary['safe_with_manual_qc_species']} ({summary['safe_with_manual_qc_percent']}%)",
        f"- Manual-QC candidate species: {summary['manual_qc_candidate_species']}",
        f"- Still missing after all mapped no-email sources: {summary['missing_species']} ({summary['missing_percent']}%)",
        "",
        "## By Source",
        "",
        "| Source | Species |",
        "| --- | ---: |",
    ]
    for source, count in sorted(summary["by_source"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {source} | {count} |")
    lines.extend(["", "## By Tier", "", "| Tier | Species |", "| --- | ---: |"])
    for tier, count in sorted(summary["by_tier"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {tier} | {count} |")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `commercial-source-coverage.csv`: row-by-row species map",
            "- `commercial-source-coverage.json`: machine-readable summary and rows",
        ]
    )
    return "\n".join(lines) + "\n"


def print_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, indent=2))


def fetch_json(url: str, *, user_agent: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def load_or_fetch(path: Path, fetcher: Any) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = fetcher()
    except Exception as exc:
        payload = {"_error": str(exc)}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def count_covered(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row["covered"] == "yes")


def tier_rank(tier: str) -> int:
    ranks = {
        "strict_safe_ab": 10,
        "strict_safe_public_domain": 11,
        "strict_safe_any_quality": 20,
        "strict_safe_commons_exact": 30,
        "candidate_safe_research_grade": 40,
        "missing": 999,
    }
    return ranks.get(tier, 999)


def is_safe_license_text(value: str) -> bool:
    upper = value.upper()
    if any(marker in upper for marker in UNSAFE_LICENSE_MARKERS):
        return False
    return any(marker in upper for marker in SAFE_LICENSE_MARKERS)


def is_share_alike(license_name: str, license_url: str) -> bool:
    return "SA" in f"{license_name} {license_url}".upper()


def is_safe_inat_license(value: str) -> bool:
    return value.lower() in {"cc0", "cc-by", "cc-by-sa"}


def inat_license_url(value: str) -> str:
    code = value.lower()
    if code == "cc0":
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    if code == "cc-by":
        return "https://creativecommons.org/licenses/by/4.0/"
    if code == "cc-by-sa":
        return "https://creativecommons.org/licenses/by-sa/4.0/"
    return ""


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return f"https:{value}"
    return value


def normalize_common(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower().replace("&", "and"))


def metadata_value(meta: dict[str, Any], key: str) -> str:
    value = meta.get(key) or {}
    return str(value.get("value") or "")


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


def parse_length_seconds(value: str | None) -> int:
    if not value:
        return 0
    parts = [int(part) for part in value.split(":") if part.isdigit()]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0


if __name__ == "__main__":
    main()
