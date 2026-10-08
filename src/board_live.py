"""Bench-ready UNO R4 USB serial runner.

This module keeps serial transport concerns outside BoardSerialAdapter.  The live
runner can reconnect after a USB/OS interruption, preserve the adapter's board
session state when counters continue, and surface a new session when the board
actually restarts.

Physical USB behavior is not claimed by the deterministic tests in this module.
"""

from __future__ import print_function

from dataclasses import asdict
import json
import os
from pathlib import Path
import time

from src.board_serial import BoardPacketError, BoardSerialAdapter


class PortSelectionError(RuntimeError):
    """No unambiguous serial port could be selected."""


def _port_text(port):
    fields = [
        getattr(port, "device", ""),
        getattr(port, "description", ""),
        getattr(port, "manufacturer", ""),
        getattr(port, "product", ""),
        getattr(port, "hwid", ""),
    ]
    return " ".join(str(x or "") for x in fields).lower()


def choose_serial_port(ports):
    """Choose a likely Arduino port without hard-coding one VID/PID.

    A unique port whose metadata mentions Arduino/UNO/Renesas is preferred.  If
    only one serial port exists, use it.  Multiple ambiguous ports require an
    explicit --port argument so the runner cannot silently attach to the wrong
    device.
    """
    ports = list(ports)
    likely = [
        p for p in ports
        if any(token in _port_text(p) for token in ("arduino", "uno r4", "renesas"))
    ]
    if len(likely) == 1:
        return likely[0].device
    if len(likely) > 1:
        raise PortSelectionError("multiple likely Arduino serial ports; pass --port explicitly")
    if len(ports) == 1:
        return ports[0].device
    if not ports:
        raise PortSelectionError("no serial ports found")
    raise PortSelectionError("multiple serial ports found and none is uniquely identifiable")


def discover_serial_port():
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise PortSelectionError("pyserial is required for live port discovery") from exc
    return choose_serial_port(list_ports.comports())


def open_pyserial(port, baudrate, timeout):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required for live serial acquisition") from exc
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


class JsonlLogger:
    """Append JSON objects and flush each record so a crash keeps prior evidence."""

    def __init__(self, path):
        self.path = None if path is None else Path(path)
        self.handle = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open("a", encoding="utf-8")

    def write(self, record):
        if self.handle is None:
            return
        self.handle.write(json.dumps(record, sort_keys=True, allow_nan=True) + "\n")
        self.handle.flush()

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


