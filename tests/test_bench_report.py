import unittest

from src.bench_report import format_bench_report


class BenchReportTests(unittest.TestCase):
    def test_report_surfaces_measurements_without_pass_fail(self):
        summary = {
            "metadata": {
                "label": "usb-idle",
                "started_utc": "2026-10-11T00:00:00+00:00",
                "ended_utc": "2026-10-11T00:01:00+00:00",
                "port_argument": "auto",
                "resolved_ports_seen": ["COM7"],
                "git_revision": "abc123",
                "git_dirty": False,
                "firmware_identity_state": "reported",
                "reported_firmware_ids": [
                    "gabc123-sdef456"
                ],
                "intended_firmware_build_id": "gabc123-sdef456",
                "firmware_build_match_state": "match",
                "firmware_artifacts_verified_before_capture": True,
                "firmware_build_manifest_sha256": "f" * 64,
                "firmware_flash_artifacts": [{
                    "manifest_path": "night_security.ino.bin",
                    "capture_file": (
                        "firmware_flash_0_night_security.ino.bin"
                    ),
                    "sha256": "a" * 64,
                }],
                "reference_distance_m": 1.0,
                "setup_note": "flat target, tape measured",
            },
            "runtime_health": {
                "connect_attempts": 1,
                "connection_errors": 0,
                "disconnects": 0,
                "timeouts": 0,
                "transport_rejected": 0,
                "identity_requests": 1,
            },
            "analysis": {
                "samples": 600,
                "capture_duration_seconds": 59.9,
                "observed_sample_rate_hz": 10.0,
                "session_count": 1,
                "reboots_observed": 0,
                "sequence_gaps": 2,
                "board_reported_drops": 1,
                "transport_latency_ms": {
                    "count": 600, "median": 4.2, "p95": 8.1,
                    "p99": 11.0, "max": 15.0,
                },
                "normal_contiguous_board_period_ms": {
                    "count": 597, "median": 100.0, "p95": 100.0,
                    "p99": 100.0, "max": 100.0,
                },
                "normal_contiguous_arrival_period_ms": {
                    "count": 597, "median": 100.1, "p95": 102.0,
                    "p99": 104.0, "max": 106.0,
                },
                "normal_transport_interval_abs_error_ms": {
                    "count": 597, "median": 0.4, "p95": 2.0,
                    "p99": 4.0, "max": 6.0,
                },
                "arrival_nonmonotonic_intervals": 0,
                "mapped_capture_nonmonotonic_intervals": 0,
                "board_nonmonotonic_intervals": 0,
                "negative_transport_latency_samples": 0,
                "range_reference": {
                    "reference_distance_m": 1.0,
                    "valid_measurements": 595,
                    "measured_range_m": {
                        "count": 595, "median": 1.002, "p95": 1.010,
                        "p99": 1.015, "max": 1.020,
                    },
                    "signed_error_m": {
                        "count": 595, "median": 0.002, "mean": 0.001,
                        "p95": 0.010, "p99": 0.015, "max": 0.020,
                    },
                    "absolute_error_m": {
                        "count": 595, "median": 0.004, "p95": 0.010,
                        "p99": 0.015, "max": 0.020,
                    },
                    "absolute_error_percent": {
                        "count": 595, "median": 0.4, "p95": 1.0,
                        "p99": 1.5, "max": 2.0,
                    },
                },
                "sensor_observations": {
                    "range_valid": 595,
                    "range_invalid": 5,
                    "degraded": 5,
                    "pir_active": 10,
                    "radar_active": 15,
                    "near_active": 8,
                    "fallback_alarm": 0,
                },
                "raw_transport": {
                    "records": 601,
                    "accepted": 600,
                    "rejected": 1,
                },
            },
        }

        report = format_bench_report(summary)

        self.assertIn("label: usb-idle", report)
        self.assertIn("resolved_ports_seen: COM7", report)
        self.assertIn("firmware_identity_state: reported", report)
        self.assertIn("reported_firmware_ids: gabc123-sdef456", report)
        self.assertIn(
            "intended_firmware_build_id: gabc123-sdef456",
            report,
        )
        self.assertIn("firmware_build_match_state: match", report)
        self.assertIn(
            "firmware_artifacts_verified_before_capture: True",
            report,
        )
        self.assertIn("firmware_build_manifest_sha256:", report)
        self.assertIn(
            "firmware_flash_artifacts: "
            "firmware_flash_0_night_security.ino.bin",
            report,
        )
        self.assertIn("reference_distance_m: 1.000", report)
        self.assertIn("setup_note: flat target, tape measured", report)
        self.assertIn("observed_sample_rate_hz: 10.000", report)
        self.assertIn("sequence_gaps: 2", report)
        self.assertIn("p95=8.100 ms", report)
        self.assertIn("range_invalid: 5", report)
        self.assertIn("identity_requests: 1", report)
        self.assertIn("Range reference analysis", report)
        self.assertIn("signed_error_mean_m: 0.001", report)
        self.assertIn("absolute_error_percent", report)
        self.assertIn("p95=1.000 %", report)
        self.assertIn("no PASS/FAIL threshold is applied", report)
        self.assertNotIn("PASS:", report)
        self.assertNotIn("FAIL:", report)

    def test_report_handles_missing_optional_values(self):
        report = format_bench_report({
            "metadata": {},
            "runtime_health": {},
            "analysis": {
                "transport_latency_ms": {},
                "normal_contiguous_board_period_ms": {},
                "normal_contiguous_arrival_period_ms": {},
                "normal_transport_interval_abs_error_ms": {},
                "sensor_observations": {},
            },
        })
        self.assertIn("observed_sample_rate_hz: n/a", report)
        self.assertIn("mapped_transport_latency: count=0", report)
        self.assertIn("resolved_ports_seen: none", report)


if __name__ == "__main__":
    unittest.main()
