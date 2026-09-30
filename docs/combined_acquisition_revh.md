# Rev-H combined acquisition coordinator

Rev-H connects the Rev-F serial runner and Rev-G timestamp synchronizer to the existing RoomStream incident pipeline.

This is the software coordination layer needed before running the UNO R4, microphone and camera together on the HP t640. It is not a physical acquisition result.

## Why a coordinator is needed

The board and host media sources do not share one packet clock:

- the board currently publishes nominal 100 ms sensor samples;
- audio may be delivered in host chunks;
- camera frames may arrive at a different cadence;
- one physical board sample may legitimately apply to multiple media packets.

For that reason, Rev-H does not use the Arduino sequence number as the RoomStream packet sequence. It maintains a separate media sequence inside each board session.

## Session boundary

IncidentJournal intentionally does not accept a different session into an existing journal. Rev-H therefore treats an Arduino reboot as a hard acquisition boundary:

1. Rev-G detects the board session change;
2. the current RoomStream is closed;
3. the media sequence resets;
4. the next media packet opens a separate directory for the new board session.

This prevents pre-reboot evidence and timestamps from being silently mixed with post-reboot evidence.

## Media handling

CombinedAcquisitionCoordinator.push_media(audio, frame, captured, arrival):

- refuses to invent a session when no non-future board sample exists yet;
- uses Rev-G fresh physical flags when the board match is valid;
- forwards stale board state only as P=0, M=0, U=0, fault=true;
- preserves a fallback alarm only when Rev-G considers it fresh;
- sends the synchronized packet to RoomStream with a monotonic media sequence.

BoardLiveRunner can feed it directly:

    coordinator = CombinedAcquisitionCoordinator("results/live-room", model)
    runner = BoardLiveRunner(sample_callback=coordinator.on_board_sample)

The microphone/camera acquisition callback should then call coordinator.push_media(...) with acquisition timestamps from the same host monotonic clock domain.

## Deterministic validation

scripts/combined_acquisition_sim.py uses simulated UNO packets and synthetic 16 kHz audio to exercise the real RoomStream/SQLite journal path. It verifies:

- media before the first board sample is not assigned invented physical state;
- multiple media packets can use one fresh board sample while keeping unique media sequences;
- fresh P/M/U flags reach the incident journal;
- stale board state becomes a health fault with P/M/U cleared;
- a board reboot creates a separate persistent journal;
- the new board session starts its own media sequence;
- post-reboot physical/fallback state does not mix with the old journal.

The next physical stage is to provide actual host microphone and camera callbacks and run this coordinator with the Rev-F serial service on the HP t640.

## First CI fault-injection correction

The first Rev-H CI run failed before the coordinator checks because the reboot fixture reset board_millis but the pre-reboot sequence was already zero. Rev-E correctly rejected that as inconsistent counter movement instead of treating it as a reboot. The fixture was corrected to start from a forward-running sequence value so both sequence and millis reset together, matching the reboot rule being tested.
