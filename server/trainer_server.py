from __future__ import annotations

import json
import mimetypes
import random
import sqlite3
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize, row_to_dict, rows_to_dicts
from ingest.birdtrainer.seed import create_seed_dataset
from server.regions import region_options, region_recording_condition


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    return "/media/" + path.replace("\\", "/")


class TrainerRepository:
    def __init__(self, paths: ProjectPaths):
        self.paths = paths
        self.paths.ensure()
        self.lock = threading.RLock()
        self.conn = connect(paths.db_path, check_same_thread=False)
        initialize(self.conn)
        species_count = self.conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
        if species_count == 0:
            create_seed_dataset(self.conn, paths.root)

    def summary(self) -> dict[str, Any]:
        latest_build = row_to_dict(
            self.conn.execute(
                "SELECT * FROM dataset_builds ORDER BY built_at DESC, id DESC LIMIT 1"
            ).fetchone()
        )
        clip_count = self.conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
        species_count = self.conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
        recording_count = self.conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        answered = self.conn.execute("SELECT COUNT(*) FROM quiz_answers").fetchone()[0]
        correct = self.conn.execute("SELECT COUNT(*) FROM quiz_answers WHERE was_correct = 1").fetchone()[0]
        families = rows_to_dicts(
            self.conn.execute(
                """
                SELECT COALESCE(family, 'Unknown') AS family, COUNT(*) AS species
                FROM species
                GROUP BY COALESCE(family, 'Unknown')
                ORDER BY species DESC, family
                """
            ).fetchall()
        )
        return {
            "species": species_count,
            "recordings": recording_count,
            "clips": clip_count,
            "answered": answered,
            "accuracy": round(correct / answered, 3) if answered else None,
            "families": families,
            "latest_build": latest_build,
        }

    def species(self, params: dict[str, list[str]]) -> dict[str, Any]:
        search = first(params, "search")
        family = first(params, "family")
        sound = first(params, "sound")
        region = first(params, "region")
        order_by = first(params, "order") or "common"
        args: list[Any] = []
        where = ["1 = 1"]
        if search:
            where.append("(s.common_name LIKE ? OR s.scientific_name LIKE ? OR s.ebird_code LIKE ?)")
            like = f"%{search}%"
            args.extend([like, like, like])
        if family:
            where.append("s.family = ?")
            args.append(family)
        if sound:
            where.append("EXISTS (SELECT 1 FROM clips cx WHERE cx.species_id = s.id AND lower(cx.clip_type) LIKE ?)")
            args.append(f"%{sound.lower()}%")
        if region and region != "all":
            where.append(
                f"""
                EXISTS (
                  SELECT 1
                  FROM species_region_membership srm
                  WHERE srm.species_id = s.id AND srm.region_id = ?
                )
                """
            )
            args.append(region)
        order_sql = {
            "common": "s.common_name",
            "family": "s.family, s.common_name",
            "clips": "clip_count DESC, s.common_name",
            "difficulty": "s.difficulty DESC, s.common_name",
        }.get(order_by, "s.common_name")
        rows = self.conn.execute(
            f"""
            SELECT
              s.*,
              COUNT(DISTINCT r.id) AS recording_count,
              COUNT(DISTINCT c.id) AS clip_count,
              SUM(CASE WHEN qa.was_correct = 1 THEN 1 ELSE 0 END) AS correct_answers,
              COUNT(qa.id) AS total_answers
            FROM species s
            LEFT JOIN recordings r ON r.species_id = s.id
            LEFT JOIN clips c ON c.species_id = s.id
            LEFT JOIN quiz_answers qa ON qa.correct_species_id = s.id
            WHERE {' AND '.join(where)}
            GROUP BY s.id
            ORDER BY {order_sql}
            """,
            args,
        ).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            total = item.pop("total_answers") or 0
            correct = item.pop("correct_answers") or 0
            item["accuracy"] = round(correct / total, 3) if total else None
            data.append(item)
        return {"species": data, "count": len(data)}

    def species_detail(self, species_id: int) -> dict[str, Any]:
        species = row_to_dict(self.conn.execute("SELECT * FROM species WHERE id = ?", (species_id,)).fetchone())
        if not species:
            raise ApiError(HTTPStatus.NOT_FOUND, "species not found")
        recordings = rows_to_dicts(
            self.conn.execute(
                """
                SELECT * FROM recordings
                WHERE species_id = ?
                ORDER BY quality, sound_type, recorded_date DESC
                """,
                (species_id,),
            ).fetchall()
        )
        clips = []
        for row in self.conn.execute(
            """
            SELECT c.*, r.recordist, r.location, r.country, r.quality, r.license_name, r.attribution_text
            FROM clips c
            JOIN recordings r ON r.id = c.recording_id
            WHERE c.species_id = ?
            ORDER BY c.clip_type, c.id
            """,
            (species_id,),
        ).fetchall():
            item = dict(row)
            item["audio_url"] = media_url(item["clip_path"])
            item["waveform_url"] = media_url(item.get("waveform_path"))
            clips.append(item)
        similar = rows_to_dicts(
            self.conn.execute(
                """
                SELECT s.id, s.common_name, s.scientific_name, s.family, ss.reason, ss.weight
                FROM species_similarity ss
                JOIN species s ON s.id = ss.similar_species_id
                WHERE ss.species_id = ?
                ORDER BY ss.weight DESC, s.common_name
                """,
                (species_id,),
            ).fetchall()
        )
        progress = row_to_dict(
            self.conn.execute(
                """
                SELECT COUNT(*) AS attempts, SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) AS correct
                FROM quiz_answers
                WHERE correct_species_id = ?
                """,
                (species_id,),
            ).fetchone()
        )
        attempts = progress["attempts"] or 0
        correct = progress["correct"] or 0
        progress["accuracy"] = round(correct / attempts, 3) if attempts else None
        return {"species": species, "recordings": recordings, "clips": clips, "similar": similar, "progress": progress}

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO quiz_sessions (mode, region_filter, sound_filter) VALUES (?, ?, ?)",
                (payload.get("mode") or "3-choice", payload.get("region"), payload.get("sound")),
            )
        return {"session_id": int(cursor.lastrowid)}

    def next_question(self, params: dict[str, list[str]]) -> dict[str, Any]:
        session_id = parse_int(first(params, "session_id"))
        choices = max(3, min(8, parse_int(first(params, "choices")) or 3))
        family = first(params, "family")
        sound = first(params, "sound")
        region = first(params, "region")
        weak = (first(params, "weak") or "").lower() in {"1", "true", "yes"}
        if not session_id:
            session_id = self.create_session({"mode": f"{choices}-choice", "sound": sound, "region": region})["session_id"]

        clip = self._select_clip(family=family, sound=sound, region=region, weak=weak)
        if not clip:
            raise ApiError(HTTPStatus.NOT_FOUND, "no clips match quiz filters")
        options = self._distractors(int(clip["species_id"]), choices)
        random.shuffle(options)
        return {
            "session_id": session_id,
            "clip_id": clip["id"],
            "audio_url": media_url(clip["clip_path"]),
            "clip_type": clip["clip_type"],
            "difficulty": clip["difficulty"],
            "options": options,
        }

    def answer_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = int(payload.get("session_id") or 0)
        clip_id = int(payload.get("clip_id") or 0)
        chosen_species_id = payload.get("chosen_species_id")
        if not session_id or not clip_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "session_id and clip_id are required")
        clip = self.conn.execute(
            """
            SELECT c.*, s.common_name, s.scientific_name, s.family
            FROM clips c
            JOIN species s ON s.id = c.species_id
            WHERE c.id = ?
            """,
            (clip_id,),
        ).fetchone()
        if not clip:
            raise ApiError(HTTPStatus.NOT_FOUND, "clip not found")
        correct_species_id = int(clip["species_id"])
        chosen = int(chosen_species_id) if chosen_species_id else None
        was_correct = chosen == correct_species_id
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO quiz_answers (
                  session_id, clip_id, correct_species_id, chosen_species_id, was_correct, response_ms
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, clip_id, correct_species_id, chosen, 1 if was_correct else 0, payload.get("response_ms")),
            )
            self.conn.execute(
                """
                UPDATE quiz_sessions
                SET total = total + 1, score = score + ?
                WHERE id = ?
                """,
                (1 if was_correct else 0, session_id),
            )
        detail = self.species_detail(correct_species_id)
        chosen_species = None
        if chosen:
            chosen_species = row_to_dict(self.conn.execute("SELECT id, common_name, scientific_name, family FROM species WHERE id = ?", (chosen,)).fetchone())
        return {
            "was_correct": was_correct,
            "correct_species": {
                "id": correct_species_id,
                "common_name": clip["common_name"],
                "scientific_name": clip["scientific_name"],
                "family": clip["family"],
            },
            "chosen_species": chosen_species,
            "clip": {
                "id": clip["id"],
                "clip_type": clip["clip_type"],
                "audio_url": media_url(clip["clip_path"]),
            },
            "recording": detail["recordings"][0] if detail["recordings"] else None,
            "similar": detail["similar"][:4],
        }

    def progress(self) -> dict[str, Any]:
        species_rows = rows_to_dicts(
            self.conn.execute(
                """
                SELECT
                  s.id, s.common_name, s.scientific_name, s.family,
                  COUNT(qa.id) AS attempts,
                  SUM(CASE WHEN qa.was_correct = 1 THEN 1 ELSE 0 END) AS correct,
                  MAX(qa.answered_at) AS last_answered
                FROM species s
                LEFT JOIN quiz_answers qa ON qa.correct_species_id = s.id
                GROUP BY s.id
                HAVING attempts > 0
                ORDER BY (1.0 * correct / attempts) ASC, attempts DESC, s.common_name
                """
            ).fetchall()
        )
        for row in species_rows:
            attempts = row["attempts"] or 0
            correct = row["correct"] or 0
            row["accuracy"] = round(correct / attempts, 3) if attempts else None

        family_rows = rows_to_dicts(
            self.conn.execute(
                """
                SELECT
                  COALESCE(s.family, 'Unknown') AS family,
                  COUNT(qa.id) AS attempts,
                  SUM(CASE WHEN qa.was_correct = 1 THEN 1 ELSE 0 END) AS correct
                FROM quiz_answers qa
                JOIN species s ON s.id = qa.correct_species_id
                GROUP BY COALESCE(s.family, 'Unknown')
                ORDER BY attempts DESC, family
                """
            ).fetchall()
        )
        for row in family_rows:
            attempts = row["attempts"] or 0
            correct = row["correct"] or 0
            row["accuracy"] = round(correct / attempts, 3) if attempts else None
        sessions = rows_to_dicts(
            self.conn.execute(
                "SELECT * FROM quiz_sessions ORDER BY started_at DESC, id DESC LIMIT 12"
            ).fetchall()
        )
        return {"species": species_rows, "families": family_rows, "sessions": sessions}

    def coverage(self, params: dict[str, list[str]] | None = None) -> dict[str, Any]:
        region = first(params or {}, "region")
        clip_region_join = ""
        clip_region_where = ""
        region_args: list[Any] = []
        if region and region != "all":
            clip_region_where = " AND EXISTS (SELECT 1 FROM species_region_membership srm WHERE srm.species_id = s.id AND srm.region_id = ?)"
            region_args.append(region)
        rows = rows_to_dicts(
            self.conn.execute(
                f"""
                SELECT
                  s.id, s.common_name, s.scientific_name, s.family, s.region_scope,
                  COUNT(DISTINCT r.id) AS recordings,
                  COUNT(DISTINCT c.id) AS clips,
                  SUM(CASE WHEN lower(COALESCE(c.clip_type, '')) LIKE '%song%' THEN 1 ELSE 0 END) AS song_clips,
                  SUM(CASE WHEN lower(COALESCE(c.clip_type, '')) LIKE '%call%' THEN 1 ELSE 0 END) AS call_clips
                FROM species s
                LEFT JOIN recordings r ON r.species_id = s.id
                LEFT JOIN clips c ON c.species_id = s.id
                  AND c.recording_id = r.id
                  {clip_region_where}
                GROUP BY s.id
                ORDER BY clips ASC, recordings ASC, s.common_name
                """,
                region_args,
            ).fetchall()
        )
        complete = sum(1 for row in rows if row["clips"] >= 2)
        partial = sum(1 for row in rows if 0 < row["clips"] < 2)
        missing = sum(1 for row in rows if row["clips"] == 0)
        return {"species": rows, "complete": complete, "partial": partial, "missing": missing}

    def attributions(self) -> dict[str, Any]:
        rows = rows_to_dicts(
            self.conn.execute(
                """
                SELECT
                  s.common_name, s.scientific_name, r.source, r.source_recording_id,
                  r.source_url, r.recordist, r.country, r.location, r.license_name,
                  r.license_url, r.attribution_text
                FROM recordings r
                JOIN species s ON s.id = r.species_id
                ORDER BY s.common_name, r.source_recording_id
                """
            ).fetchall()
        )
        return {"recordings": rows, "count": len(rows)}

    def filters(self) -> dict[str, Any]:
        families = [row["family"] for row in self.conn.execute("SELECT DISTINCT family FROM species WHERE family IS NOT NULL ORDER BY family").fetchall()]
        sounds = [row["clip_type"] for row in self.conn.execute("SELECT DISTINCT clip_type FROM clips WHERE clip_type IS NOT NULL ORDER BY clip_type").fetchall()]
        taxonomy_regions = [row["region_scope"] for row in self.conn.execute("SELECT DISTINCT region_scope FROM species WHERE region_scope IS NOT NULL ORDER BY region_scope").fetchall()]
        return {"families": families, "sounds": sounds, "taxonomy_regions": taxonomy_regions, "regions": region_options()}

    def reset_progress(self) -> dict[str, Any]:
        with self.conn:
            self.conn.execute("DELETE FROM quiz_answers")
            self.conn.execute("DELETE FROM quiz_sessions")
        return {"ok": True}

    def _select_clip(self, *, family: str | None, sound: str | None, region: str | None, weak: bool) -> sqlite3.Row | None:
        args: list[Any] = []
        where = ["1 = 1"]
        if family:
            where.append("s.family = ?")
            args.append(family)
        if sound:
            where.append("lower(c.clip_type) LIKE ?")
            args.append(f"%{sound.lower()}%")
        if region and region != "all":
            where.append("EXISTS (SELECT 1 FROM species_region_membership srm WHERE srm.species_id = s.id AND srm.region_id = ?)")
            args.append(region)
        order = "RANDOM()"
        if weak:
            order = """
            CASE WHEN stats.attempts IS NULL THEN 0 ELSE 1 END,
            COALESCE(1.0 * stats.correct / NULLIF(stats.attempts, 0), 0.5) ASC,
            RANDOM()
            """
        return self.conn.execute(
            f"""
            SELECT c.*, s.family
            FROM clips c
            JOIN species s ON s.id = c.species_id
            JOIN recordings r ON r.id = c.recording_id
            LEFT JOIN (
              SELECT correct_species_id, COUNT(*) AS attempts, SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) AS correct
              FROM quiz_answers
              GROUP BY correct_species_id
            ) stats ON stats.correct_species_id = s.id
            WHERE {' AND '.join(where)}
            ORDER BY {order}
            LIMIT 1
            """,
            args,
        ).fetchone()

    def _distractors(self, species_id: int, choices: int) -> list[dict[str, Any]]:
        correct = row_to_dict(
            self.conn.execute(
                "SELECT id, common_name, scientific_name, family FROM species WHERE id = ?",
                (species_id,),
            ).fetchone()
        )
        if not correct:
            raise ApiError(HTTPStatus.NOT_FOUND, "correct species not found")
        options: list[dict[str, Any]] = [{**correct, "is_answer": True, "reason": "target species"}]
        seen = {species_id}

        candidate_queries = [
            (
                """
                SELECT s.id, s.common_name, s.scientific_name, s.family, ss.reason
                FROM species_similarity ss
                JOIN species s ON s.id = ss.similar_species_id
                WHERE ss.species_id = ? AND EXISTS (SELECT 1 FROM clips c WHERE c.species_id = s.id)
                ORDER BY ss.weight DESC
                """,
                (species_id,),
            ),
            (
                """
                SELECT s.id, s.common_name, s.scientific_name, s.family,
                       'same family' AS reason
                FROM species s
                WHERE s.family = ? AND s.id != ? AND EXISTS (SELECT 1 FROM clips c WHERE c.species_id = s.id)
                ORDER BY RANDOM()
                """,
                (correct.get("family"), species_id),
            ),
            (
                """
                SELECT s.id, s.common_name, s.scientific_name, s.family,
                       'general regional distractor' AS reason
                FROM species s
                WHERE s.id != ? AND EXISTS (SELECT 1 FROM clips c WHERE c.species_id = s.id)
                ORDER BY RANDOM()
                """,
                (species_id,),
            ),
        ]
        for query, args in candidate_queries:
            for row in self.conn.execute(query, args).fetchall():
                if row["id"] in seen:
                    continue
                options.append({**dict(row), "is_answer": False})
                seen.add(row["id"])
                if len(options) >= choices:
                    return options
        return options


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class TrainerHandler(BaseHTTPRequestHandler):
    repository: TrainerRepository
    static_dir: Path
    root: Path

    def do_GET(self) -> None:
        self.route()

    def do_POST(self) -> None:
        self.route()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def route(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self.send_json({"ok": True, "app": "BirdSoundTrainer", "time": time.time()})
            elif parsed.path.startswith("/api/"):
                with self.repository.lock:
                    self.route_api(parsed.path, params)
            elif parsed.path.startswith("/media/"):
                self.serve_media(parsed.path[len("/media/") :])
            else:
                self.serve_static(parsed.path)
        except ApiError as exc:
            self.send_json({"error": exc.message}, status=exc.status)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def route_api(self, path: str, params: dict[str, list[str]]) -> None:
        if path == "/api/summary":
            self.send_json(self.repository.summary())
        elif path == "/api/filters":
            self.send_json(self.repository.filters())
        elif path == "/api/species":
            self.send_json(self.repository.species(params))
        elif path.startswith("/api/species/"):
            self.send_json(self.repository.species_detail(int(path.rsplit("/", 1)[-1])))
        elif path == "/api/quiz/session" and self.command == "POST":
            self.send_json(self.repository.create_session(self.read_json()))
        elif path == "/api/quiz/next":
            self.send_json(self.repository.next_question(params))
        elif path == "/api/quiz/answer" and self.command == "POST":
            self.send_json(self.repository.answer_question(self.read_json()))
        elif path == "/api/progress":
            self.send_json(self.repository.progress())
        elif path == "/api/progress/reset" and self.command == "POST":
            self.send_json(self.repository.reset_progress())
        elif path == "/api/coverage":
            self.send_json(self.repository.coverage(params))
        elif path == "/api/attributions":
            self.send_json(self.repository.attributions())
        else:
            raise ApiError(HTTPStatus.NOT_FOUND, "not found")

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, request_path: str) -> None:
        rel = request_path.strip("/") or "index.html"
        if rel.startswith("api/"):
            raise ApiError(HTTPStatus.NOT_FOUND, "not found")
        candidate = (self.static_dir / rel).resolve()
        if not is_relative_to(candidate, self.static_dir) or not candidate.exists() or candidate.is_dir():
            candidate = self.static_dir / "index.html"
        self.serve_file(candidate)

    def serve_media(self, rel_url: str) -> None:
        rel = urllib.parse.unquote(rel_url).replace("/", "\\")
        candidate = (self.root / rel).resolve()
        if not is_relative_to(candidate, self.root) or not candidate.exists() or candidate.is_dir():
            raise ApiError(HTTPStatus.NOT_FOUND, "media not found")
        self.serve_file(candidate)

    def serve_file(self, path: Path) -> None:
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            mime = "text/javascript"
        if path.suffix == ".css":
            mime = "text/css"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(data)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key) or []
    return values[0] if values else None


def parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def run(host: str = "127.0.0.1", port: int = 8765, *, root_override: Path | None = None) -> None:
    paths = ProjectPaths(root_override.resolve()) if root_override else ProjectPaths.discover(ROOT)
    repo = TrainerRepository(paths)
    app_static_dir = (paths.root / "app").resolve()
    media_root = paths.root.resolve()

    class Handler(TrainerHandler):
        repository = repo
        static_dir = app_static_dir
        root = media_root

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Bird Sound Trainer running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(args.host, args.port)
