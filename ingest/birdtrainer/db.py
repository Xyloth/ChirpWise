from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS species (
  id INTEGER PRIMARY KEY,
  common_name TEXT NOT NULL,
  scientific_name TEXT NOT NULL,
  ebird_code TEXT,
  family TEXT,
  order_name TEXT,
  taxonomy_source TEXT,
  taxonomy_version TEXT,
  region_scope TEXT,
  range_notes TEXT,
  difficulty INTEGER DEFAULT 2,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scientific_name, region_scope)
);

CREATE TABLE IF NOT EXISTS recordings (
  id INTEGER PRIMARY KEY,
  species_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  source_recording_id TEXT NOT NULL,
  source_url TEXT,
  audio_original_path TEXT,
  audio_app_path TEXT,
  recordist TEXT,
  country TEXT,
  location TEXT,
  latitude REAL,
  longitude REAL,
  recorded_date TEXT,
  sound_type TEXT,
  quality TEXT,
  license_name TEXT,
  license_url TEXT,
  attribution_text TEXT,
  length_seconds REAL,
  sample_rate INTEGER,
  usable_for_quiz INTEGER DEFAULT 0,
  metadata_json TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE,
  UNIQUE(source, source_recording_id)
);

CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY,
  recording_id INTEGER NOT NULL,
  species_id INTEGER NOT NULL,
  clip_path TEXT NOT NULL,
  start_seconds REAL DEFAULT 0,
  end_seconds REAL,
  clip_type TEXT,
  difficulty INTEGER DEFAULT 2,
  has_background_species INTEGER DEFAULT 0,
  waveform_path TEXT,
  spectrogram_path TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(recording_id) REFERENCES recordings(id) ON DELETE CASCADE,
  FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS species_similarity (
  species_id INTEGER NOT NULL,
  similar_species_id INTEGER NOT NULL,
  reason TEXT,
  weight REAL DEFAULT 1,
  PRIMARY KEY(species_id, similar_species_id),
  FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE,
  FOREIGN KEY(similar_species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quiz_sessions (
  id INTEGER PRIMARY KEY,
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  ended_at TEXT,
  mode TEXT,
  region_filter TEXT,
  sound_filter TEXT,
  score INTEGER DEFAULT 0,
  total INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quiz_answers (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  clip_id INTEGER NOT NULL,
  correct_species_id INTEGER NOT NULL,
  chosen_species_id INTEGER,
  was_correct INTEGER NOT NULL,
  answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
  response_ms INTEGER,
  FOREIGN KEY(session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE,
  FOREIGN KEY(clip_id) REFERENCES clips(id) ON DELETE CASCADE,
  FOREIGN KEY(correct_species_id) REFERENCES species(id),
  FOREIGN KEY(chosen_species_id) REFERENCES species(id)
);

CREATE TABLE IF NOT EXISTS practice_sets (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS practice_set_species (
  practice_set_id INTEGER NOT NULL,
  species_id INTEGER NOT NULL,
  PRIMARY KEY(practice_set_id, species_id),
  FOREIGN KEY(practice_set_id) REFERENCES practice_sets(id) ON DELETE CASCADE,
  FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dataset_builds (
  id INTEGER PRIMARY KEY,
  built_at TEXT DEFAULT CURRENT_TIMESTAMP,
  taxonomy_source TEXT,
  taxonomy_version TEXT,
  region_scope TEXT,
  license_policy TEXT,
  species_count INTEGER,
  recording_count INTEGER,
  clip_count INTEGER,
  coverage_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_species_common ON species(common_name);
CREATE INDEX IF NOT EXISTS idx_species_family ON species(family);
CREATE INDEX IF NOT EXISTS idx_recordings_species ON recordings(species_id);
CREATE INDEX IF NOT EXISTS idx_recordings_sound ON recordings(sound_type);
CREATE INDEX IF NOT EXISTS idx_clips_species ON clips(species_id);
CREATE INDEX IF NOT EXISTS idx_answers_species ON quiz_answers(correct_species_id);
"""


def connect(db_path: Path, *, check_same_thread: bool = True) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]
