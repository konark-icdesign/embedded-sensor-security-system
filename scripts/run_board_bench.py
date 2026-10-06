"""Run a bounded UNO R4 -> HP serial bench capture and summarize it."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
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


def _source_state():
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"git_revision": None, "git_dirty": None}
    return {"git_revision": revision or None, "git_dirty": dirty}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_integrity_manifest(path, files):
    records = {}
    for file_path in files:
        file_path = Path(file_path)
        if not file_path.exists():
            continue
        records[file_path.name] = {
            "bytes": file_path.stat().st_size,
            "sha256": _sha256(file_path),
        }
    manifest = {"algorithm": "sha256", "files": records}
    _write_json(path, manifest)
    return manifest


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
    integrity_path = output / "capture_integrity.json"

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
    source_state = _source_state()
    metadata = {
        "label": args.label,
        "requested_seconds": args.seconds,
        "port_argument": args.port,
        "resolved_ports_seen": health.get("ports_seen", []),
        "baud": args.baud,
        "host_platform": platform.platform(),
        "python_version": platform.python_version(),
        "git_revision": source_state["git_revision"],
        "git_dirty": source_state["git_dirty"],
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
    _write_integrity_manifest(
        integrity_path,
        [raw_path, parsed_path, health_path, metadata_path, summary_path],
    )

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
