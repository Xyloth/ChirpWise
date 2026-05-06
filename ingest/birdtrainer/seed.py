from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .audio import write_fixture_wav
from .build import build_license_manifest, record_dataset_build


SEED_SPECIES = [
    ("Northern Cardinal", "Cardinalis cardinalis", "norcar", "Cardinalidae", "Passeriformes", "US+Canada", "Common in thickets, yards, and woodland edges.", 1),
    ("Rose-breasted Grosbeak", "Pheucticus ludovicianus", "rebgro", "Cardinalidae", "Passeriformes", "US+Canada", "Breeds in deciduous woods across the northern and eastern regions.", 2),
    ("American Robin", "Turdus migratorius", "amerob", "Turdidae", "Passeriformes", "US+Canada", "Widespread in towns, fields, and forests.", 1),
    ("Wood Thrush", "Hylocichla mustelina", "woothr", "Turdidae", "Passeriformes", "US+Canada", "Breeds in mature deciduous forest; rich fluting song.", 3),
    ("Swainson's Thrush", "Catharus ustulatus", "swathr", "Turdidae", "Passeriformes", "US+Canada", "Northern and western breeder with upward-spiraling song.", 3),
    ("Black-capped Chickadee", "Poecile atricapillus", "bkcchi", "Paridae", "Passeriformes", "US+Canada", "Resident in northern forests, suburbs, and feeders.", 1),
    ("Carolina Chickadee", "Poecile carolinensis", "carchi", "Paridae", "Passeriformes", "US+Canada", "Resident of southeastern woods and neighborhoods.", 2),
    ("Red-eyed Vireo", "Vireo olivaceus", "reevir1", "Vireonidae", "Passeriformes", "US+Canada", "Canopy singer in eastern deciduous forests.", 2),
    ("Warbling Vireo", "Vireo gilvus", "warvir", "Vireonidae", "Passeriformes", "US+Canada", "Riparian and shade-tree vireo with flowing song.", 3),
    ("Song Sparrow", "Melospiza melodia", "sonspa", "Passerellidae", "Passeriformes", "US+Canada", "Widespread brushy habitat sparrow with variable songs.", 2),
    ("Lincoln's Sparrow", "Melospiza lincolnii", "linspa", "Passerellidae", "Passeriformes", "US+Canada", "Secretive wet-meadow sparrow with fine bubbling song.", 4),
    ("Killdeer", "Charadrius vociferus", "killde", "Charadriidae", "Charadriiformes", "US+Canada", "Open-ground shorebird often heard giving piercing calls.", 1),
]


