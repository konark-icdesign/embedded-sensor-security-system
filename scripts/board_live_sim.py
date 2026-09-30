"""Deterministic Rev-F simulation of the live/reconnecting board runner."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.board_live import BoardLiveRunner


def wire(seq, ms, drops=0, p=0, m=0, u=0, metres=3.0, valid=1,
         alarm=0, armed=1, degraded=0, fallback=0):
    value = "nan" if not valid else "{:.3f}".format(metres)
    return (
        "S,{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
            seq, ms, p, m, u, value, valid, alarm, armed, degraded,
            fallback, drops
        )
    ).encode("ascii")


class FakeClock:
    def __init__(self, start=100.0):
        self.value = float(start)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


class FakeSerial:
    def __init__(self, clock, events):
        self.clock = clock
        self.events = list(events)
        self.closed = False

    def readline(self):
        if not self.events:
            raise OSError("simulated end/disconnect")
        delay, payload = self.events.pop(0)
        self.clock.advance(delay)
        if isinstance(payload, BaseException):
            raise payload
        return payload

    def close(self):
        self.closed = True


class Factory:
    def __init__(self, clock, connections):
        self.clock = clock
        self.connections = [list(x) for x in connections]
        self.opens = 0

    def __call__(self, port, baudrate, timeout):
        del port, baudrate, timeout
        if not self.connections:
            raise OSError("no more simulated connections")
        self.opens += 1
        return FakeSerial(self.clock, self.connections.pop(0))


def run():
    clock = FakeClock()
    connections = [
        [
            (0.010, wire(0, 60000)),
            (0.100, wire(1, 60100, p=1)),
            (0.100, OSError("USB unplug")),
        ],
        [
            (0.210, wire(4, 60400, drops=2, m=1)),
            (0.100, b"garbage\n"),
            (0.100, wire(5, 60500, drops=2, u=1, metres=1.2)),
            (0.100, OSError("board reset/re-enumeration")),
        ],
        [
            (0.250, wire(0, 120, drops=0)),
            (0.100, wire(1, 220, drops=0, degraded=1, valid=0)),
        ],
    ]
    factory = Factory(clock, connections)

    with tempfile.TemporaryDirectory() as td:
        raw_log = Path(td) / "raw.jsonl"
        parsed_log = Path(td) / "parsed.jsonl"
        statuses = []
        runner = BoardLiveRunner(
            port="SIM",
            serial_factory=factory,
            clock=clock,
            wall_clock=lambda: 1700000000.0 + clock(),
            sleep=lambda seconds: clock.advance(seconds),
            reconnect_delay=0.050,
            raw_log=raw_log,
            parsed_log=parsed_log,
            status_interval=0.0,
            status_callback=statuses.append,
        )
        final = runner.run(max_samples=6, max_connect_attempts=4)
        raw_rows = [json.loads(x) for x in raw_log.read_text().splitlines()]
        parsed_rows = [json.loads(x) for x in parsed_log.read_text().splitlines()]

    checks = {
        "accepted_six_samples": final["samples"] == 6,
        "two_disconnects_reconnected": final["disconnects"] == 2 and factory.opens == 3,
        "gap_detected_across_reconnect": final["sequence_gaps"] == 2,
        "board_drop_counter_preserved": final["board_reported_drops"] == 2,
        "malformed_line_rejected_without_stopping": final["transport_rejected"] == 1,
        "board_reset_started_new_session": final["reboots"] == 1 and final["session"] == "uno-r4-0001",
        "raw_log_keeps_rejected_line": len(raw_rows) == 7 and any(not x["accepted"] for x in raw_rows),
        "parsed_log_only_keeps_accepted_samples": len(parsed_rows) == 6,
        "degraded_sample_visible": parsed_rows[-1]["degraded"] is True and parsed_rows[-1]["range_valid"] is False,
        "health_status_emitted": len(statuses) > 0,
    }
    return {
        "scope": "deterministic host-side Rev-F serial runner simulation; no physical USB, UNO R4 or sensor measurements",
        "checks": checks,
        "passed": all(checks.values()),
        "final_health": final,
        "connection_opens": factory.opens,
        "raw_records": len(raw_rows),
        "parsed_records": len(parsed_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/board_live_simulation.json")
    args = parser.parse_args()
    result = run()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
