# First physical bench measurement

This is the next project milestone after the scope reset. It is intentionally
small: measure the existing UNO R4 -> HP serial path before changing more
firmware, fusion logic or host architecture.

No physical result is recorded in this document yet.

## What the capture records

The bounded bench command uses the existing Rev-F transport and stores:

- `board_raw.jsonl` — every received packet line, including rejected lines;
- `board_samples.jsonl` — validated and timestamp-mapped board samples;
- `health.jsonl` — periodic runner state including disconnects/timeouts/gaps;
- `metadata.json` — requested duration, requested/resolved ports, host/Python version, Git revision/dirty state and UTC run times;
- `bench_summary.json` — timing/drop/reboot/sensor-health measurements;
- `bench_report.txt` — compact human-readable measurements with no invented PASS/FAIL threshold;
- `capture_integrity.json` — byte counts and SHA-256 hashes for the raw, parsed, health, metadata, summary and report files.

The summary and text report deliberately have no invented PASS threshold.
`bench_report.txt` is intended for quick bench review; `bench_summary.json`
remains the machine-readable source for detailed analysis.

## Metrics

The analyzer reports:

- observed sample rate;
- all host inter-arrival gaps;
- normal contiguous board period;
- normal contiguous host arrival period;
- transport interval error = host interval - board interval;
- mapped transport latency distribution;
- mapped capture timestamps that move backward;
- negative mapped latency, where capture time lands after host arrival;
- sequence gaps;
- board-reported serial drops;
- board sessions/reboots;
- invalid/degraded range samples;
- when a reference distance is supplied: measured range, signed bias, absolute error and absolute percentage-error distributions;
- PIR/radar/near activity counts;
- rejected raw packets.

Normal cadence statistics exclude known sequence gaps and session changes. This
prevents a USB outage or reboot from being averaged into the nominal 100 ms
sample period.

## Preflight

The normal bench command now runs preflight automatically before creating a
timestamped capture directory. It checks that pyserial can enumerate ports, that
the requested/automatic port can be resolved, that the bench output root is
writable and whether the Git working tree is dirty.

To inspect those checks without starting a capture:

```text
python scripts/preflight_board_bench.py --port auto
```

Add `--json` for a machine-readable report. A dirty working tree is a warning,
not a hard failure, because the capture metadata already records
`git_dirty=true`. Missing/ambiguous ports and an unwritable output root are hard
failures. The preflight does not open the serial port or claim that hardware is
working; the bounded capture remains the actual transport test.

## Trial 1 — steady USB

Connect the flashed UNO R4 to the HP and leave it untouched for 60 seconds.

```text
python scripts/run_board_bench.py --port auto --seconds 60 --label usb-idle
```

If automatic selection is ambiguous, use the actual COM/device name. Connection
failures are retained in the runtime health record, including the last error and
number of connection attempts. A zero-sample run now prints the concrete reason
when possible: port-selection/open failure, rejected non-UNO serial traffic, or
a port that opened but produced no valid telemetry.

Close Arduino Serial Monitor before starting the capture because only one
process should own the serial port.

Do not deliberately unplug USB during this first run. The purpose is to measure
the ordinary cadence and transport latency distribution. Check `metadata.json`
afterward: `resolved_ports_seen` should identify the actual COM/device path used
rather than leaving the evidence labelled only as `auto`. The metadata also
keeps the preflight port inventory so the device list immediately before the run
is preserved. Also confirm
`git_revision` identifies the code used for the run and `git_dirty` is false
for a reproducible baseline capture. `capture_integrity.json` is written last;
if an evidence file is later edited, its stored SHA-256 will no longer match.

Verify a capture before analysis, archiving or transfer:

```text
python scripts/verify_board_bench.py results/bench/<capture>
```

The command exits successfully only when every file recorded by
`capture_integrity.json` is present with the expected byte count and SHA-256.
It also rejects manifest filenames that try to escape the capture directory.

## Trial 2 — reconnect

Run a separate capture for 90 seconds:

```text
python scripts/run_board_bench.py --port auto --seconds 90 --label usb-reconnect
```

After approximately 30 seconds, unplug and reconnect the UNO USB once. Do not
edit the resulting files. The run should show whether the OS re-enumerates the
port, whether the board restarts, how long the sample gap lasts and whether
sequence/serial-drop accounting agrees.

## Trial 3 — one physical sensor

After the serial-only path is understood, attach one sensor already intended for
the build. For ultrasonic testing, use separate static-distance captures rather
than moving the target continuously, for example:

```text
python scripts/run_board_bench.py --port auto --seconds 30 --label range-static-1m --reference-distance-m 1.0 --setup-note "flat target, tape measured"
```

Use `--reference-distance-m` for the actual tape-measured distance so the
ground-truth value is stored inside the capture metadata instead of in a
separate note. `--setup-note` can hold a short physical setup description.
Repeat at other useful distances and include an invalid/no-echo condition
(without a reference distance when there is no target). For a referenced static
trial, only samples marked `range_valid` contribute to the accuracy statistics;
the report shows signed error, absolute error and percentage error without
inventing an acceptance limit. Do not tune the fusion threshold from these
captures; this trial is for the sensor/firmware path.

## Comparing multiple static-distance trials

After collecting at least two referenced range captures, characterize them
together:

```text
python scripts/summarize_range_trials.py \
  results/bench/<capture-0p5m> \
  results/bench/<capture-1m> \
  results/bench/<capture-2m> \
  --output-json results/bench/range_characterization.json \
  --output-csv results/bench/range_characterization.csv
```

Every input capture is integrity-verified before analysis. The tool requires
`metadata.json`, `board_samples.jsonl` and `board_raw.jsonl` to be covered
by that verified manifest, then recomputes each trial from the stored evidence
and its stored tape reference. Trials are sorted by reference distance. JSON and
CSV keep the per-distance valid fraction, measured mean/median, signed bias,
absolute-error statistics, percentage-error statistics, sequence gaps, board
drops and source revision. It deliberately does not collapse different
distances into one headline accuracy number.

## Reanalyzing an existing capture

```text
python scripts/analyze_board_bench.py \
  --parsed results/bench/<capture>/board_samples.jsonl \
  --raw results/bench/<capture>/board_raw.jsonl \
  --output results/bench/<capture>/bench_summary_recomputed.json
```

When `metadata.json` beside the parsed capture contains
`reference_distance_m`, reanalysis uses it automatically. An explicit
`--reference-distance-m` is still supported for older captures, but a value
that conflicts with stored metadata is rejected instead of silently changing
the physical ground truth.

## Decision after the measurements

Only after these runs should implementation change. Examples:

- real sequence loss -> investigate firmware/USB/host scheduling;
- large latency tail -> revisit buffering/freshness assumptions;
- negative or backward mapped capture time -> inspect the Rev-E clock mapper before media fusion;
- false invalid ranges -> inspect ultrasonic electrical/firmware path;
- board restart on reconnect -> verify intended session handling;
- stable serial path -> move to microphone capture and then camera.

The purpose is to make the next code change answer a measured problem rather
than create another synthetic subsystem.