def create_seed_dataset(conn: sqlite3.Connection, root: Path) -> None:
    clips_dir = root / "data" / "processed" / "clips"
    waveform_dir = root / "data" / "processed" / "waveforms"
    clips_dir.mkdir(parents=True, exist_ok=True)
    waveform_dir.mkdir(parents=True, exist_ok=True)

    with conn:
        conn.execute("DELETE FROM quiz_answers")
        conn.execute("DELETE FROM quiz_sessions")
        conn.execute("DELETE FROM species_similarity")
        conn.execute("DELETE FROM clips")
        conn.execute("DELETE FROM recordings")
        conn.execute("DELETE FROM species")

    species_ids: dict[str, int] = {}
    for index, row in enumerate(SEED_SPECIES, start=1):
        common, scientific, code, family, order_name, scope, notes, difficulty = row
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO species (
                  common_name, scientific_name, ebird_code, family, order_name,
                  taxonomy_source, taxonomy_version, region_scope, range_notes, difficulty
                )
                VALUES (?, ?, ?, ?, ?, 'fixture', 'demo-2026.05', ?, ?, ?)
                """,
                (common, scientific, code, family, order_name, scope, notes, difficulty),
            )
            species_id = int(cursor.lastrowid)
            species_ids[common] = species_id

        for clip_index, sound_type in enumerate(["song", "call"], start=1):
            file_name = f"{code}_{sound_type}.wav"
            clip_path = clips_dir / file_name
            write_fixture_wav(clip_path, pattern_seed=index * 7 + clip_index)
            waveform_path = waveform_dir / f"{code}_{sound_type}.json"
            waveform_path.write_text(
                json.dumps({"peaks": fixture_peaks(index, clip_index), "kind": "generated"}),
                encoding="utf-8",
            )
            source_recording_id = f"fixture-{code}-{sound_type}"
            attribution = (
                f"Generated fixture audio for {common}; source {source_recording_id}; "
                "licensed CC0-1.0; not a real bird recording"
            )
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO recordings (
                      species_id, source, source_recording_id, source_url, audio_original_path,
                      audio_app_path, recordist, country, location, recorded_date, sound_type,
                      quality, license_name, license_url, attribution_text, length_seconds,
                      sample_rate, usable_for_quiz, metadata_json
                    )
                    VALUES (?, 'fixture', ?, 'docs/fixture-audio.md', ?, ?, 'Bird Sound Trainer',
                            'United States', 'Generated local fixture', '2026-05-06', ?,
                            'A', 'CC0-1.0', 'https://creativecommons.org/publicdomain/zero/1.0/',
                            ?, 7.5, 22050, 1, ?)
                    """,
                    (
                        species_id,
                        source_recording_id,
                        str(clip_path.relative_to(root)),
                        str(clip_path.relative_to(root)),
                        sound_type,
                        attribution,
                        json.dumps({"fixture": True, "warning": "Generated audio, not a real field recording"}),
                    ),
                )
                recording_id = int(cursor.lastrowid)
                conn.execute(
                    """
                    INSERT INTO clips (
                      recording_id, species_id, clip_path, start_seconds, end_seconds,
                      clip_type, difficulty, has_background_species, waveform_path
                    )
                    VALUES (?, ?, ?, 0, 7.5, ?, ?, 0, ?)
                    """,
                    (
                        recording_id,
                        species_id,
                        str(clip_path.relative_to(root)),
                        sound_type,
                        difficulty,
                        str(waveform_path.relative_to(root)),
                    ),
                )

    add_similarity(conn, species_ids)
    record_dataset_build(
        conn,
        taxonomy_source="fixture",
        taxonomy_version="demo-2026.05",
        region_scope="US+Canada",
        license_policy="fixture CC0; real builds enforce per-recording license metadata",
    )
    build_license_manifest(conn, root / "data" / "manifests" / "license_manifest.json")


def add_similarity(conn: sqlite3.Connection, species_ids: dict[str, int]) -> None:
    pairs = [
        ("Northern Cardinal", "Rose-breasted Grosbeak", "same family: rich whistled song", 0.72),
        ("American Robin", "Wood Thrush", "same family: thrush song comparison", 0.68),
        ("Wood Thrush", "Swainson's Thrush", "same family: flute-like thrush songs", 0.92),
        ("Black-capped Chickadee", "Carolina Chickadee", "sister taxa with overlapping vocal patterns", 0.98),
        ("Red-eyed Vireo", "Warbling Vireo", "same family: repetitive vireo phrases", 0.84),
        ("Song Sparrow", "Lincoln's Sparrow", "same genus: sparrow trills and phrases", 0.9),
    ]
    with conn:
        for left, right, reason, weight in pairs:
            a = species_ids[left]
            b = species_ids[right]
            conn.execute(
                "INSERT OR REPLACE INTO species_similarity (species_id, similar_species_id, reason, weight) VALUES (?, ?, ?, ?)",
                (a, b, reason, weight),
            )
            conn.execute(
                "INSERT OR REPLACE INTO species_similarity (species_id, similar_species_id, reason, weight) VALUES (?, ?, ?, ?)",
                (b, a, reason, weight),
            )


def fixture_peaks(seed: int, variant: int) -> list[float]:
    peaks = []
    for i in range(96):
        value = abs(((i * (seed + 3) + variant * 11) % 37) / 37)
        shaped = 0.15 + 0.85 * value
        if i % (5 + variant) == 0:
            shaped = min(1.0, shaped + 0.3)
        peaks.append(round(shaped, 3))
    return peaks

