# Rev-E board-to-host serial ingress

Rev-E closes one software integration gap between the UNO R4 firmware and the HP-side incident pipeline. It does **not** claim a physical USB bench test. The input is the exact ASCII packet format already emitted by `firmware/night_security/night_security.ino`.

## Wire contract

```text
S,sequence,board_millis,pir_filtered,radar_filtered,near_filtered,range_metres,range_valid,alarm,armed,degraded,fallback_alarm,serial_drops
```

`src/board_serial.py` validates this packet, rejects malformed fields, unwraps the 32-bit sequence and `millis()` counters, detects sequence gaps, tracks the board's cumulative serial-drop counter, and maps board time onto one monotonic host acquisition clock.

The mapper deliberately does not replace acquisition time with USB arrival time. Arrival jitter is transport delay; the incident engine needs sensor timing. The first good packet creates an initial board-to-host offset. Later packets may reduce that offset when they arrive with less transport delay; this lower-envelope update removes first-packet latency bias while keeping capture time monotonic. The simulation found and corrected an earlier fixed-anchor version that could map a low-latency packet into the future.

## Reboot and reconnect rules

A missing group of sequence numbers with forward-running board time is treated as packet loss/reconnect. The session remains the same and the missing sample count is preserved.

If both sequence and `board_millis` move backwards by more than half the uint32 space, Rev-E treats that as a board restart and starts a new board session. A normal uint32 wrap is forward modulo arithmetic and does not create a false reboot.

A new board session must not be silently appended to an existing `IncidentJournal`: the existing journal contract already requires a separate session/clock after a reboot. The adapter exposes that boundary explicitly.

## Incident-pipeline mapping

Each accepted packet exposes fields ready for `RoomStream.push`:

- unwrapped sequence;
- mapped host-clock capture timestamp;
- host arrival timestamp;
- `P`, `M`, `U` physical flags;
- a health fault when the board is degraded or range is invalid;
- board fallback-alarm provenance;
- board session identifier.

Audio and camera buffers are still acquired on the HP and are not created by this adapter.

## Deterministic simulation

`scripts/board_serial_sim.py` injects:

1. normal 100 ms packets with varying USB arrival jitter;
2. two missing packets plus a matching board `serial_drops` increment;
3. a longer USB reconnect gap while the board keeps running;
4. a board reboot with sequence and `millis()` reset;
5. malformed and duplicate packets;
6. uint32 sequence/`millis()` wraparound.

Local verification before upload: 9/9 focused unit tests passed and all 12 simulation checks passed. The main simulated stream recorded six missing sequence samples and six board-reported serial drops across the two injected loss periods, then created a new session at the injected reboot.

The committed JSON result is `results/board_serial_simulation.json`. It is host-side simulation evidence only. Physical USB reconnect behaviour, OS serial-device naming, actual UNO reset behaviour when opening the port, and end-to-end audio/camera acquisition remain bench work.
