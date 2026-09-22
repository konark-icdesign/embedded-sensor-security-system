"""UNO R4 USB sensor packet parsing, session tracking and host-clock mapping.

The board publishes one ASCII line per nominal 100 ms sample. This module keeps
wire-format handling separate from the incident engine so the same mapper can be
exercised with deterministic fault injection before a physical USB bench run.
"""

from dataclasses import dataclass, asdict
import math
import time

UINT32 = 1 << 32
HALF32 = 1 << 31


class BoardPacketError(ValueError):
    """Malformed or non-monotonic board input."""


@dataclass(frozen=True)
class BoardWirePacket:
    sequence: int
    board_millis: int
    pir: bool
    radar: bool
    near: bool
    range_metres: float
    range_valid: bool
    alarm: bool
    armed: bool
    degraded: bool
    fallback_alarm: bool
    serial_drops: int


@dataclass(frozen=True)
class BoardSample:
    session: str
    sequence: int
    sequence_unwrapped: int
    board_millis: int
    board_millis_unwrapped: int
    captured: float
    arrival: float
    pir: bool
    radar: bool
    near: bool
    range_metres: float
    range_valid: bool
    alarm: bool
    armed: bool
    degraded: bool
    fallback_alarm: bool
    serial_drops: int
    missing_before: int
    board_reported_drops_delta: int

    def room_physical(self):
        return {
            "P": self.pir,
            "M": self.radar,
            "U": self.near,
            "fault": self.degraded or not self.range_valid,
        }

    def room_push_fields(self):
        """Fields consumed by RoomStream.push in the existing incident pipeline."""
        return {
            "seq": self.sequence_unwrapped,
            "captured": self.captured,
            "physical": self.room_physical(),
            "session": self.session,
            "arrival": self.arrival,
            "fallback": self.fallback_alarm,
        }

    def as_dict(self):
        out = asdict(self)
        out["physical"] = self.room_physical()
        return out


def _u32(value, name):
    value = int(value)
    if not 0 <= value < UINT32:
        raise BoardPacketError(f"{name} is outside uint32")
    return value


def _bit(value, name):
    if value not in ("0", "1"):
        raise BoardPacketError(f"{name} must be 0 or 1")
    return value == "1"


def parse_sensor_line(line):
    if isinstance(line, bytes):
        line = line.decode("ascii", errors="strict")
    fields = line.strip().split(",")
    if len(fields) != 13 or fields[0] != "S":
        raise BoardPacketError("expected 13-field S packet")
    try:
        sequence = _u32(fields[1], "sequence")
        board_millis = _u32(fields[2], "board_millis")
        pir = _bit(fields[3], "pir")
        radar = _bit(fields[4], "radar")
        near = _bit(fields[5], "near")
        range_metres = float(fields[6])
        range_valid = _bit(fields[7], "range_valid")
        alarm = _bit(fields[8], "alarm")
        armed = _bit(fields[9], "armed")
        degraded = _bit(fields[10], "degraded")
        fallback_alarm = _bit(fields[11], "fallback_alarm")
        serial_drops = _u32(fields[12], "serial_drops")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, BoardPacketError):
            raise
        raise BoardPacketError("invalid numeric field") from exc
    if range_valid:
        if not math.isfinite(range_metres) or range_metres < 0:
            raise BoardPacketError("valid range must be finite and non-negative")
    elif not (math.isnan(range_metres) or (math.isfinite(range_metres) and range_metres >= 0)):
        raise BoardPacketError("invalid-range payload is malformed")
    return BoardWirePacket(sequence, board_millis, pir, radar, near, range_metres,
                           range_valid, alarm, armed, degraded, fallback_alarm,
                           serial_drops)


def _forward_delta(previous, current):
    return (current - previous) & 0xFFFFFFFF


