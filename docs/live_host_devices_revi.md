# Rev-I live host device acquisition

Rev-I adds optional physical microphone and webcam backends while keeping CI device-free.

The live path is UNO USB -> Rev-F -> Rev-G -> Rev-H/Rev-I coordinator, with 16 kHz microphone chunks and recent grayscale webcam frames feeding RoomStream.

Audio timestamps use PortAudio input-buffer time mapped into the host monotonic clock instead of treating callback arrival as acquisition time. PortAudio faults, impossible clock mappings and microphone queue overflow are propagated as media-health faults. Queue overflow drops the oldest queued chunk so the live path stays current.

Camera capture runs in a background thread, converts frames to 320x240 grayscale and keeps a bounded recent buffer. Each audio chunk can use only a non-future camera frame no older than 350 ms.

Rev-I also fixes a live-thread issue in Rev-H. The serial callback no longer closes SQLite/RoomStream state. A board reboot updates synchronized state in the serial thread, then the media thread closes the old journal and opens the new board-session journal on the next audio packet.

Install optional device packages with:

    python -m pip install -r requirements-live.txt

Example:

    python scripts/run_live_room.py --port auto --camera-index 0 --seconds 60

The current runner still uses the synthetic quiet-room baseline, so it is for acquisition engineering only. CI uses fake devices and makes no physical HP t640, microphone, webcam or UNO measurement claim.
