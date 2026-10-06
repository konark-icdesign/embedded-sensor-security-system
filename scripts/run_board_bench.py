"""Run a bounded UNO R4 -> HP serial bench capture and summarize it."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bench_analysis import analyze_board_bench_files
from src.board_live import BoardLiveRunner, format_health


_LABEL = re.compile(r"^[A-Za-z0-9_-]+$")


def _write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="auto")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--label", default="usb-idle")
    parser.add_argument("--output-root", default="results/bench")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if not _LABEL.fullmatch(args.label):
        parser.error("--label may contain only letters, digits, '_' and '-'")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root) / (args.label + "-" + stamp)
    if output.exists():
        parser.error("capture directory already exists: {}".format(output))
    output.mkdir(parents=True)

    raw_path = output / "board_raw.jsonl"
    parsed_path = output / "board_samples.jsonl"
    health_path = output / "health.jsonl"
    metadata_path = output / "metadata.json"
    summary_path = output / "bench_summary.json"

    started_wall = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    health_handle = health_path.open("a", encoding="utf-8")

    def status(status_value):
        record = dict(status_value)
        record["host_wall_time"] = time.time()
        record["host_monotonic"] = time.monotonic()
        health_handle.write(json.dumps(record, sort_keys=True) + "\n")
        health_handle.flush()
        print(format_health(status_value), flush=True)

    stop_event = threading.Event()
    timer = threading.Timer(args.seconds, stop_event.set)
    timer.daemon = True

    runner = BoardLiveRunner(
        port=args.port,
        baudrate=args.baud,
        raw_log=raw_path,
        parsed_log=parsed_path,
        status_callback=status,
    )

    print(
        "BENCH capture={} duration={:.1f}s port={}".format(
            output, args.seconds, args.port
        ),
        flush=True,
    )

    timer.start()
    try:
        health = runner.run(stop_event=stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        health = runner.health_snapshot()
        print("Stopped by user.", flush=True)
    finally:
        timer.cancel()
        health_handle.close()

    ended_wall = datetime.now(timezone.utc)
    metadata = {
        "label": args.label,
        "requested_seconds": args.seconds,
        "port_argument": args.port,
        "resolved_ports_seen": health.get("ports_seen", []),
        "baud": args.baud,
        "host_platform": platform.platform(),
        "python_version": platform.python_version(),
        "started_utc": started_wall.isoformat(),
        "ended_utc": ended_wall.isoformat(),
        "host_elapsed_seconds": time.monotonic() - started_monotonic,
        "claim_boundary": (
            "This directory is a capture artifact. It is physical bench "
            "evidence only if the command was actually run with the stated "
            "hardware connected."
        ),
    }
    _write_json(metadata_path, metadata)

    analysis = analyze_board_bench_files(parsed_path, raw_path)
    summary = {
        "metadata": metadata,
        "runtime_health": health,
        "analysis": analysis,
    }
    _write_json(summary_path, summary)

    print(
        "SUMMARY samples={} gaps={} drops={} sessions={} output={}".format(
            analysis["samples"],
            analysis["sequence_gaps"],
            analysis["board_reported_drops"],
            analysis["session_count"],
            summary_path,
        ),
        flush=True,
    )

    if analysis["samples"] == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
