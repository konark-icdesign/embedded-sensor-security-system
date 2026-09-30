# System architecture

This document describes the current intended system rather than only the
original scenario runner. Historical simulation details remain in
[experiment_report.md](experiment_report.md), while the scope boundary is
recorded in [project_scope_audit.md](project_scope_audit.md).

## Purpose

The prototype monitors one room using audio, a camera and three physical sensor
channels. It does not treat any one weak observation as proof of intrusion.
Instead it correlates observations that occur close in time and records the
evidence for review.

The central idea is:

```text
microphone ──> audio anomaly ──┐
camera ─────> image change ────┤
PIR ────────> motion ──────────┤
radar ──────> presence/motion ─┼─> time correlation ─> GREEN / YELLOW / RED
ultrasonic ─> near range ──────┘
```

Sound alone cannot create RED.

## Hardware / software split

```text
PIR ───────┐
radar ─────┼─> UNO R4 firmware ──USB──┐
ultrasonic ┘                           │
                                      ▼
microphone ───────────────────────> HP t640
camera ───────────────────────────> host acquisition
                                      │
                                      ├─ C numerical core
                                      ├─ Python orchestration / fusion / evidence
                                      └─ MATLAB reference checks
```

| Part | Primary responsibility |
|---|---|
| UNO R4 C++ | physical sensor sampling/filtering, board health, packet generation, local fallback/alarm |
| C core | selected audio feature/anomaly and corroboration calculations |
| Python host | acquisition, timestamp synchronization, fusion/state handling, evidence storage and experiments |
| MATLAB | independent numerical/replay checks |
| HP t640 | intended host for the live system |
| Router/network | evidence/notification transport only; not part of sensing |

## Core state behavior

GREEN means there is no recent accepted evidence and no active reported fault.

YELLOW means an investigation is open because recent evidence or degraded sensor
health needs corroboration.

RED means the configured correlation rule was satisfied. RED is an engineering
state in this prototype, not a claim that a person or crime has been identified.

The current correlation window is four seconds. Each channel retains its most
recent accepted observation inside that window.

| Symbol | Evidence | Current weight |
|---|---|---:|
| A | audio anomaly | 1.5 |
| V | camera changed area above threshold | 3 |
| P | persisted PIR activity | 2 |
| M | persisted radar activity | 2 |
| U | persisted near-range result | 2 |

RED requires at least five points and one of the currently allowed combinations:

- camera plus PIR, radar or near range;
- PIR + radar + near range;
- audio plus at least two physical channels.

The weights are heuristics, not probabilities. They remain provisional until
room recordings provide evidence for changing them.

## Acquisition and timing

The planned live rates are:

- audio: 16 kHz mono;
- physical telemetry: nominal 10 Hz;
- camera processing: about 5 frames/s.

Rev-E through Rev-I provide the support path needed to combine those streams:

- board counter unwrap and board-to-host time mapping;
- serial reconnect/gap/reboot handling;
- stale board-state rejection;
- non-future camera selection;
- media/board synchronization;
- evidence journal isolation across board reboots.

Those mechanisms exist to protect the sensor-fusion experiment from stale or
mis-timestamped data. They are not separate detection features.

## Local fallback

If the host health signal is lost for more than two seconds, the board can use a
stricter local fallback. The current fallback requires filtered PIR, radar and
near ultrasonic evidence together for ten ticks before latching the alarm.

This rule intentionally favors avoiding weak local alarms and can miss a person
outside the ultrasonic beam. Coverage and placement must be measured physically.

## Evidence recording

The host keeps incident records with acquisition timestamps and preserves board
session boundaries. The existing continuous runner also exercises restart and
delivery behavior.

Five seconds of pre-trigger evidence and post-trigger evidence are part of the
intended recording behavior. The live path must be evaluated with real device
buffers before its timing can be treated as measured.

## What is verified and what is not

Verified at software/model level:

- synthetic fusion scenarios and state transitions;
- C/Python numerical agreement checks;
- MATLAB reference execution;
- UNO R4 target compilation;
- host-executed embedded-core fault tests;
- electrical/circuit models;
- Rev-E to Rev-I fake-device/replay integration tests.

Not yet established by the repository:

- actual room detection accuracy;
- actual sensor coverage and placement;
- real USB latency/drop distribution on the HP t640;
- real microphone callback/queue behavior;
- real camera frame-age/drop behavior;
- calibrated thresholds from the intended room;
- production notification reliability.

The next architecture milestone is therefore a physical synchronized capture,
not another host abstraction layer.
