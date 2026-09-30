import json
from pathlib import Path
import tempfile
import unittest

from src.bench_analysis import analyze_board_bench, load_jsonl


def sample(session, seq, ms, arrival, captured, *, missing=0, drops=0,
           valid=True, degraded=False, p=False, m=False, u=False):
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
