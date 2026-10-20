"""Run a bounded UNO R4 -> HP serial bench capture and summarize it."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bench_analysis import analyze_board_bench_files
from src.bench_preflight import format_preflight, run_preflight
from src.bench_report import format_bench_report
from src.board_live import BoardLiveRunner, format_health
from src.firmware_build_manifest import verify_manifest_artifacts


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


def _firmware_identity_state(health):
    identities = list(health.get("firmware_ids_seen", []))
    if not identities:
        return "missing"
    if len(identities) > 1:
        return "changed-during-capture"
    if identities[0] == "UNSTAMPED":
        return "unstamped"
    return "reported"


def _firmware_build_match_state(expected_build_id, reported_ids):
    if expected_build_id is None:
        return "not-requested"
    reported_ids = list(reported_ids or [])
    if not reported_ids:
        return "board-id-missing"
    if len(reported_ids) != 1:
        return "multiple-board-ids"
    if reported_ids[0] == expected_build_id:
        return "match"
    return "mismatch"


def _zero_sample_diagnostic(health):
    connection_error = health.get("last_connection_error")
    if connection_error:
        return "connection failed: {}".format(connection_error)
    rejected = int(health.get("transport_rejected", 0) or 0)
    if rejected:
        return (
            "{} serial line(s) were rejected; verify the selected device, "
            "UNO R4 firmware and baud rate"
        ).format(rejected)
    timeouts = int(health.get("timeouts", 0) or 0)
    if timeouts:
        return (
            "serial port opened but no valid telemetry arrived "
            "({} read timeout(s)); close Arduino Serial Monitor and verify "
            "the firmware is running"
        ).format(timeouts)
    return "no valid board telemetry was received"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="auto")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--label", default="usb-idle")
    parser.add_argument("--output-root", default="results/bench")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--reference-distance-m", type=float)
    parser.add_argument("--setup-note")
    parser.add_argument("--firmware-build-manifest")
    parser.add_argument("--firmware-artifact-dir")
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if not _LABEL.fullmatch(args.label):
        parser.error("--label may contain only letters, digits, '_' and '-'")
    if (
        args.reference_distance_m is not None
        and args.reference_distance_m <= 0
    ):
        parser.error("--reference-distance-m must be positive")
    if args.setup_note is not None and len(args.setup_note) > 500:
        parser.error("--setup-note must be 500 characters or fewer")
    if bool(args.firmware_build_manifest) != bool(args.firmware_artifact_dir):
        parser.error(
            "--firmware-build-manifest and --firmware-artifact-dir "
            "must be supplied together"
        )

    build_verification = None
    intended_build_id = None
    if args.firmware_build_manifest:
        try:
            build_verification = verify_manifest_artifacts(
                args.firmware_build_manifest,
                args.firmware_artifact_dir,
            )
        except ValueError as exc:
            parser.error(str(exc))
        if not build_verification["ok"]:
            parser.error(
                "compiled firmware artifacts do not match the build manifest"
            )
        intended_build_id = build_verification["firmware_build_id"]

    preflight = run_preflight(
        port=args.port,
        output_root=args.output_root,
        repo_root=ROOT,
    )
    print(format_preflight(preflight), flush=True)
    if not preflight["ok"]:
        for item in preflight["serial_ports"]:
            print(
                "PORT device={device} description={description} "
                "manufacturer={manufacturer} product={product}".format(**item),
                file=sys.stderr,
                flush=True,
            )
        raise SystemExit(2)

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
    report_path = output / "bench_report.txt"
    integrity_path = output / "capture_integrity.json"
    firmware_manifest_copy = None
    if args.firmware_build_manifest:
        firmware_manifest_copy = output / "firmware_build_manifest.json"
        shutil.copy2(args.firmware_build_manifest, firmware_manifest_copy)

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
    reported_firmware_ids = health.get("firmware_ids_seen", [])
    firmware_build_match_state = _firmware_build_match_state(
        intended_build_id,
        reported_firmware_ids,
    )
    metadata = {
        "label": args.label,
        "requested_seconds": args.seconds,
        "port_argument": args.port,
        "resolved_ports_seen": health.get("ports_seen", []),
        "reported_firmware_ids": reported_firmware_ids,
        "firmware_identity_state": _firmware_identity_state(health),
        "intended_firmware_build_id": intended_build_id,
        "firmware_build_match_state": firmware_build_match_state,
        "firmware_artifacts_verified_before_capture": (
            None if build_verification is None else True
        ),
        "firmware_build_manifest_sha256": (
            None
            if firmware_manifest_copy is None
            else _sha256(firmware_manifest_copy)
        ),
        "baud": args.baud,
        "reference_distance_m": args.reference_distance_m,
        "setup_note": args.setup_note,
        "host_platform": platform.platform(),
        "python_version": platform.python_version(),
        "preflight_selected_port": preflight["selected_port"],
        "preflight_serial_ports": preflight["serial_ports"],
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

    analysis = analyze_board_bench_files(
        parsed_path,
        raw_path,
        reference_distance_m=args.reference_distance_m,
    )
    summary = {
        "metadata": metadata,
        "runtime_health": health,
        "analysis": analysis,
    }
    _write_json(summary_path, summary)
    report_path.write_text(format_bench_report(summary), encoding="utf-8")
    integrity_files = [
        raw_path,
        parsed_path,
        health_path,
        metadata_path,
        summary_path,
        report_path,
    ]
    if firmware_manifest_copy is not None:
        integrity_files.append(firmware_manifest_copy)
    _write_integrity_manifest(
        integrity_path,
        integrity_files,
    )

    print(
        "SUMMARY samples={} gaps={} drops={} sessions={} output={}".format(
            analysis["samples"],
            analysis["sequence_gaps"],
            analysis["board_reported_drops"],
            analysis["session_count"],
            report_path,
        ),
        flush=True,
    )

    if analysis["samples"] == 0:
        print(
            "ERROR no valid board samples: {}".format(
                _zero_sample_diagnostic(health)
            ),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)

    if (
        intended_build_id is not None
        and firmware_build_match_state != "match"
    ):
        print(
            "ERROR firmware build provenance mismatch: expected={} "
            "reported={} state={}".format(
                intended_build_id,
                reported_firmware_ids,
                firmware_build_match_state,
            ),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(3)


if __name__ == "__main__":
    main()
