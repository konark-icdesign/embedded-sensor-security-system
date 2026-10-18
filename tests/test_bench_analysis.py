import json
from pathlib import Path
import tempfile
import unittest

from src.bench_analysis import analyze_board_bench, load_jsonl


def sample(session, seq, ms, arrival, captured, *, missing=0, drops=0,
           valid=True, degraded=False, p=False, m=False, u=False,
           range_m=1.0):
    return {
        "session": session,
        "sequence_unwrapped": seq,
        "board_millis_unwrapped": ms,
        "arrival": arrival,
        "captured": captured,
        "latency_seconds": arrival - captured,
        "missing_before": missing,
        "board_reported_drops_delta": drops,
        "range_valid": valid,
        "range_metres": range_m,
        "degraded": degraded,
        "pir": p,
        "radar": m,
        "near": u,
        "fallback_alarm": False,
    }


class BenchAnalysisTests(unittest.TestCase):
    def test_separates_normal_cadence_from_gaps_and_reboots(self):
        parsed = [
            sample("uno-r4-0000", 0, 1000, 10.010, 10.000, p=True),
            sample("uno-r4-0000", 1, 1100, 10.112, 10.100, m=True),
            sample("uno-r4-0000", 3, 1300, 10.315, 10.300,
                   missing=1, drops=1, u=True),
            sample("uno-r4-0001", 0, 100, 10.520, 10.500,
                   valid=False, degraded=True),
        ]
        raw = [
            {"accepted": True},
            {"accepted": True},
            {"accepted": False, "error": "bad packet"},
            {"accepted": True},
            {"accepted": True},
        ]

        result = analyze_board_bench(parsed, raw)

        self.assertEqual(result["samples"], 4)
        self.assertEqual(result["session_count"], 2)
        self.assertEqual(result["reboots_observed"], 1)
        self.assertEqual(result["sequence_gaps"], 1)
        self.assertEqual(result["board_reported_drops"], 1)
        self.assertEqual(
            result["normal_contiguous_board_period_ms"]["count"], 1
        )
        self.assertAlmostEqual(
            result["normal_contiguous_board_period_ms"]["mean"], 100.0
        )
        self.assertAlmostEqual(
            result["normal_contiguous_arrival_period_ms"]["mean"], 102.0
        )
        self.assertAlmostEqual(
            result["normal_transport_interval_error_ms"]["mean"], 2.0
        )
        self.assertEqual(result["sensor_observations"]["range_invalid"], 1)
        self.assertEqual(result["sensor_observations"]["degraded"], 1)
        self.assertEqual(result["raw_transport"]["rejected"], 1)

    def test_flags_clock_mapping_that_goes_backward_or_future(self):
        parsed = [
            sample("uno-r4-0000", 0, 1000, 10.100, 10.090),
            sample("uno-r4-0000", 1, 1100, 10.200, 10.210),
            sample("uno-r4-0000", 2, 1200, 10.300, 10.150),
        ]

        result = analyze_board_bench(parsed)

        self.assertEqual(result["negative_transport_latency_samples"], 1)
        self.assertEqual(
            result["mapped_capture_nonmonotonic_intervals"], 1
        )

    def test_range_reference_reports_bias_and_absolute_error(self):
        parsed = [
            sample("uno-r4-0000", 0, 1000, 10.0, 9.99, range_m=0.98),
            sample("uno-r4-0000", 1, 1100, 10.1, 10.09, range_m=1.01),
            sample("uno-r4-0000", 2, 1200, 10.2, 10.19, range_m=1.03),
            sample(
                "uno-r4-0000", 3, 1300, 10.3, 10.29,
                range_m=9.99, valid=False
            ),
        ]

        result = analyze_board_bench(
            parsed,
            reference_distance_m=1.0,
        )
        accuracy = result["range_reference"]

        self.assertEqual(accuracy["valid_measurements"], 3)
        self.assertAlmostEqual(
            accuracy["measured_range_m"]["mean"],
            (0.98 + 1.01 + 1.03) / 3.0,
        )
        self.assertAlmostEqual(
            accuracy["signed_error_m"]["mean"],
            (0.98 + 1.01 + 1.03) / 3.0 - 1.0,
        )
        self.assertAlmostEqual(
            accuracy["absolute_error_m"]["max"],
            0.03,
        )
        self.assertAlmostEqual(
            accuracy["absolute_error_percent"]["max"],
            3.0,
        )

    def test_range_reference_requires_positive_finite_distance(self):
        parsed = [
            sample("uno-r4-0000", 0, 1000, 10.0, 9.99, range_m=1.0)
        ]
        with self.assertRaises(ValueError):
            analyze_board_bench(parsed, reference_distance_m=0)
        with self.assertRaises(ValueError):
            analyze_board_bench(parsed, reference_distance_m=float("nan"))

    def test_empty_capture_is_reported_without_fake_numbers(self):
        result = analyze_board_bench([], [])
        self.assertEqual(result["samples"], 0)
        self.assertIsNone(result["observed_sample_rate_hz"])
        self.assertIsNone(result["transport_latency_ms"]["mean"])
        self.assertEqual(result["session_count"], 0)

    def test_load_jsonl_rejects_malformed_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capture.jsonl"
            path.write_text('{"ok": true}\nnot-json\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_jsonl(path)

    def test_load_jsonl_preserves_record_order(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capture.jsonl"
            rows = [{"n": 2}, {"n": 1}]
            path.write_text(
                "".join(json.dumps(x) + "\n" for x in rows),
                encoding="utf-8",
            )
            self.assertEqual(load_jsonl(path), rows)


if __name__ == "__main__":
    unittest.main()
