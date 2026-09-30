# Rev-F live board runner

Rev-F turns the Rev-E packet adapter into a host program that is ready for an actual UNO R4 USB bench run. It still does **not** claim that the UNO, USB reconnect behavior, sensors or HP t640 have been physically measured.

## What changed

`src/board_live.py` adds the transport layer around `BoardSerialAdapter`:

- explicit serial port or conservative automatic discovery;
- reconnect after an OS/USB read failure;
- preservation of the current board session when counters continue after reconnect;
- normal Rev-E reboot detection when sequence and `millis()` actually restart;
- append-only raw JSONL logging, including malformed/rejected lines;
- append-only parsed JSONL logging for accepted `BoardSample` objects;
- live health state for packet rate, latency, sequence gaps, board-reported drops, reboots and sensor-health flags.

The runner intentionally does not guess among multiple ambiguous serial ports. If more than one port is present and no unique Arduino/UNO/Renesas descriptor is found, pass the device explicitly.

## Live command

Install dependencies and connect the UNO R4 by USB.

Windows example:

```text
python scripts/run_board_live.py --port COM7
```

Linux example:

```text
python scripts/run_board_live.py --port /dev/ttyACM0
```

Automatic discovery is available:

```text
python scripts/run_board_live.py --port auto
```

Default evidence paths are:

```text
results/live/board_raw.jsonl
results/live/board_samples.jsonl
```

Those files are intentionally ignored by Git because a real bench capture can become large and should be reviewed before any evidence is committed.

## Health output

A normal status line has this shape:

```text
BOARD connected port=COM7 session=uno-r4-0000 samples=123 rate=10.01 Hz latency=18.0 ms gaps=0 board_drops=0 reboots=0 rejected=0 P=False M=True U=False range_valid=True degraded=False
```

A USB unplug causes a disconnected state and a reconnect loop. If the board keeps counting after re-enumeration, Rev-E gap accounting remains in the same session. If the board restarts and both counters reset, the adapter creates a new session.

## Deterministic validation

`scripts/board_live_sim.py` drives the real runner using fake serial connections. It injects:

1. normal packets;
2. USB disconnect and reconnect;
3. a forward sequence gap plus board `serial_drops`;
4. a malformed line that must be logged and rejected without stopping;
5. a second disconnect followed by a board reboot;
6. a degraded/invalid-range sample.

The focused unit tests additionally exercise an arrival-delay violation against Rev-E's 0.5 s freshness gate and serial read timeouts.

The committed/CI simulation is software evidence only. The next physical step is to connect the real UNO R4 to the HP t640, identify the actual port, record a short capture, unplug/replug USB once, and inspect the raw/parsed logs before making any hardware claim.
