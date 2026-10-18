import csv
import io
import unittest

from src.range_characterization import (
    build_characterization,
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
