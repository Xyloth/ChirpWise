import tempfile
import unittest
from pathlib import Path

from ingest.birdtrainer.config import ProjectPaths
from ingest.birdtrainer.db import connect, initialize
from ingest.birdtrainer.seed import create_seed_dataset
from server.trainer_server import TrainerRepository


class SeedAndQuizTests(unittest.TestCase):
    def test_seed_dataset_builds_playable_quiz(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ProjectPaths(root)
            paths.ensure()
            conn = connect(paths.db_path)
            initialize(conn)
            create_seed_dataset(conn, root)

            self.assertEqual(conn.execute("SELECT COUNT(*) FROM species").fetchone()[0], 12)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0], 24)
            self.assertTrue((root / "data" / "manifests" / "license_manifest.json").exists())

            repo = TrainerRepository(paths)
            question = repo.next_question({"choices": ["3"]})
            self.assertEqual(len(question["options"]), 3)
            self.assertTrue(question["audio_url"].startswith("/media/"))

            chosen = question["options"][0]["id"]
            reveal = repo.answer_question(
                {
                    "session_id": question["session_id"],
                    "clip_id": question["clip_id"],
                    "chosen_species_id": chosen,
                    "response_ms": 1200,
                }
            )
            self.assertIn("was_correct", reveal)
            self.assertIn("correct_species", reveal)
            repo.conn.close()
            conn.close()


if __name__ == "__main__":
    unittest.main()
