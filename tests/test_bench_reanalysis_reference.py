import json
from pathlib import Path
import tempfile
import unittest

from scripts.analyze_board_bench import resolve_reference_distance


class BenchReanalysisReferenceTests(unittest.TestCase):
    def test_uses_reference_stored_next_to_parsed_capture(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parsed = root / "board_samples.jsonl"
            parsed.write_text("", encoding="utf-8")
            (root / "metadata.json").write_text(
                json.dumps({"reference_distance_m": 1.25}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(resolve_reference_distance(parsed), 1.25)

    def test_explicit_reference_may_match_stored_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parsed = root / "board_samples.jsonl"
            parsed.write_text("", encoding="utf-8")
            (root / "metadata.json").write_text(
                json.dumps({"reference_distance_m": 0.75}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                resolve_reference_distance(parsed, explicit=0.75),
                0.75,
            )

    def test_conflicting_explicit_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parsed = root / "board_samples.jsonl"
            parsed.write_text("", encoding="utf-8")
            (root / "metadata.json").write_text(
                json.dumps({"reference_distance_m": 1.0}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "conflicts"):
                resolve_reference_distance(parsed, explicit=1.1)

    def test_capture_without_metadata_reference_remains_supported(self):
        with tempfile.TemporaryDirectory() as td:
            parsed = Path(td) / "board_samples.jsonl"
            parsed.write_text("", encoding="utf-8")
            self.assertIsNone(resolve_reference_distance(parsed))
            self.assertEqual(
                resolve_reference_distance(parsed, explicit=2.0),
                2.0,
            )


if __name__ == "__main__":
    unittest.main()
