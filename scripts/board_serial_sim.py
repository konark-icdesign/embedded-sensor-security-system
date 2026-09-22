"""Deterministic Rev-E simulation for the UNO R4 -> HP serial ingress layer."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.board_serial import BoardPacketError, BoardSerialAdapter


def wire(seq, ms, drops=0, p=0, m=0, u=0, metres=3.0, valid=1,
         alarm=0, armed=1, degraded=0, fallback=0):
    value = "nan" if not valid else f"{metres:.3f}"
    return f"S,{seq},{ms},{p},{m},{u},{value},{valid},{alarm},{armed},{degraded},{fallback},{drops}"


def run():
    checks = {}
    trace = []
    a = BoardSerialAdapter()
    base_ms = 60000
    base_host = 100.0
    jitter = [0.012, 0.018, 0.010, 0.021, 0.014]

    samples = []
    for i in range(20):
        s = a.ingest(wire(i, base_ms + 100 * i), base_host + .1 * i + jitter[i % len(jitter)])
        samples.append(s)
        trace.append(s.as_dict())
    cadence = [round(samples[i].captured - samples[i-1].captured, 9) for i in range(1, len(samples))]
    checks["normal_100ms_capture_cadence"] = all(abs(v - .1) <= .005 for v in cadence)
    checks["arrival_jitter_not_copied_into_sensor_clock"] = max(cadence) - min(cadence) <= .005

    s = a.ingest(wire(22, base_ms + 2200, drops=2, p=1, m=1, u=1, metres=1.2),
                 base_host + 2.2 + .019)
    trace.append(s.as_dict())
    checks["sequence_gap_detected"] = s.missing_before == 2
    checks["board_drop_counter_correlates"] = s.board_reported_drops_delta == 2
    checks["physical_flags_mapped"] = s.room_physical() == {"P": True, "M": True, "U": True, "fault": False}

    old_session = s.session
    s = a.ingest(wire(27, base_ms + 2700, drops=6), base_host + 2.7 + .020)
    trace.append(s.as_dict())
    checks["usb_reconnect_same_session"] = s.session == old_session
    checks["usb_reconnect_missing_samples_visible"] = s.missing_before == 4

    before_reboot = s.session
    s = a.ingest(wire(0, 120, drops=0), base_host + 3.05)
    trace.append(s.as_dict())
    checks["board_reboot_new_session"] = s.session != before_reboot and a.stats()["reboots"] == 1
    checks["reboot_does_not_invent_gap"] = s.missing_before == 0

    rejected = 0
    for bad in [
        "garbage",
        "S,1,220,2,0,0,3.0,1,0,1,0,0,0",
        wire(0, 220),
    ]:
        try:
            a.ingest(bad, base_host + 3.20)
        except BoardPacketError:
            rejected += 1
    checks["malformed_and_duplicate_rejected"] = rejected == 3

    w = BoardSerialAdapter("wrap")
    x0 = w.ingest(wire(0xFFFFFFFE, 0xFFFFFF00), 500.010)
    x1 = w.ingest(wire(1, 0x0000002C), 500.310)
    checks["uint32_wrap_preserves_session"] = x0.session == x1.session and w.stats()["reboots"] == 0
    checks["uint32_wrap_time_monotonic"] = x1.captured > x0.captured

    return {
        "scope": "deterministic host-side simulation of UNO R4 ASCII sensor packets; no physical USB or sensor measurements",
        "checks": checks,
        "passed": all(checks.values()),
        "stats": a.stats(),
        "wrap_stats": w.stats(),
        "trace_count": len(trace),
        "normal_cadence_seconds": {"min": min(cadence), "max": max(cadence)},
        "last_pre_reboot_sample": trace[-2],
        "first_post_reboot_sample": trace[-1],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/board_serial_simulation.json")
    args = parser.parse_args()
    result = run()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "stats": result["stats"]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
