"""Coordinate board, audio and camera acquisition into RoomStream packets."""

import math
from pathlib import Path
import re
import threading

from .board_sync import BoardMediaSynchronizer
from .streaming import RoomStream


_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")


class CombinedAcquisitionCoordinator:
    """Join asynchronous board state to media without cross-thread SQLite use."""

    def __init__(self, root, model, backend=None, synchronizer=None,
                 stream_factory=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.backend = backend
        self.sync = synchronizer or BoardMediaSynchronizer()
        self._stream_factory = (
            stream_factory if stream_factory is not None
            else lambda directory: RoomStream(directory, self.model, self.backend)
        )
        self._lock = threading.RLock()
        self._stream = None
        self._stream_session = None
        self._media_seq = 0
        self.media_received = 0
        self.media_forwarded = 0
        self.waiting_for_board = 0
        self.stale_board_packets = 0
        self.media_fault_packets = 0
        self.room_rejected = 0
        self.stream_rotations = 0
        self.session_directories = {}

    @property
    def current_stream(self):
        with self._lock:
            return self._stream

    @property
    def current_session(self):
        with self._lock:
            return self._stream_session

    @staticmethod
    def _validate_session(session):
        if not isinstance(session, str) or not _SAFE_SESSION.fullmatch(session):
            raise ValueError("unsafe or missing board session")
        return session

    def _directory_for(self, session):
        session = self._validate_session(session)
        directory = self.root / ("board-" + session)
        self.session_directories[session] = str(directory)
        return directory

    def _close_stream(self):
        if self._stream is not None:
            self._stream.close()
        self._stream = None
        self._stream_session = None
        self._media_seq = 0

    def on_board_sample(self, sample):
        """Accept a validated BoardSample; never touch SQLite from serial thread."""
        with self._lock:
            self.sync.ingest(sample)

    def _ensure_stream(self, session):
        session = self._validate_session(session)
        if self._stream is not None and self._stream_session == session:
            return
        if self._stream is not None:
            self.stream_rotations += 1
            self._close_stream()
        self._stream = self._stream_factory(self._directory_for(session))
        self._stream_session = session
        self._media_seq = 0

    def push_media(self, audio, frame, captured, arrival=None, media_fault=False):
        captured = float(captured)
        arrival = captured if arrival is None else float(arrival)
        if not math.isfinite(captured) or not math.isfinite(arrival):
            raise ValueError("media timestamps must be finite")
        if arrival < captured:
            raise ValueError("media arrival cannot precede capture")

        with self._lock:
            self.media_received += 1
            match = self.sync.match(captured)
            if match.session is None or match.reason == "no_board_sample":
                self.waiting_for_board += 1
                return {"accepted": False, "reason": "waiting_for_board",
                        "board_match": match.as_dict(), "room": None}

            self._ensure_stream(match.session)
            self._media_seq += 1
            if not match.matched:
                self.stale_board_packets += 1
            physical = dict(match.physical)
            if media_fault:
                physical["fault"] = True
                self.media_fault_packets += 1

            room = self._stream.push(
                self._media_seq, captured, audio, frame, physical,
                session=match.session, arrival=arrival, fallback=match.fallback,
            )
            if room["accepted"]:
                self.media_forwarded += 1
            else:
                self.room_rejected += 1
            return {
                "accepted": bool(room["accepted"]),
                "reason": "ok" if room["accepted"] else "room_rejected",
                "session": match.session,
                "media_seq": self._media_seq,
                "board_match": match.as_dict(),
                "media_fault": bool(media_fault),
                "room": room,
            }

    def stats(self):
        with self._lock:
            return {
                "board_sync": self.sync.stats(),
                "current_session": self._stream_session,
                "media_received": self.media_received,
                "media_forwarded": self.media_forwarded,
                "waiting_for_board": self.waiting_for_board,
                "stale_board_packets": self.stale_board_packets,
                "media_fault_packets": self.media_fault_packets,
                "room_rejected": self.room_rejected,
                "stream_rotations": self.stream_rotations,
                "session_directories": dict(self.session_directories),
            }

    def close(self):
        with self._lock:
            self._close_stream()
