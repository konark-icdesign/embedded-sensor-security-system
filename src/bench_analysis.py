"""Analysis helpers for the first physical UNO R4 -> HP bench capture.

The analyzer consumes Rev-F JSONL evidence. It does not decide whether hardware
"passed"; it reports timing, gaps, drops, reboots and sensor-health observations
so acceptance limits can be based on measured data instead of invented values.
"""

import json
import math
from pathlib import Path
from statistics import fmean, median


def load_jsonl(path):
    path = Path(path)
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "{}:{} is not valid JSON".format(path, line_number)
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    "{}:{} is not a JSON object".format(path, line_number)
                )
            rows.append(row)
    return rows


def _percentile(values, percentile):
    values = sorted(float(x) for x in values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * float(percentile) / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] + fraction * (values[upper] - values[lower])


def _stats(values):
    values = [float(x) for x in values if math.isfinite(float(x))]
    if not values:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "mean": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "count": len(values),
        "min": min(values),
        "median": median(values),
        "mean": fmean(values),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
        "max": max(values),
    }


def _bool_count(rows, field, value=True):
    return sum(bool(row.get(field, False)) is bool(value) for row in rows)


def analyze_board_bench(parsed_rows, raw_rows=None):
    parsed_rows = list(parsed_rows)
    raw_rows = None if raw_rows is None else list(raw_rows)

    sessions = []
    for row in parsed_rows:
        session = row.get("session")
        if session is not None and session not in sessions:
            sessions.append(session)

    latencies_ms = []
    all_arrival_intervals_ms = []
    normal_arrival_period_ms = []
    normal_board_period_ms = []
    transport_interval_error_ms = []
    arrival_nonmonotonic = 0
    board_nonmonotonic = 0

    for row in parsed_rows:
        latency = row.get("latency_seconds")
        if latency is None:
            arrival = row.get("arrival")
            captured = row.get("captured")
            if arrival is not None and captured is not None:
                latency = float(arrival) - float(captured)
        if latency is not None and math.isfinite(float(latency)):
            latencies_ms.append(float(latency) * 1000.0)

    for previous, current in zip(parsed_rows, parsed_rows[1:]):
        previous_arrival = float(previous["arrival"])
        current_arrival = float(current["arrival"])
        arrival_delta_ms = (current_arrival - previous_arrival) * 1000.0
        all_arrival_intervals_ms.append(arrival_delta_ms)
        if arrival_delta_ms <= 0:
            arrival_nonmonotonic += 1

        same_session = previous.get("session") == current.get("session")
        if not same_session:
            continue

        previous_ms = int(previous["board_millis_unwrapped"])
        current_ms = int(current["board_millis_unwrapped"])
        board_delta_ms = float(current_ms - previous_ms)
        if board_delta_ms <= 0:
            board_nonmonotonic += 1
            continue

        sequence_delta = (
            int(current["sequence_unwrapped"])
            - int(previous["sequence_unwrapped"])
        )
        no_gap = int(current.get("missing_before", 0)) == 0
        if sequence_delta == 1 and no_gap:
            normal_board_period_ms.append(board_delta_ms)
            normal_arrival_period_ms.append(arrival_delta_ms)
            transport_interval_error_ms.append(
                arrival_delta_ms - board_delta_ms
            )

    sequence_gaps = sum(
        max(0, int(row.get("missing_before", 0))) for row in parsed_rows
    )
    board_reported_drops = sum(
        max(0, int(row.get("board_reported_drops_delta", 0)))
        for row in parsed_rows
    )

    if parsed_rows:
        start_arrival = float(parsed_rows[0]["arrival"])
        end_arrival = float(parsed_rows[-1]["arrival"])
        capture_duration_seconds = max(0.0, end_arrival - start_arrival)
        observed_rate_hz = (
            (len(parsed_rows) - 1) / capture_duration_seconds
            if len(parsed_rows) > 1 and capture_duration_seconds > 0
            else None
        )
    else:
        capture_duration_seconds = 0.0
        observed_rate_hz = None

    raw_summary = None
    if raw_rows is not None:
        raw_summary = {
            "records": len(raw_rows),
            "accepted": sum(bool(row.get("accepted", False)) for row in raw_rows),
            "rejected": sum(not bool(row.get("accepted", False)) for row in raw_rows),
        }

    normal_error_abs = [abs(x) for x in transport_interval_error_ms]

    return {
        "scope": (
            "measurement summary from Rev-F JSONL logs; interpretation depends "
            "on whether the supplied logs came from a real bench or a simulation"
        ),
        "samples": len(parsed_rows),
        "sessions": sessions,
        "session_count": len(sessions),
        "reboots_observed": max(0, len(sessions) - 1),
        "capture_duration_seconds": capture_duration_seconds,
        "observed_sample_rate_hz": observed_rate_hz,
        "sequence_gaps": sequence_gaps,
        "board_reported_drops": board_reported_drops,
        "arrival_nonmonotonic_intervals": arrival_nonmonotonic,
        "board_nonmonotonic_intervals": board_nonmonotonic,
        "transport_latency_ms": _stats(latencies_ms),
        "all_arrival_interval_ms": _stats(all_arrival_intervals_ms),
        "normal_contiguous_board_period_ms": _stats(normal_board_period_ms),
        "normal_contiguous_arrival_period_ms": _stats(normal_arrival_period_ms),
        "normal_transport_interval_error_ms": _stats(
            transport_interval_error_ms
        ),
        "normal_transport_interval_abs_error_ms": _stats(normal_error_abs),
        "sensor_observations": {
            "range_valid": _bool_count(parsed_rows, "range_valid", True),
            "range_invalid": _bool_count(parsed_rows, "range_valid", False),
            "degraded": _bool_count(parsed_rows, "degraded", True),
            "pir_active": _bool_count(parsed_rows, "pir", True),
            "radar_active": _bool_count(parsed_rows, "radar", True),
            "near_active": _bool_count(parsed_rows, "near", True),
            "fallback_alarm": _bool_count(
                parsed_rows, "fallback_alarm", True
            ),
        },
        "raw_transport": raw_summary,
    }


def analyze_board_bench_files(parsed_path, raw_path=None):
    parsed = load_jsonl(parsed_path)
    raw = None if raw_path is None else load_jsonl(raw_path)
    return analyze_board_bench(parsed, raw)
