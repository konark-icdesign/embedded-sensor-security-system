import json
from pathlib import Path
import tempfile
import unittest

from src.board_live import (
    BoardLiveRunner,
    PortSelectionError,
    choose_serial_port,
    format_health,
)


def packet(seq, ms, drops=0, *, p=0, m=0, u=0, metres=3.0, valid=1,
           alarm=0, armed=1, degraded=0, fallback=0):
    value = "nan" if not valid else str(metres)
    return (
        f"S,{seq},{ms},{p},{m},{u},{value},{valid},{alarm},{armed},"
        f"{degraded},{fallback},{drops}\n"
    ).encode("ascii")


class Port:
    def __init__(self, device, description="", manufacturer="", product="", hwid=""):
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.product = product
        self.hwid = hwid


class FakeClock:
    def __init__(self, start=10.0):
        self.value = float(start)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeSerial:
    def __init__(self, clock, events):
        self.clock = clock
        self.events = list(events)
        self.closed = False

    def readline(self):
        if not self.events:
            raise OSError("disconnect")
        dt, payload = self.events.pop(0)
        self.clock.advance(dt)
        if isinstance(payload, BaseException):
            raise payload
        return payload

    def close(self):
        self.closed = True


class Factory:
    def __init__(self, clock, connections):
        self.clock = clock
        self.connections = [list(c) for c in connections]
        self.opens = 0

    def __call__(self, port, baudrate, timeout):
        del port, baudrate, timeout
        self.opens += 1
        if not self.connections:
            raise OSError("no more connections")
        return FakeSerial(self.clock, self.connections.pop(0))


