# Project scope reset

This document records the September 2026 scope audit. It does not remove or
invalidate the Rev-E through Rev-I work. It separates the **security-system
experiment** from the **host infrastructure that supports it**.

## Core question

Can a small room-security prototype reduce weak single-sensor alarms by checking
whether independent observations from approximately the same event agree?

The intended evidence channels are:

- microphone / audio anomaly;
- camera motion evidence;
- PIR motion;
- radar presence/motion;
- ultrasonic range.

The intended central behavior remains:

1. an unusual sound or other recent evidence opens a YELLOW investigation;
2. evidence is correlated inside a provisional four-second window;
3. sound alone cannot create RED;
4. RED requires corroboration from camera and/or physical sensors;
5. evidence is recorded and surfaced for human review.

This sensor-fusion behavior is the project. USB reconnect logic, SQLite session
rotation and device wrappers are supporting mechanisms, not separate project
goals.

## System partition

| Layer | Responsibility | Project role |
|---|---|---|
| UNO R4 firmware | sample/filter PIR, radar and ultrasonic inputs; report health; maintain local fallback/alarm behavior | Core embedded layer |
| C numerical core | selected audio features, anomaly scoring and corroboration used by the host | Core computation |
| Python host | acquire audio/camera/board data, synchronize timestamps, call the detection/fusion path, record evidence and run experiments | Integration layer |
| MATLAB | independent numerical/replay reference | Verification layer |
| Rev-E to Rev-I host services | serial parsing/reconnect, board-clock mapping, media synchronization, journal/session handling and optional device backends | Support infrastructure |
| HTTP/local receiver | exercise delivery/retry behavior | Test infrastructure |

The language is not the objective. C/C++, Python and MATLAB are used where they
fit the system.

## Scope audit of Rev-E through Rev-I

The audit found that these revisions solve legitimate live-integration problems:

- **Rev-E:** board packet contract, counter unwrap, gap/reboot detection and clock mapping;
- **Rev-F:** reconnecting serial transport and evidence logging;
- **Rev-G:** board/media timestamp matching with stale-state rejection;
- **Rev-H:** handoff into RoomStream and journal isolation across board sessions;
- **Rev-I:** optional microphone/webcam backends and live host threading.

They are therefore retained. The problem was not that the code exists; the
problem was that recent documentation made this infrastructure look like the
main project.

No further host abstraction should be added merely because it can be simulated.
A new support feature should have a clear path to one of the core measurements
below.

## Evidence ladder

Results must be labelled by the strongest evidence actually obtained:

1. **Synthetic simulation** — generated audio/images/sensor traces.
2. **Host-executed implementation test** — real project code with fake devices or replay data.
3. **Target compile / electrical model** — UNO R4 compilation or circuit simulation.
4. **Bench measurement** — physical UNO/USB/sensor/microphone/camera capture.
5. **Integrated room trial** — synchronized room data with separate ground truth.
6. **Held-out evaluation** — frozen rules/model tested on separate recording sessions.

Passing a lower level does not imply a higher one.

## Current boundary

The repository has reached level 1–3 for many subsystems. Rev-I makes a first
combined bench run possible, but the repository still does **not** contain
physical evidence for the complete chain.

The next useful work should therefore be measurement-driven:

- run UNO R4 -> HP serial and record actual cadence, gaps, reset/reconnect behavior and latency;
- capture the intended microphone and measure audio callback/queue behavior;
- add webcam capture and measure frame age/drop behavior;
- collect synchronized room recordings and test the existing GREEN/YELLOW/RED fusion;
- revisit thresholds and sensor placement from those recordings.

Possible firmware or C changes are justified when those measurements expose a
real limitation. Another synthetic Rev-J/Rev-K infrastructure layer is not a
goal by itself.

## Explicit non-goals for this prototype

- production-grade home-security certification;
- identity recognition or claims that a detected object is a person;
- cloud-scale or distributed-service architecture;
- replacing physical sensor/room testing with increasingly elaborate simulation;
- maximizing the amount of C, C++, Python or any other language for portfolio appearance.

The project should remain a buildable, explainable multi-sensor engineering
prototype with clear evidence for what was actually tested.
