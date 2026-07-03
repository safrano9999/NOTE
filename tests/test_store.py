import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StoreTests(unittest.TestCase):
    def run_store(self, backend, note_path):
        env = os.environ.copy()
        env.update({"NOTE_DB_BACKEND": backend, "NOTE_PATH": str(note_path), "PYTHONPATH": str(ROOT)})
        payload = {
            "message": "Test note",
            "timestamp": 1783090800000,
            "note_path": str(note_path),
            "channel": "telegram",
            "account_id": "main",
            "sender_id": "42",
            "message_id": "99",
        }
        return subprocess.run(
            ["python3", str(ROOT / "note" / "store.py")],
            input=json.dumps(payload), text=True, capture_output=True, env=env, check=True,
        )

    def test_file_backend_appends_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = json.loads(self.run_store("file", tmp).stdout)
            target = Path(result["path"])
            self.assertTrue(target.name.endswith(".md"))
            self.assertIn("Test note  \n", target.read_text(encoding="utf-8"))
            env = os.environ.copy()
            env.update({"NOTE_DB_BACKEND": "file", "PYTHONPATH": str(ROOT)})
            shown = subprocess.run(
                ["python3", str(ROOT / "note" / "store.py")],
                input=json.dumps({"action": "show", "note_path": tmp, "hours": 48}),
                text=True, capture_output=True, env=env, check=True,
            )
            self.assertIn("Test note", json.loads(shown.stdout)["text"])

    def test_sqlite_backend_creates_note(self):
        result = json.loads(self.run_store("sqlite", "/unused").stdout)
        self.assertEqual(result["backend"], "sqlite")
        self.assertGreater(result["id"], 0)


if __name__ == "__main__":
    unittest.main()