class BoardLiveTests(unittest.TestCase):
    def test_port_choice_prefers_unique_arduino(self):
        ports = [
            Port("COM3", "Bluetooth"),
            Port("COM7", "Arduino UNO R4 WiFi"),
        ]
        self.assertEqual(choose_serial_port(ports), "COM7")

    def test_port_choice_refuses_ambiguous_ports(self):
        with self.assertRaises(PortSelectionError):
            choose_serial_port([Port("COM3"), Port("COM4")])
        with self.assertRaises(PortSelectionError):
            choose_serial_port([])

    def test_reconnect_gap_rejection_reboot_and_logs(self):
        clock = FakeClock(100.0)
        factory = Factory(clock, [
            [
                (.010, packet(0, 60000)),
                (.100, packet(1, 60100, p=1)),
                (.100, OSError("unplug")),
            ],
            [
                (.210, packet(4, 60400, 2, m=1)),
                (.100, b"garbage\n"),
                (.100, packet(5, 60500, 2, u=1)),
                (.100, OSError("reset")),
            ],
            [
                (.250, packet(0, 120)),
                (.100, packet(1, 220, degraded=1, valid=0)),
            ],
        ])

        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "raw.jsonl"
            parsed = Path(td) / "parsed.jsonl"
            runner = BoardLiveRunner(
                port="COM7",
                serial_factory=factory,
                clock=clock,
                wall_clock=lambda: 1700000000.0,
                sleep=lambda dt: clock.advance(dt),
                reconnect_delay=.05,
                raw_log=raw,
                parsed_log=parsed,
                status_interval=0,
            )
            result = runner.run(max_samples=6, max_connect_attempts=4)
            raw_rows = [json.loads(x) for x in raw.read_text().splitlines()]
            parsed_rows = [json.loads(x) for x in parsed.read_text().splitlines()]

        self.assertEqual(result["samples"], 6)
        self.assertEqual(result["ports_seen"], ["COM7"])
        self.assertEqual(result["disconnects"], 2)
        self.assertEqual(result["sequence_gaps"], 2)
        self.assertEqual(result["board_reported_drops"], 2)
        self.assertEqual(result["transport_rejected"], 1)
        self.assertEqual(result["reboots"], 1)
        self.assertEqual(result["session"], "uno-r4-0001")
        self.assertEqual(len(raw_rows), 7)
        self.assertEqual(len(parsed_rows), 6)
        self.assertTrue(any(not x["accepted"] for x in raw_rows))
        self.assertTrue(parsed_rows[-1]["degraded"])
        self.assertFalse(parsed_rows[-1]["range_valid"])

    def test_auto_reconnect_records_changed_port(self):
        clock = FakeClock(30.0)
        factory = Factory(clock, [
            [
                (.010, packet(0, 1000)),
                (.100, OSError("unplug")),
            ],
            [
                (.200, packet(1, 1100)),
            ],
        ])
        ports = iter(["COM7", "COM8"])
        runner = BoardLiveRunner(
            port="auto",
            port_resolver=lambda: next(ports),
            serial_factory=factory,
            clock=clock,
            wall_clock=lambda: 0.0,
            sleep=lambda dt: clock.advance(dt),
            reconnect_delay=.05,
        )
        result = runner.run(max_samples=2, max_connect_attempts=2)
        self.assertEqual(result["ports_seen"], ["COM7", "COM8"])

    def test_connection_error_is_preserved_in_health(self):
        clock = FakeClock(40.0)

        def fail_open(port, baudrate, timeout):
            del port, baudrate, timeout
            raise OSError("access denied")

        runner = BoardLiveRunner(
            port="COM7",
            serial_factory=fail_open,
            clock=clock,
            wall_clock=lambda: 0.0,
            sleep=lambda dt: clock.advance(dt),
            reconnect_delay=.05,
        )
        result = runner.run(max_connect_attempts=1)
        self.assertEqual(result["connect_attempts"], 1)
        self.assertEqual(result["connection_errors"], 1)
        self.assertIn("access denied", result["last_connection_error"])

    def test_resolution_failures_respect_connect_attempt_limit(self):
        clock = FakeClock(50.0)

        def no_port():
            raise PortSelectionError("no serial ports found")

        runner = BoardLiveRunner(
            port="auto",
            port_resolver=no_port,
            clock=clock,
            wall_clock=lambda: 0.0,
            sleep=lambda dt: clock.advance(dt),
            reconnect_delay=.05,
        )
        result = runner.run(max_connect_attempts=2)
        self.assertEqual(result["connect_attempts"], 2)
        self.assertEqual(result["connection_errors"], 2)
        self.assertIn("no serial ports found", result["last_connection_error"])

    def test_stale_packet_rejected_but_runner_continues(self):
        clock = FakeClock(10.0)
        factory = Factory(clock, [[
            (.010, packet(1, 1000)),
            (.690, packet(2, 1100)),
            (.010, packet(3, 1200)),
        ]])
        runner = BoardLiveRunner(
            port="COM7",
            serial_factory=factory,
            clock=clock,
            wall_clock=lambda: 0.0,
            sleep=lambda dt: clock.advance(dt),
            status_interval=0,
        )
        result = runner.run(max_samples=2, max_connect_attempts=1)
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["transport_rejected"], 1)
        self.assertEqual(result["adapter_rejected"], 1)

    def test_timeout_does_not_disconnect(self):
        clock = FakeClock(20.0)
        factory = Factory(clock, [[
            (.010, b""),
            (.100, packet(1, 1000)),
        ]])
        runner = BoardLiveRunner(
            port="COM7",
            serial_factory=factory,
            clock=clock,
            wall_clock=lambda: 0.0,
            sleep=lambda dt: clock.advance(dt),
        )
        result = runner.run(max_samples=1, max_connect_attempts=1)
        self.assertEqual(result["timeouts"], 1)
        self.assertEqual(result["disconnects"], 0)

    def test_health_formatter_is_compact(self):
        status = {
            "connected": True, "port": "COM7", "session": "uno-r4-0000",
            "samples": 10, "rate_hz": 10.0, "last_latency_seconds": .018,
            "sequence_gaps": 1, "board_reported_drops": 1, "reboots": 0,
            "transport_rejected": 0, "pir": True, "radar": False,
            "near": False, "range_valid": True, "degraded": False,
        }
        line = format_health(status)
        self.assertIn("rate=10.00 Hz", line)
        self.assertIn("latency=18.0 ms", line)
        self.assertIn("gaps=1", line)

    def test_health_formatter_shows_disconnected_connection_error(self):
        status = {
            "connected": False, "port": None, "session": "uno-r4-0000",
            "samples": 0, "rate_hz": None, "last_latency_seconds": None,
            "sequence_gaps": 0, "board_reported_drops": 0, "reboots": 0,
            "transport_rejected": 0, "pir": None, "radar": None,
            "near": None, "range_valid": None, "degraded": None,
            "last_connection_error": "OSError: access denied",
        }
        line = format_health(status)
        self.assertIn("BOARD disconnected", line)
        self.assertIn("connection_error=OSError: access denied", line)


if __name__ == "__main__":
    unittest.main()
