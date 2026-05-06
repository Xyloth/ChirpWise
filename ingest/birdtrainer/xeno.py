from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .license_policy import build_attribution, evaluate_license


XENO_API_URL = "https://xeno-canto.org/api/3/recordings"


@dataclass(frozen=True)
class XenoQueryOptions:
    countries: tuple[str, ...] = ("United States", "Canada")
    qualities: tuple[str, ...] = ("A", "B")
    sound_types: tuple[str, ...] = ("song", "call")
    max_pages: int = 2
    per_page: int = 100
    polite_delay: float = 1.0
    allow_noncommercial: bool = True
    commercial_build: bool = False
    api_key: str | None = None


def api_key_from_env_or_option(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        import os

        key = os.environ.get("XENO_CANTO_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Xeno-canto API v3 requires an API key. Set XENO_CANTO_API_KEY or pass --key. "
            "Get it from https://xeno-canto.org/account after registering and verifying your email."
        )
    return key


def request_headers() -> dict[str, str]:
    return {"User-Agent": "BirdSoundTrainer/0.2 local data builder"}


def build_query(scientific_name: str, countries: tuple[str, ...], qualities: tuple[str, ...], sound_type: str | None) -> str:
    parts = [f'sp:"{scientific_name}"', "grp:birds"]
    if countries:
        if len(countries) == 1:
            parts.append(f'cnt:"{countries[0]}"')
        else:
            parts.append("(" + " OR ".join(f'cnt:"{country}"' for country in countries) + ")")
    if qualities:
        if len(qualities) == 1:
            parts.append(f"q:{qualities[0]}")
        else:
            parts.append("(" + " OR ".join(f"q:{quality}" for quality in qualities) + ")")
    if sound_type:
        parts.append(f"type:{quote_tag_value(sound_type)}")
    parts.append('len:"<180"')
    return " ".join(parts)


def quote_tag_value(value: str) -> str:
    if " " in value or any(char in value for char in '<>=:"'):
        return f'"{value}"'
    return value


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return f"https:{value}"
    return value


def license_name_from_url(url: str | None) -> str | None:
    if not url:
        return None
    text = url.lower().strip("/")
    if "creativecommons.org/publicdomain/zero" in text:
        return "CC0-1.0"
    marker = "creativecommons.org/licenses/"
    if marker not in text:
        return url
    tail = text.split(marker, 1)[1].strip("/")
    parts = tail.split("/")
    code = parts[0].upper() if parts else "UNKNOWN"
    version = parts[1] if len(parts) > 1 else ""
    return f"CC {code} {version}".strip()


def fetch_recordings(query: str, *, key: str, page: int = 1, per_page: int = 100, timeout: int = 45) -> dict[str, Any]:
    params = urllib.parse.urlencode({"query": query, "key": key, "page": page, "per_page": per_page})
    request = urllib.request.Request(f"{XENO_API_URL}?{params}", headers=request_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Xeno-canto API error {exc.code}: {body[:500]}") from exc


def query_species(
    conn: sqlite3.Connection,
    *,
    metadata_dir: Path,
    limit_species: int | None = None,
    options: XenoQueryOptions = XenoQueryOptions(),
) -> int:
    key = api_key_from_env_or_option(options.api_key)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    species_rows = conn.execute(
        "SELECT id, common_name, scientific_name FROM species ORDER BY common_name"
    ).fetchall()
    if limit_species:
        species_rows = species_rows[:limit_species]

    written = 0
    for species in species_rows:
        species_payload: dict[str, Any] = {
            "species_id": species["id"],
            "common_name": species["common_name"],
            "scientific_name": species["scientific_name"],
            "api": "xeno-canto v3",
            "queries": [],
            "recordings": [],
        }
        seen_ids: set[str] = set()
        for sound_type in options.sound_types:
            query = build_query(species["scientific_name"], options.countries, options.qualities, sound_type)
            for page in range(1, options.max_pages + 1):
                payload = fetch_recordings(query, key=key, page=page, per_page=options.per_page)
                species_payload["queries"].append(
                    {"query": query, "page": page, "numRecordings": payload.get("numRecordings")}
                )
                for recording in payload.get("recordings", []):
                    recording_id = str(recording.get("id") or recording.get("nr") or "")
                    if not recording_id or recording_id in seen_ids:
                        continue
                    if recording.get("_meta", {}).get("redacted_fields", {}).get("file"):
                        continue
                    license_url = normalize_url(recording.get("lic") or recording.get("licUrl") or recording.get("licenseUrl"))
                    license_name = license_name_from_url(license_url) or recording.get("license")
                    decision = evaluate_license(
                        license_name or license_url,
                        license_url,
                        allow_noncommercial=options.allow_noncommercial,
                        commercial_build=options.commercial_build,
                    )
                    if not decision.allowed:
                        continue
                    recording["_license_decision"] = decision.reason
                    recording["_license_name"] = license_name
                    recording["_license_url"] = license_url
                    recording["url"] = normalize_url(recording.get("url"))
                    recording["file"] = normalize_url(recording.get("file"))
                    species_payload["recordings"].append(recording)
                    seen_ids.add(recording_id)
                if int(payload.get("numPages") or 1) <= page:
                    break
                time.sleep(options.polite_delay)
            if species_payload["recordings"]:
                break
        out_path = metadata_dir / f"{species['id']:05d}_{slugify(species['common_name'])}.json"
        out_path.write_text(json.dumps(species_payload, indent=2, ensure_ascii=True), encoding="utf-8")
        written += 1
        time.sleep(options.polite_delay)
    return written


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "item"


def ingest_xeno_metadata(conn: sqlite3.Connection, metadata_dir: Path) -> int:
    count = 0
    for path in sorted(metadata_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        species_id = int(payload["species_id"])
        for rec in payload.get("recordings", []):
            recording_id = str(rec.get("id") or rec.get("nr") or "")
            if not recording_id:
                continue
            source_url = normalize_url(rec.get("url")) or f"https://xeno-canto.org/{recording_id}"
            recordist = rec.get("rec") or rec.get("recordist")
            license_url = normalize_url(rec.get("_license_url") or rec.get("lic") or rec.get("licUrl") or rec.get("licenseUrl"))
            license_name = rec.get("_license_name") or license_name_from_url(license_url) or rec.get("license")
            attribution = build_attribution(
                title=f"{payload.get('common_name')} recording",
                recordist=recordist,
                source="xeno-canto",
                source_recording_id=recording_id,
                source_url=source_url,
                license_name=license_name,
            )
            with conn:
                conn.execute(
                    """
                    INSERT INTO recordings (
                      species_id, source, source_recording_id, source_url, recordist,
                      country, location, latitude, longitude, recorded_date, sound_type,
                      quality, license_name, license_url, attribution_text,
                      length_seconds, sample_rate, usable_for_quiz, metadata_json
                    )
                    VALUES (?, 'xeno-canto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    ON CONFLICT(source, source_recording_id) DO UPDATE SET
                      species_id = excluded.species_id,
                      source_url = excluded.source_url,
                      recordist = excluded.recordist,
                      country = excluded.country,
                      location = excluded.location,
                      latitude = excluded.latitude,
                      longitude = excluded.longitude,
                      recorded_date = excluded.recorded_date,
                      sound_type = excluded.sound_type,
                      quality = excluded.quality,
                      license_name = excluded.license_name,
                      license_url = excluded.license_url,
                      attribution_text = excluded.attribution_text,
                      length_seconds = excluded.length_seconds,
                      sample_rate = excluded.sample_rate,
                      metadata_json = excluded.metadata_json
                    """,
                    (
                        species_id,
                        recording_id,
                        source_url,
                        recordist,
                        rec.get("cnt"),
                        rec.get("loc"),
                        parse_float(rec.get("lat")),
                        parse_float(rec.get("lon") or rec.get("lng")),
                        rec.get("date"),
                        rec.get("type"),
                        rec.get("q"),
                        license_name,
                        license_url,
                        attribution,
                        parse_length(rec.get("length")),
                        parse_int(rec.get("smp")),
                        json.dumps(rec, ensure_ascii=True),
                    ),
                )
                count += 1
    return count


def download_audio(conn: sqlite3.Connection, output_dir: Path, *, limit: int | None = None, api_key: str | None = None) -> int:
    key = api_key_from_env_or_option(api_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT id, source_recording_id, metadata_json
        FROM recordings
        WHERE source = 'xeno-canto'
          AND (audio_original_path IS NULL OR audio_original_path = '')
        ORDER BY id
        """
    ).fetchall()
    if limit:
        rows = rows[:limit]
    downloaded = 0
    for row in rows:
        metadata = json.loads(row["metadata_json"] or "{}")
        file_url = normalize_url(metadata.get("file") or metadata.get("download") or metadata.get("fileUrl"))
        if not file_url:
            continue
        extension = Path(urllib.parse.urlparse(file_url).path).suffix or Path(metadata.get("file-name") or "").suffix or ".mp3"
        destination = output_dir / f"xc{row['source_recording_id']}{extension}"
        separator = "&" if "?" in file_url else "?"
        request = urllib.request.Request(f"{file_url}{separator}{urllib.parse.urlencode({'key': key})}", headers=request_headers())
        with urllib.request.urlopen(request, timeout=120) as response:
            destination.write_bytes(response.read())
        with conn:
            conn.execute(
                "UPDATE recordings SET audio_original_path = ? WHERE id = ?",
                (str(destination.relative_to(output_dir.parents[2])), row["id"]),
            )
        downloaded += 1
        time.sleep(0.75)
    return downloaded


def attach_originals_as_clips(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT r.id AS recording_id, r.species_id, r.audio_original_path, r.sound_type,
               r.length_seconds, r.license_name, r.license_url, s.difficulty
        FROM recordings r
        JOIN species s ON s.id = r.species_id
        WHERE r.source = 'xeno-canto'
          AND r.audio_original_path IS NOT NULL
          AND r.audio_original_path != ''
          AND NOT EXISTS (SELECT 1 FROM clips c WHERE c.recording_id = r.id)
        ORDER BY r.quality, r.id
        """
    ).fetchall()
    inserted = 0
    with conn:
        for row in rows:
            decision = evaluate_license(row["license_name"], row["license_url"], derivative_required=False)
            if not decision.allowed:
                continue
            conn.execute(
                """
                INSERT INTO clips (
                  recording_id, species_id, clip_path, start_seconds, end_seconds,
                  clip_type, difficulty, has_background_species
                )
                VALUES (?, ?, ?, 0, ?, ?, ?, 0)
                """,
                (
                    row["recording_id"],
                    row["species_id"],
                    row["audio_original_path"],
                    row["length_seconds"],
                    row["sound_type"],
                    row["difficulty"] or 2,
                ),
            )
            conn.execute("UPDATE recordings SET usable_for_quiz = 1 WHERE id = ?", (row["recording_id"],))
            inserted += 1
    return inserted


def remove_fixture_audio(conn: sqlite3.Connection) -> int:
    before = conn.execute("SELECT COUNT(*) FROM recordings WHERE source = 'fixture'").fetchone()[0]
    with conn:
        conn.execute("DELETE FROM recordings WHERE source = 'fixture'")
    return int(before)


def parse_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def parse_length(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value)
    if ":" in text:
        parts = [float(part) for part in text.split(":")]
        total = 0.0
        for part in parts:
            total = total * 60 + part
        return total
    return parse_float(value)

