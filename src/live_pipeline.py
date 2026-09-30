"""Coordinate board, audio and camera acquisition into RoomStream packets."""

import math
from pathlib import Path
import re

from .board_sync import BoardMediaSynchronizer
from .streaming import RoomStream


_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")


class CombinedAcquisitionCoordinator:
    """Join asynchronous board state to media and rotate journals on board reboot.

    BoardLiveRunner can call on_board_sample through its sample_callback.
    Host audio/camera acquisition calls push_media with the media acquisition
    timestamp. A separate media sequence is used because one 10 Hz board sample
    may legitimately be paired with more than one media packet.
    """

    def __init__(
        self,
        root,
        model,
        backend=None,
        synchronizer=None,
        stream_factory=None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.backend = backend
        self.sync = synchronizer or BoardMediaSynchronizer()
        self._stream_factory = (
            stream_factory
            if stream_factory is not None
            else lambda directory: RoomStream(directory, self.model, self.backend)
        )

        self._stream = None
        self._stream_session = None
        self._media_seq = 0

        self.media_received = 0
        self.media_forwarded = 0
        self.waiting_for_board = 0
        self.stale_board_packets = 0
        self.room_rejected = 0
        self.stream_rotations = 0
        self.session_directories = {}

    @property
    def current_stream(self):
        return self._stream

    @property
    def current_session(self):
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
        """Accept a validated BoardSample from BoardLiveRunner."""
        previous = self.sync.session
        self.sync.ingest(sample)
        if previous is not None and self.sync.session != previous:
            self.stream_rotations += 1
            self._close_stream()

    def _ensure_stream(self, session):
        session = self._validate_session(session)
        if self._stream is not None and self._stream_session == session:
            return
        if self._stream is not None:
            self._close_stream()
        self._stream = self._stream_factory(self._directory_for(session))
        self._stream_session = session
        self._media_seq = 0

    def push_media(self, audio, frame, captured, arrival=None):
        """Push one host media packet using the board state valid at capture time."""
        captured = float(captured)
        arrival = captured if arrival is None else float(arrival)
        if not math.isfinite(captured) or not math.isfinite(arrival):
            raise ValueError("media timestamps must be finite")
        if arrival < captured:
            raise ValueError("media arrival cannot precede capture")

        self.media_received += 1
        match = self.sync.match(captured)

        if match.session is None or match.reason == "no_board_sample":
            self.waiting_for_board += 1
            return {
                "accepted": False,
                "reason": "waiting_for_board",
                "board_match": match.as_dict(),
                "room": None,
            }

        self._ensure_stream(match.session)
        self._media_seq += 1

        if not match.matched:
            self.stale_board_packets += 1

        room = self._stream.push(
            self._media_seq,
            captured,
            audio,
            frame,
            match.physical,
            session=match.session,
            arrival=arrival,
            fallback=match.fallback,
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
            "room": room,
        }

    def stats(self):
        return {
            "board_sync": self.sync.stats(),
            "current_session": self._stream_session,
            "media_received": self.media_received,
            "media_forwarded": self.media_forwarded,
            "waiting_for_board": self.waiting_for_board,
            "stale_board_packets": self.stale_board_packets,
            "room_rejected": self.room_rejected,
            "stream_rotations": self.stream_rotations,
            "session_directories": dict(self.session_directories),
        }

    def close(self):
        self._close_stream()