class BoardSerialAdapter:
    """Turn board packets into one host-clock stream with explicit reboot sessions.

    Clock offset follows the lowest observed arrival-minus-board-time value. That
    treats USB delay as non-negative transport latency instead of sensor time.
    """

    def __init__(self, session_prefix="uno-r4"):
        self.session_prefix = session_prefix
        self.session_index = 0
        self.last_seq_raw = None
        self.last_ms_raw = None
        self.last_drop_raw = None
        self.seq_unwrapped = None
        self.ms_unwrapped = None
        self.clock_offset = None
        self.last_captured = None
        self.sequence_gaps = 0
        self.board_reported_drops = 0
        self.reboots = 0
        self.rejected = 0

    @property
    def session(self):
        return f"{self.session_prefix}-{self.session_index:04d}"

    def _start_session(self, packet, arrival, reboot=False):
        if reboot:
            self.session_index += 1
            self.reboots += 1
        self.last_seq_raw = packet.sequence
        self.last_ms_raw = packet.board_millis
        self.last_drop_raw = packet.serial_drops
        self.seq_unwrapped = packet.sequence
        self.ms_unwrapped = packet.board_millis
        self.clock_offset = float(arrival) - self.ms_unwrapped / 1000.0
        self.last_captured = float(arrival)
        return 0, 0

    def ingest(self, line, arrival=None):
        arrival = time.monotonic() if arrival is None else float(arrival)
        if not math.isfinite(arrival):
            raise BoardPacketError("arrival time must be finite")
        try:
            packet = parse_sensor_line(line)
            if self.last_seq_raw is None:
                missing, drop_delta = self._start_session(packet, arrival)
            else:
                seq_delta = _forward_delta(self.last_seq_raw, packet.sequence)
                ms_delta = _forward_delta(self.last_ms_raw, packet.board_millis)
                seq_backward = seq_delta > HALF32
                ms_backward = ms_delta > HALF32
                if seq_backward and ms_backward:
                    missing, drop_delta = self._start_session(packet, arrival, reboot=True)
                elif seq_backward or ms_backward:
                    raise BoardPacketError("board counters moved inconsistently")
                else:
                    if seq_delta == 0:
                        raise BoardPacketError("duplicate sequence")
                    if ms_delta == 0:
                        raise BoardPacketError("board_millis did not advance")
                    self.seq_unwrapped += seq_delta
                    self.ms_unwrapped += ms_delta
                    missing = max(0, seq_delta - 1)
                    self.sequence_gaps += missing
                    drop_delta = _forward_delta(self.last_drop_raw, packet.serial_drops)
                    if drop_delta > HALF32:
                        raise BoardPacketError("serial_drops moved backwards without reboot")
                    self.board_reported_drops += drop_delta
                    self.last_seq_raw = packet.sequence
                    self.last_ms_raw = packet.board_millis
                    self.last_drop_raw = packet.serial_drops
                    observed_offset = arrival - self.ms_unwrapped / 1000.0
                    if observed_offset < self.clock_offset:
                        self.clock_offset = observed_offset
                    captured = self.clock_offset + self.ms_unwrapped / 1000.0
                    if captured <= self.last_captured:
                        raise BoardPacketError("mapped capture time is not monotonic")
                    self.last_captured = captured
            captured = self.last_captured
            if arrival < captured:
                raise BoardPacketError("packet arrived before mapped capture time")
            if arrival - captured > 0.5:
                raise BoardPacketError("packet latency exceeds incident freshness limit")
            return BoardSample(
                self.session, packet.sequence, self.seq_unwrapped,
                packet.board_millis, self.ms_unwrapped, captured, arrival,
                packet.pir, packet.radar, packet.near, packet.range_metres,
                packet.range_valid, packet.alarm, packet.armed, packet.degraded,
                packet.fallback_alarm, packet.serial_drops, missing, drop_delta,
            )
        except BoardPacketError:
            self.rejected += 1
            raise

    def stats(self):
        return {
            "session": self.session,
            "reboots": self.reboots,
            "sequence_gaps": self.sequence_gaps,
            "board_reported_drops": self.board_reported_drops,
            "rejected": self.rejected,
        }
