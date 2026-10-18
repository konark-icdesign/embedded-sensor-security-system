import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from src.range_characterization import (
    build_characterization,
    characterize_capture,
    characterization_csv,
)


def trial(capture, reference, *, revision="abc", dirty=False, bias=0.0):
    return {
        "capture": capture,
        "label": capture,
        "reference_distance_m": reference,
        "setup_note": "flat target",
        "git_revision": revision,
        "git_dirty": dirty,
        "samples": 100,
        "valid_measurements": 98,
        "valid_fraction": 0.98,
        "measured_mean_m": reference + bias,
        "measured_median_m": reference + bias,
        "signed_error_mean_m": bias,
        "signed_error_median_m": bias,
        "absolute_error_mean_m": abs(bias),
        "absolute_error_median_m": abs(bias),
        "absolute_error_p95_m": abs(bias) + 0.01,
        "absolute_error_max_m": abs(bias) + 0.02,
        "absolute_error_percent_mean": abs(bias) / reference * 100.0,
        "absolute_error_percent_median": abs(bias) / reference * 100.0,
        "absolute_error_percent_p95": (
            (abs(bias) + 0.01) / reference * 100.0
        ),
        "absolute_error_percent_max": (
            (abs(bias) + 0.02) / reference * 100.0
        ),
        "range_invalid": 2,
        "sequence_gaps": 0,
        "board_reported_drops": 0,
        "integrity_ok": True,
    }


class RangeCharacterizationTests(unittest.TestCase):
    def test_trials_sort_by_reference_distance(self):
        result = build_characterization([
            trial("two", 2.0),
            trial("half", 0.5),
            trial("one", 1.0),
        ])
        self.assertEqual(
            [row["reference_distance_m"] for row in result["trials"]],
            [0.5, 1.0, 2.0],
        )
        self.assertEqual(result["reference_distance_min_m"], 0.5)
        self.assertEqual(result["reference_distance_max_m"], 2.0)

    def test_revision_and_dirty_capture_provenance_is_preserved(self):
        result = build_characterization([
            trial("a", 1.0, revision="aaa", dirty=False),
            trial("b", 2.0, revision="bbb", dirty=True),
            trial("c", 3.0, revision="aaa", dirty=False),
        ])
        self.assertEqual(result["source_revisions"], ["aaa", "bbb"])
        self.assertEqual(result["dirty_capture_count"], 1)

    def test_does_not_emit_single_aggregate_accuracy_claim(self):
        result = build_characterization([
            trial("a", 1.0, bias=0.01),
            trial("b", 2.0, bias=-0.02),
        ])
        self.assertNotIn("accuracy", result)
        self.assertNotIn("pass", result)
        self.assertNotIn("fail", result)

    def test_capture_is_recomputed_from_verified_raw_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "metadata.json").write_text(
                json.dumps({
                    "label": "range-static-1m",
                    "reference_distance_m": 1.0,
                    "setup_note": "flat target",
                    "git_revision": "abc123",
                    "git_dirty": False,
                }) + "\n",
                encoding="utf-8",
            )
            rows = [
                {
                    "session": "uno-r4-0000",
                    "sequence_unwrapped": 0,
                    "board_millis_unwrapped": 1000,
                    "arrival": 10.01,
                    "captured": 10.00,
                    "latency_seconds": 0.01,
                    "missing_before": 0,
                    "board_reported_drops_delta": 0,
                    "range_valid": True,
                    "range_metres": 0.98,
                    "degraded": False,
                    "pir": False,
                    "radar": False,
                    "near": False,
                    "fallback_alarm": False,
                },
                {
                    "session": "uno-r4-0000",
                    "sequence_unwrapped": 1,
                    "board_millis_unwrapped": 1100,
                    "arrival": 10.11,
                    "captured": 10.10,
                    "latency_seconds": 0.01,
                    "missing_before": 0,
                    "board_reported_drops_delta": 0,
                    "range_valid": True,
                    "range_metres": 1.02,
                    "degraded": False,
                    "pir": False,
                    "radar": False,
                    "near": False,
                    "fallback_alarm": False,
                },
                {
                    "session": "uno-r4-0000",
                    "sequence_unwrapped": 2,
                    "board_millis_unwrapped": 1200,
                    "arrival": 10.21,
                    "captured": 10.20,
                    "latency_seconds": 0.01,
                    "missing_before": 0,
                    "board_reported_drops_delta": 0,
                    "range_valid": False,
                    "range_metres": 9.0,
                    "degraded": True,
                    "pir": False,
                    "radar": False,
                    "near": False,
                    "fallback_alarm": False,
                },
            ]
            (root / "board_samples.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            (root / "board_raw.jsonl").write_text(
                "".join(
                    json.dumps({"accepted": True}) + "\n"
                    for _ in rows
                ),
                encoding="utf-8",
            )
            integrity = {
                "ok": True,
                "files": {
                    "metadata.json": {"ok": True},
                    "board_samples.jsonl": {"ok": True},
                    "board_raw.jsonl": {"ok": True},
                },
            }

            result = characterize_capture(root, integrity)

        self.assertEqual(result["valid_measurements"], 2)
        self.assertAlmostEqual(result["valid_fraction"], 2 / 3)
        self.assertAlmostEqual(result["measured_mean_m"], 1.0)
        self.assertAlmostEqual(result["signed_error_mean_m"], 0.0)
        self.assertAlmostEqual(result["absolute_error_mean_m"], 0.02)
        self.assertEqual(result["range_invalid"], 1)

    def test_unverified_required_file_is_rejected(self):
        integrity = {
            "ok": True,
            "files": {
                "metadata.json": {"ok": True},
                "board_samples.jsonl": {"ok": True},
            },
        }
        with self.assertRaisesRegex(ValueError, "board_raw.jsonl"):
            characterize_capture("unused", integrity)

    def test_csv_contains_one_row_per_trial(self):
        result = build_characterization([
            trial("a", 1.0, bias=0.01),
            trial("b", 2.0, bias=-0.02),
        ])
        rows = list(csv.DictReader(io.StringIO(
            characterization_csv(result)
        )))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["capture"], "a")
        self.assertEqual(rows[1]["capture"], "b")
        self.assertIn("absolute_error_p95_m", rows[0])


if __name__ == "__main__":
    unittest.main()
