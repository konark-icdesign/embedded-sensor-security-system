"""Human-readable report for one measured board bench capture.

This formatter deliberately reports observations without inventing acceptance
thresholds or converting them into PASS/FAIL decisions.
"""


def _number(value, digits=3):
    if value is None:
        return "n/a"
    return ("{:.%df}" % digits).format(float(value))


def _stat_line(label, stats, unit=""):
    stats = stats or {}
    suffix = (" " + unit) if unit else ""
    return (
        "{label}: count={count} median={median}{suffix} "
        "p95={p95}{suffix} p99={p99}{suffix} max={maxv}{suffix}"
    ).format(
        label=label,
        count=stats.get("count", 0),
        median=_number(stats.get("median")),
        p95=_number(stats.get("p95")),
        p99=_number(stats.get("p99")),
        maxv=_number(stats.get("max")),
        suffix=suffix,
    )


def format_bench_report(summary):
    metadata = summary.get("metadata", {})
    health = summary.get("runtime_health", {})
    analysis = summary.get("analysis", {})
    sensors = analysis.get("sensor_observations", {})
    range_reference = analysis.get("range_reference")
    raw = analysis.get("raw_transport") or {}

    lines = [
        "UNO R4 -> host bench measurement report",
        "Interpretation: measured observations only; no PASS/FAIL threshold is applied.",
        "",
        "Capture",
        "  label: {}".format(metadata.get("label", "n/a")),
        "  started_utc: {}".format(metadata.get("started_utc", "n/a")),
        "  ended_utc: {}".format(metadata.get("ended_utc", "n/a")),
        "  requested_port: {}".format(metadata.get("port_argument", "n/a")),
        "  resolved_ports_seen: {}".format(
            ", ".join(metadata.get("resolved_ports_seen", [])) or "none"
        ),
        "  git_revision: {}".format(metadata.get("git_revision") or "n/a"),
        "  git_dirty: {}".format(metadata.get("git_dirty")),
        "  reference_distance_m: {}".format(
            _number(metadata.get("reference_distance_m"))
        ),
        "  setup_note: {}".format(metadata.get("setup_note") or "n/a"),
        "",
        "Transport",
        "  samples: {}".format(analysis.get("samples", 0)),
        "  capture_duration_seconds: {}".format(
            _number(analysis.get("capture_duration_seconds"))
        ),
        "  observed_sample_rate_hz: {}".format(
            _number(analysis.get("observed_sample_rate_hz"))
        ),
        "  sessions: {}".format(analysis.get("session_count", 0)),
        "  reboots_observed: {}".format(analysis.get("reboots_observed", 0)),
        "  sequence_gaps: {}".format(analysis.get("sequence_gaps", 0)),
        "  board_reported_drops: {}".format(
            analysis.get("board_reported_drops", 0)
        ),
        "  raw_records: {}".format(raw.get("records", "n/a")),
        "  raw_rejected: {}".format(raw.get("rejected", "n/a")),
        "",
        "Timing",
        "  " + _stat_line(
            "mapped_transport_latency",
            analysis.get("transport_latency_ms"),
            "ms",
        ),
        "  " + _stat_line(
            "normal_board_period",
            analysis.get("normal_contiguous_board_period_ms"),
            "ms",
        ),
        "  " + _stat_line(
            "normal_host_arrival_period",
            analysis.get("normal_contiguous_arrival_period_ms"),
            "ms",
        ),
        "  " + _stat_line(
            "normal_transport_interval_abs_error",
            analysis.get("normal_transport_interval_abs_error_ms"),
            "ms",
        ),
        "",
        "Clock integrity",
        "  arrival_nonmonotonic_intervals: {}".format(
            analysis.get("arrival_nonmonotonic_intervals", 0)
        ),
        "  mapped_capture_nonmonotonic_intervals: {}".format(
            analysis.get("mapped_capture_nonmonotonic_intervals", 0)
        ),
        "  board_nonmonotonic_intervals: {}".format(
            analysis.get("board_nonmonotonic_intervals", 0)
        ),
        "  negative_transport_latency_samples: {}".format(
            analysis.get("negative_transport_latency_samples", 0)
        ),
        "",
        "Sensor observations",
        "  range_valid: {}".format(sensors.get("range_valid", 0)),
        "  range_invalid: {}".format(sensors.get("range_invalid", 0)),
        "  degraded: {}".format(sensors.get("degraded", 0)),
        "  pir_active: {}".format(sensors.get("pir_active", 0)),
        "  radar_active: {}".format(sensors.get("radar_active", 0)),
        "  near_active: {}".format(sensors.get("near_active", 0)),
        "  fallback_alarm: {}".format(sensors.get("fallback_alarm", 0)),
        "",
    ]
    if range_reference is not None:
        lines.extend([
            "Range reference analysis",
            "  reference_distance_m: {}".format(
                _number(range_reference.get("reference_distance_m"))
            ),
            "  valid_measurements: {}".format(
                range_reference.get("valid_measurements", 0)
            ),
            "  " + _stat_line(
                "measured_range",
                range_reference.get("measured_range_m"),
                "m",
            ),
            "  " + _stat_line(
                "signed_error",
                range_reference.get("signed_error_m"),
                "m",
            ),
            "  signed_error_mean_m: {}".format(
                _number(
                    (range_reference.get("signed_error_m") or {}).get("mean")
                )
            ),
            "  " + _stat_line(
                "absolute_error",
                range_reference.get("absolute_error_m"),
                "m",
            ),
            "  " + _stat_line(
                "absolute_error_percent",
                range_reference.get("absolute_error_percent"),
                "%",
            ),
            "",
        ])
    lines.extend([
        "Runtime",
        "  connect_attempts: {}".format(health.get("connect_attempts", "n/a")),
        "  connection_errors: {}".format(
            health.get("connection_errors", "n/a")
        ),
        "  disconnects: {}".format(health.get("disconnects", "n/a")),
        "  timeouts: {}".format(health.get("timeouts", "n/a")),
        "  transport_rejected: {}".format(
            health.get("transport_rejected", "n/a")
        ),
        "",
        "Use the JSON evidence for detailed analysis. Set acceptance limits only",
        "after real measurements establish the expected hardware distribution.",
    ])
    return "\n".join(lines) + "\n"
