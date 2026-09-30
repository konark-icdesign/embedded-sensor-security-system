"""Synchronize asynchronous board samples with host audio/camera capture time."""

from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BoardMediaMatch:
    matched: bool
    reason: str
    session: str
    age_seconds: float
    board_sequence: int
    board_captured: float
    physical: dict
    fallback: bool

    def as_dict(self):
        return {
            "matched": self.matched,
            "reason": self.reason,
            "session": self.session,
            "age_seconds": self.age_seconds,
            "board_sequence": self.board_sequence,
            "board_captured": self.board_captured,
            "physical": dict(self.physical),
            "fallback": self.fallback,
        }


class BoardMediaSynchronizer:
    """Pair a media timestamp with the most recent non-future board sample.

    Stale or missing board data is converted to an explicit physical-health
    fault. Sensor flags are never reused after the freshness limit, and a board
    session change clears buffered samples so pre-reboot state cannot leak into
    the new session.
    """

    def __init__(self, max_age=0.15, capacity=32):
        self.max_age = float(max_age)
        self.capacity = int(capacity)
        if not math.isfinite(self.max_age) or self.max_age <= 0:
            raise ValueError("max_age must be finite and positive")
        if self.capacity < 2:
            raise ValueError("capacity must be at least two")
        self.samples = deque(maxlen=self.capacity)
        self.session = None
        self.session_changes = 0
        self.rejected = 0

    @staticmethod
    def fault_physical():
        return {"P": False, "M": False, "U": False, "fault": True}

    def ingest(self, sample):
        if self.session is None:
            self.session = sample.session
        elif sample.session != self.session:
            self.samples.clear()
            self.session = sample.session
            self.session_changes += 1
        elif self.samples and sample.captured <= self.samples[-1].captured:
            self.rejected += 1
            raise ValueError("board capture time must increase within a session")
        self.samples.append(sample)

    def match(self, captured):
        captured = float(captured)
        if not math.isfinite(captured):
            raise ValueError("media capture time must be finite")

        candidate = None
        for sample in reversed(self.samples):
            if sample.captured <= captured:
                candidate = sample
                break

        if candidate is None:
            return BoardMediaMatch(
                False, "no_board_sample", self.session, None, None, None,
                self.fault_physical(), False,
            )

        age = captured - candidate.captured
        if age > self.max_age:
            return BoardMediaMatch(
                False, "stale_board_sample", candidate.session, age,
                candidate.sequence_unwrapped, candidate.captured,
                self.fault_physical(), False,
            )

        return BoardMediaMatch(
            True, "ok", candidate.session, age,
            candidate.sequence_unwrapped, candidate.captured,
            candidate.room_physical(), candidate.fallback_alarm,
        )

    def stats(self):
        return {
            "session": self.session,
            "buffered_samples": len(self.samples),
            "session_changes": self.session_changes,
            "rejected": self.rejected,
            "max_age_seconds": self.max_age,
        }