class BoardLiveRunner:
    """Read UNO packets, reconnect transport, log evidence and expose health."""

    def __init__(
        self,
        port="auto",
        baudrate=115200,
        timeout=0.25,
        reconnect_delay=1.0,
        adapter=None,
        serial_factory=None,
        port_resolver=None,
        clock=None,
        wall_clock=None,
        sleep=None,
        raw_log=None,
        parsed_log=None,
        status_interval=2.0,
        status_callback=None,
        sample_callback=None,
    ):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.reconnect_delay = float(reconnect_delay)
        self.adapter = adapter or BoardSerialAdapter()
        self.serial_factory = serial_factory or open_pyserial
        self.port_resolver = port_resolver or discover_serial_port
        self.clock = clock or time.monotonic
        self.wall_clock = wall_clock or time.time
        self.sleep = sleep or time.sleep
        self.raw_log = JsonlLogger(raw_log)
        self.parsed_log = JsonlLogger(parsed_log)
        self.status_interval = float(status_interval)
        self.status_callback = status_callback
        self.sample_callback = sample_callback

        self.connected = False
        self.active_port = None
        self.ports_seen = []
        self.connect_attempts = 0
        self.connection_errors = 0
        self.last_connection_error = None
        self.disconnects = 0
        self.timeouts = 0
        self.accepted = 0
        self.transport_rejected = 0
        self.first_accept_time = None
        self.last_accept_time = None
        self.last_arrival = None
        self.last_latency = None
        self.last_sample = None
        self.last_status_time = None

    def close(self):
        self.raw_log.close()
        self.parsed_log.close()

    def _resolve_port(self):
        return self.port_resolver() if self.port == "auto" else self.port

    def _emit_status(self, force=False):
        if self.status_callback is None:
            return
        now = self.clock()
        if (
            force
            or self.last_status_time is None
            or now - self.last_status_time >= self.status_interval
        ):
            self.last_status_time = now
            self.status_callback(self.health_snapshot(now=now))

    def _record_raw(self, raw, arrival, error=None):
        if isinstance(raw, bytes):
            text = raw.decode("ascii", errors="replace").rstrip("\r\n")
        else:
            text = str(raw).rstrip("\r\n")
        record = {
            "host_wall_time": self.wall_clock(),
            "arrival_monotonic": arrival,
            "port": self.active_port,
            "line": text,
            "accepted": error is None,
        }
        if error is not None:
            record["error"] = str(error)
        self.raw_log.write(record)

    def _record_sample(self, sample):
        record = sample.as_dict()
        record.update({
            "host_wall_time": self.wall_clock(),
            "port": self.active_port,
            "latency_seconds": sample.arrival - sample.captured,
        })
        self.parsed_log.write(record)

    def health_snapshot(self, now=None):
        now = self.clock() if now is None else float(now)
        duration = None
        rate_hz = None
        if self.first_accept_time is not None and self.accepted > 1:
            duration = self.last_accept_time - self.first_accept_time
            if duration > 0:
                rate_hz = (self.accepted - 1) / duration

        stale_seconds = None
        if self.last_arrival is not None:
            stale_seconds = max(0.0, now - self.last_arrival)

        sample = self.last_sample
        return {
            "connected": self.connected,
            "port": self.active_port,
            "ports_seen": list(self.ports_seen),
            "connect_attempts": self.connect_attempts,
            "connection_errors": self.connection_errors,
            "last_connection_error": self.last_connection_error,
            "samples": self.accepted,
            "rate_hz": rate_hz,
            "timeouts": self.timeouts,
            "disconnects": self.disconnects,
            "transport_rejected": self.transport_rejected,
            "session": self.adapter.session,
            "sequence_gaps": self.adapter.sequence_gaps,
            "board_reported_drops": self.adapter.board_reported_drops,
            "reboots": self.adapter.reboots,
            "adapter_rejected": self.adapter.rejected,
            "last_latency_seconds": self.last_latency,
            "stale_seconds": stale_seconds,
            "pir": None if sample is None else sample.pir,
            "radar": None if sample is None else sample.radar,
            "near": None if sample is None else sample.near,
            "range_valid": None if sample is None else sample.range_valid,
            "degraded": None if sample is None else sample.degraded,
            "fallback_alarm": None if sample is None else sample.fallback_alarm,
        }

    def run(self, max_samples=None, max_connect_attempts=None, stop_event=None):
        """Run until interrupted, stopped, or an optional test limit is met."""
        serial_obj = None
        try:
            while ((max_samples is None or self.accepted < max_samples)
                   and (stop_event is None or not stop_event.is_set())):
                if serial_obj is None:
                    if (
                        max_connect_attempts is not None
                        and self.connect_attempts >= max_connect_attempts
                    ):
                        break
                    try:
                        self.connect_attempts += 1
                        self.active_port = self._resolve_port()
                        serial_obj = self.serial_factory(
                            self.active_port, self.baudrate, self.timeout
                        )
                        if self.active_port not in self.ports_seen:
                            self.ports_seen.append(self.active_port)
                        self.connected = True
                        self._emit_status(force=True)
                    except (OSError, IOError, PortSelectionError, RuntimeError) as exc:
                        self.connection_errors += 1
                        self.last_connection_error = "{}: {}".format(
                            type(exc).__name__, exc
                        )
                        self.connected = False
                        self.active_port = None
                        self._emit_status(force=True)
                        if (
                            max_connect_attempts is not None
                            and self.connect_attempts >= max_connect_attempts
                        ):
                            break
                        if stop_event is None:
                            self.sleep(self.reconnect_delay)
                        else:
                            stop_event.wait(self.reconnect_delay)
                        continue

                try:
                    raw = serial_obj.readline()
                    arrival = self.clock()
                except (OSError, IOError):
                    self.disconnects += 1
                    self.connected = False
                    try:
                        serial_obj.close()
                    except Exception:
                        pass
                    serial_obj = None
                    self._emit_status(force=True)
                    if stop_event is None:
                        self.sleep(self.reconnect_delay)
                    else:
                        stop_event.wait(self.reconnect_delay)
                    continue

                if raw in (b"", ""):
                    self.timeouts += 1
                    self._emit_status()
                    continue

                try:
                    sample = self.adapter.ingest(raw, arrival=arrival)
                except BoardPacketError as exc:
                    self.transport_rejected += 1
                    self._record_raw(raw, arrival, error=exc)
                    self._emit_status()
                    continue

                self._record_raw(raw, arrival)
                self._record_sample(sample)
                self.accepted += 1
                if self.first_accept_time is None:
                    self.first_accept_time = arrival
                self.last_accept_time = arrival
                self.last_arrival = arrival
                self.last_latency = sample.arrival - sample.captured
                self.last_sample = sample
                if self.sample_callback is not None:
                    self.sample_callback(sample)
                self._emit_status()

            return self.health_snapshot()
        finally:
            self.connected = False
            if serial_obj is not None:
                try:
                    serial_obj.close()
                except Exception:
                    pass
            self._emit_status(force=True)
            self.close()


def format_health(status):
    rate = status["rate_hz"]
    latency = status["last_latency_seconds"]
    rate_text = "n/a" if rate is None else "{:.2f} Hz".format(rate)
    latency_text = "n/a" if latency is None else "{:.1f} ms".format(latency * 1000.0)
    return (
        "BOARD {state} port={port} session={session} samples={samples} "
        "rate={rate} latency={latency} gaps={gaps} board_drops={drops} "
        "reboots={reboots} rejected={rejected} P={pir} M={radar} U={near} "
        "range_valid={range_valid} degraded={degraded}"
    ).format(
        state="connected" if status["connected"] else "disconnected",
        port=status["port"] or "-",
        session=status["session"],
        samples=status["samples"],
        rate=rate_text,
        latency=latency_text,
        gaps=status["sequence_gaps"],
        drops=status["board_reported_drops"],
        reboots=status["reboots"],
        rejected=status["transport_rejected"],
        pir=status["pir"],
        radar=status["radar"],
        near=status["near"],
        range_valid=status["range_valid"],
        degraded=status["degraded"],
    )
