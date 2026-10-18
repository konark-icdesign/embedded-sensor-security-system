"""Aggregate verified static-distance bench captures for characterization."""

import csv
import io
import json
from pathlib import Path

from src.bench_analysis import analyze_board_bench_files


def _load_json_object(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("{} not found".format(label)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("{} is not valid JSON".format(label)) from exc
    if not isinstance(value, dict):
        raise ValueError("{} is not a JSON object".format(label))
    return value


def characterize_capture(capture_dir, integrity_result):
    capture_dir = Path(capture_dir)
    if not integrity_result.get("ok", False):
        raise ValueError(
            "capture integrity verification failed: {}".format(capture_dir)
        )

    metadata = _load_json_object(
        capture_dir / "metadata.json",
        "metadata.json",
    )
    reference = metadata.get("reference_distance_m")
    if reference is None:
        raise ValueError(
            "capture has no reference_distance_m: {}".format(capture_dir)
        )
    try:
        reference = float(reference)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "reference_distance_m is not numeric: {}".format(capture_dir)
        ) from exc
    if reference <= 0:
        raise ValueError(
            "reference_distance_m must be positive: {}".format(capture_dir)
        )

    analysis = analyze_board_bench_files(
        capture_dir / "board_samples.jsonl",
        capture_dir / "board_raw.jsonl",
        reference_distance_m=reference,
    )
    accuracy = analysis["range_reference"]
    measured = accuracy["measured_range_m"]
    signed = accuracy["signed_error_m"]
    absolute = accuracy["absolute_error_m"]
    percent = accuracy["absolute_error_percent"]
    total = int(analysis.get("samples", 0))
    valid = int(accuracy.get("valid_measurements", 0))

    return {
        "capture": str(capture_dir),
        "label": metadata.get("label"),
        "reference_distance_m": reference,
        "setup_note": metadata.get("setup_note"),
        "git_revision": metadata.get("git_revision"),
        "git_dirty": metadata.get("git_dirty"),
        "samples": total,
        "valid_measurements": valid,
        "valid_fraction": (valid / total) if total else None,
        "measured_mean_m": measured.get("mean"),
        "measured_median_m": measured.get("median"),
        "signed_error_mean_m": signed.get("mean"),
        "signed_error_median_m": signed.get("median"),
        "absolute_error_mean_m": absolute.get("mean"),
        "absolute_error_median_m": absolute.get("median"),
        "absolute_error_p95_m": absolute.get("p95"),
        "absolute_error_max_m": absolute.get("max"),
        "absolute_error_percent_mean": percent.get("mean"),
        "absolute_error_percent_median": percent.get("median"),
        "absolute_error_percent_p95": percent.get("p95"),
        "absolute_error_percent_max": percent.get("max"),
        "sequence_gaps": analysis.get("sequence_gaps", 0),
        "board_reported_drops": analysis.get("board_reported_drops", 0),
        "range_invalid": (
            analysis.get("sensor_observations", {}).get("range_invalid", 0)
        ),
        "integrity_ok": True,
    }


def build_characterization(captures):
    captures = list(captures)
    trials = sorted(
        captures,
        key=lambda row: (
            float(row["reference_distance_m"]),
            str(row.get("capture", "")),
        ),
    )
    revisions = sorted({
        str(row["git_revision"])
        for row in trials
        if row.get("git_revision")
    })
    references = [float(row["reference_distance_m"]) for row in trials]
    return {
        "scope": (
            "verified static-distance bench captures; per-trial measurements "
            "are reported without an invented acceptance threshold"
        ),
        "trial_count": len(trials),
        "reference_distance_min_m": min(references) if references else None,
        "reference_distance_max_m": max(references) if references else None,
        "source_revisions": revisions,
        "dirty_capture_count": sum(
            row.get("git_dirty") is True for row in trials
        ),
        "trials": trials,
    }


_CSV_FIELDS = [
    "capture",
    "label",
    "reference_distance_m",
    "samples",
    "valid_measurements",
    "valid_fraction",
    "measured_mean_m",
    "measured_median_m",
    "signed_error_mean_m",
    "signed_error_median_m",
    "absolute_error_mean_m",
    "absolute_error_median_m",
    "absolute_error_p95_m",
    "absolute_error_max_m",
    "absolute_error_percent_mean",
    "absolute_error_percent_median",
    "absolute_error_percent_p95",
    "absolute_error_percent_max",
    "range_invalid",
    "sequence_gaps",
    "board_reported_drops",
    "git_revision",
    "git_dirty",
    "setup_note",
]


def characterization_csv(result):
    handle = io.StringIO()
    writer = csv.DictWriter(
        handle,
        fieldnames=_CSV_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in result.get("trials", []):
        writer.writerow(row)
    return handle.getvalue()
