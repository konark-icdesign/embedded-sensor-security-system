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
- `metadata.json` — requested duration, port argument and UTC run times;
- `bench_summary.json` — timing/drop/reboot/sensor-health measurements.

The summary deliberately has no invented PASS threshold.

## Metrics

The analyzer reports:

- observed sample rate;
- all host inter-arrival gaps;
- normal contiguous board period;
- normal contiguous host arrival period;
- transport interval error = host interval - board interval;
- mapped transport latency distribution;
- sequence gaps;
- board-reported serial drops;
- board sessions/reboots;
- invalid/degraded range samples;
- PIR/radar/near activity counts;
- rejected raw packets.

Normal cadence statistics exclude known sequence gaps and session changes. This
prevents a USB outage or reboot from being averaged into the nominal 100 ms
sample period.

## Trial 1 — steady USB

Connect the flashed UNO R4 to the HP and leave it untouched for 60 seconds.

```text
python scripts/run_board_bench.py --port auto --seconds 60 --label usb-idle
```

If automatic selection is ambiguous, use the actual COM/device name.

Do not deliberately unplug USB during this first run. The purpose is to measure
the ordinary cadence and transport latency distribution.

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
python scripts/run_board_bench.py --port auto --seconds 30 --label range-static-1m
```

Record the actual tape-measured distance separately. Repeat at other useful
distances and include an invalid/no-echo condition. Do not tune the fusion
threshold from these captures; this trial is for the sensor/firmware path.

## Reanalyzing an existing capture

```text
python scripts/analyze_board_bench.py \
  --parsed results/bench/<capture>/board_samples.jsonl \
  --raw results/bench/<capture>/board_raw.jsonl \
  --output results/bench/<capture>/bench_summary_recomputed.json
```

## Decision after the measurements

Only after these runs should implementation change. Examples:

- real sequence loss -> investigate firmware/USB/host scheduling;
- large latency tail -> revisit buffering/freshness assumptions;
- false invalid ranges -> inspect ultrasonic electrical/firmware path;
- board restart on reconnect -> verify intended session handling;
- stable serial path -> move to microphone capture and then camera.

The purpose is to make the next code change answer a measured problem rather
than create another synthetic subsystem.
