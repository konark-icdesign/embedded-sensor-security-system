from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.bench_preflight import format_preflight, run_preflight


class Port:
    def __init__(
        self,
        device,
        description="",
        manufacturer="",
        product="",
        hwid="",
    ):
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.product = product
        self.hwid = hwid


class Completed:
    def __init__(self, stdout):
        self.stdout = stdout


class BenchPreflightTests(unittest.TestCase):
    @patch("src.bench_preflight.subprocess.run")
    def test_auto_selects_uno_and_checks_output(self, git_run):
        git_run.side_effect = [
            Completed("abc123\n"),
            Completed(""),
        ]
        with tempfile.TemporaryDirectory() as td:
            result = run_preflight(
                port="auto",
                output_root=Path(td) / "bench",
                repo_root=td,
                port_provider=lambda: [
                    Port("COM3", "Bluetooth"),
                    Port("COM7", "Arduino UNO R4 WiFi"),
                ],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["selected_port"], "COM7")
        self.assertEqual(result["git_revision"], "abc123")
        self.assertFalse(result["git_dirty"])
        self.assertEqual(len(result["serial_ports"]), 2)

    @patch("src.bench_preflight.subprocess.run")
    def test_no_ports_fails_before_capture(self, git_run):
        git_run.side_effect = [
            Completed("abc123\n"),
            Completed(""),
        ]
        with tempfile.TemporaryDirectory() as td:
            result = run_preflight(
                output_root=td,
                repo_root=td,
                port_provider=lambda: [],
            )

        self.assertFalse(result["ok"])
        self.assertIn("no serial ports found", result["errors"])

    @patch("src.bench_preflight.subprocess.run")
    def test_explicit_missing_port_fails(self, git_run):
        git_run.side_effect = [
            Completed("abc123\n"),
            Completed(""),
        ]
        with tempfile.TemporaryDirectory() as td:
            result = run_preflight(
                port="COM9",
                output_root=td,
                repo_root=td,
                port_provider=lambda: [Port("COM7", "Arduino UNO R4 WiFi")],
            )

        self.assertFalse(result["ok"])
        self.assertIn(
            "requested serial port is not present: COM9",
            result["errors"],
        )

    @patch("src.bench_preflight.subprocess.run")
    def test_dirty_tree_warns_but_does_not_fail(self, git_run):
        git_run.side_effect = [
            Completed("abc123\n"),
            Completed(" M src/board_live.py\n"),
        ]
        with tempfile.TemporaryDirectory() as td:
            result = run_preflight(
                output_root=td,
                repo_root=td,
                port_provider=lambda: [
                    Port("COM7", "Arduino UNO R4 WiFi")
                ],
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["git_dirty"])
        self.assertTrue(result["warnings"])

    @patch("src.bench_preflight.subprocess.run")
    def test_unwritable_output_fails(self, git_run):
        git_run.side_effect = [
            Completed("abc123\n"),
            Completed(""),
        ]

        def fail_probe(path):
            raise RuntimeError("output root is not writable: {}".format(path))

        result = run_preflight(
            output_root="Z:/missing",
            repo_root=".",
            port_provider=lambda: [Port("COM7", "Arduino UNO R4 WiFi")],
            output_probe=fail_probe,
        )
        self.assertFalse(result["ok"])
        self.assertIn(
            "output root is not writable: Z:/missing",
            result["errors"],
        )

    def test_formatter_is_compact(self):
        line = format_preflight({
            "ok": False,
            "selected_port": None,
            "warnings": [],
            "errors": ["no serial ports found"],
        })
        self.assertIn("PREFLIGHT FAIL", line)
        self.assertIn("no serial ports found", line)


if __name__ == "__main__":
    unittest.main()
