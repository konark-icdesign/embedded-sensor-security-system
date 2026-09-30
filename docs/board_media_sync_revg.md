# Rev-G board/media timestamp synchronizer

Rev-F made the UNO serial path bench-ready. Rev-G handles the next integration problem: board packets, audio chunks and camera frames are acquired independently, so physical sensor state must be paired to media using acquisition time rather than USB arrival order.

`BoardMediaSynchronizer` keeps a short buffer of validated `BoardSample` objects and applies three rules:

1. choose only the newest board sample whose capture time is not in the future relative to the media timestamp;
2. never reuse a board sample older than 150 ms; stale or missing board data becomes an explicit physical-health fault with P/M/U cleared;
3. clear the buffer on a board session change so sensor state from before a reboot cannot leak into the new session.

The 150 ms initial limit is based on the current nominal 100 ms board cadence plus modest scheduling/transport margin. It is a software integration limit, not a measured USB jitter specification; the physical bench capture should be used to revise it if needed.

The synchronizer preserves fallback-alarm provenance only for a fresh match. A stale fallback flag is not replayed.

## Deterministic checks

`scripts/board_media_sync_sim.py` verifies:

- a future board sample is never used for an earlier media frame;
- two media timestamps select the correct changing board state;
- a 151 ms-old sample becomes a health fault instead of stale P/M/U evidence;
- a simulated board reboot flushes the old buffer;
- post-reboot media uses only the new session and preserves a fresh fallback alarm.

This stage still does not create physical microphone/camera evidence. Its purpose is to make the timing contract explicit before the first combined bench capture.
