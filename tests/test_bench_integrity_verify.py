import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_board_bench import verify_capture


def digest(data):
    return hashlib.sha256(data).hexdigest()


class BenchIntegrityVerifierTests(unittest.TestCase):
    def _write_manifest(self, root, files):
        (root / "capture_integrity.json").write_text(
            json.dumps({"algorithm": "sha256", "files": files}) + "\n",
            encoding="utf-8",
        )

    def test_valid_capture_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = b"abc"
            (root / "board_raw.jsonl").write_bytes(data)
            self._write_manifest(root, {
                "board_raw.jsonl": {
                    "bytes": len(data),
                    "sha256": digest(data),
                }
            })

            result = verify_capture(root)

        self.assertTrue(result["ok"])
        self.assertTrue(result["files"]["board_raw.jsonl"]["bytes_ok"])
        self.assertTrue(result["files"]["board_raw.jsonl"]["sha256_ok"])

    def test_same_size_edit_is_detected_by_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = b"abc"
            (root / "board_raw.jsonl").write_bytes(b"abd")
            self._write_manifest(root, {
                "board_raw.jsonl": {
                    "bytes": len(original),
                    "sha256": digest(original),
                }
            })

            result = verify_capture(root)

        self.assertFalse(result["ok"])
        self.assertTrue(result["files"]["board_raw.jsonl"]["bytes_ok"])
        self.assertFalse(result["files"]["board_raw.jsonl"]["sha256_ok"])

    def test_missing_evidence_file_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_manifest(root, {
                "board_samples.jsonl": {
                    "bytes": 10,
                    "sha256": "0" * 64,
                }
            })

            result = verify_capture(root)

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["files"]["board_samples.jsonl"]["error"],
            "file missing",
        )

    def test_manifest_cannot_escape_capture_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_manifest(root, {
                "../outside.txt": {
                    "bytes": 0,
                    "sha256": digest(b""),
                }
            })

            result = verify_capture(root)

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["files"]["../outside.txt"]["error"],
            "unsafe manifest filename",
        )

    def test_missing_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(
                ValueError, "capture_integrity.json not found"
            ):
                verify_capture(td)


if __name__ == "__main__":
    unittest.main()
