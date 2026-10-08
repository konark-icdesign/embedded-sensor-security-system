import unittest

from scripts.run_board_bench import _zero_sample_diagnostic


class BenchFailureDiagnosticTests(unittest.TestCase):
    def test_connection_error_is_preferred(self):
        message = _zero_sample_diagnostic({
            "last_connection_error": "OSError: access denied",
            "transport_rejected": 0,
            "timeouts": 0,
        })
        self.assertIn("access denied", message)

    def test_rejected_lines_point_to_device_or_firmware(self):
        message = _zero_sample_diagnostic({
            "last_connection_error": None,
            "transport_rejected": 3,
            "timeouts": 0,
        })
        self.assertIn("3 serial line(s) were rejected", message)
        self.assertIn("firmware", message)

    def test_silent_open_port_points_to_serial_monitor(self):
        message = _zero_sample_diagnostic({
            "last_connection_error": None,
            "transport_rejected": 0,
            "timeouts": 8,
        })
        self.assertIn("8 read timeout(s)", message)
        self.assertIn("Serial Monitor", message)

    def test_empty_health_has_generic_diagnostic(self):
        self.assertEqual(
            _zero_sample_diagnostic({}),
            "no valid board telemetry was received",
        )


if __name__ == "__main__":
    unittest.main()
