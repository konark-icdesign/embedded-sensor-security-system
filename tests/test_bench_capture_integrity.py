import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_board_bench import (
    _source_state,
    _write_integrity_manifest,
)


class Completed:
    def __init__(self, stdout):
        self.stdout = stdout


class BenchCaptureIntegrityTests(unittest.TestCase):
    def test_integrity_manifest_records_size_and_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / "board_raw.jsonl"
            evidence.write_bytes(b"abc")
            manifest_path = root / "capture_integrity.json"

            manifest = _write_integrity_manifest(
                manifest_path, [evidence, root / "missing.jsonl"]
            )
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))

        expected = (
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        )
        self.assertEqual(manifest, stored)
        self.assertEqual(stored["algorithm"], "sha256")
        self.assertEqual(stored["files"]["board_raw.jsonl"]["bytes"], 3)
        self.assertEqual(
            stored["files"]["board_raw.jsonl"]["sha256"], expected
        )
        self.assertNotIn("missing.jsonl", stored["files"])

    @patch("scripts.run_board_bench.subprocess.run")
    def test_source_state_records_revision_and_dirty_tree(self, run):
        run.side_effect = [
            Completed("1234567890abcdef\n"),
            Completed(" M scripts/run_board_bench.py\n"),
        ]
        state = _source_state()
        self.assertEqual(state["git_revision"], "1234567890abcdef")
        self.assertTrue(state["git_dirty"])

    @patch("scripts.run_board_bench.subprocess.run")
    def test_source_state_degrades_cleanly_without_git(self, run):
        run.side_effect = OSError("git unavailable")
        self.assertEqual(
            _source_state(),
            {"git_revision": None, "git_dirty": None},
        )


if __name__ == "__main__":
    unittest.main()
