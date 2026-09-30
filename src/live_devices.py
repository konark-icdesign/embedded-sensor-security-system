"""Optional microphone/camera backends and the live HP host runtime."""

from collections import deque
from dataclasses import dataclass, replace
import math
import queue
import threading
import time

import numpy as np

from .dsp import FS


@dataclass(frozen=True)
class AudioChunk:
    samples: np.ndarray
    captured: float
    arrival: float
    fault: bool = False
    reason: str = ""


@dataclass(frozen=True)
class CameraFrame:
    frame: np.ndarray
    captured: float


def map_portaudio_end_to_monotonic(arrival, input_adc_time, current_time,
                                   frames, samplerate):
    vals = [arrival, input_adc_time, current_time, samplerate]
    try:
        finite = all(math.isfinite(float(x)) for x in vals)
    except (TypeError, ValueError):
        finite = False
    if not finite or frames <= 0 or samplerate <= 0:
        return float(arrival), True
    end_pa = float(input_adc_time) + float(frames) / float(samplerate)
    mapped = float(arrival) + (end_pa - float(current_time))
    fault = mapped > float(arrival) + 0.020 or mapped < float(arrival) - 5.0
    if fault:
        return float(arrival), True
    return min(mapped, float(arrival)), False


def _time_field(info, name):
    value = getattr(info, name, None)
    if value is None and isinstance(info, dict):
        value = info.get(name)
    return value


class CameraFrameBuffer:
    def __init__(self, capacity=16):
        self.frames = deque(maxlen=int(capacity))
        self.lock = threading.Lock()

    def push(self, frame, captured):
        x = np.asarray(frame)
        if x.ndim != 2 or x.size == 0:
            raise ValueError("camera frame must be a non-empty grayscale image")
        with self.lock:
            self.frames.append(CameraFrame(x.astype(np.uint8, copy=True),
                                           float(captured)))

    def match(self, captured, max_age=0.35):
        captured = float(captured)
        with self.lock:
            for item in reversed(self.frames):
                if item.captured <= captured:
                    if captured - item.captured <= float(max_age):
                        return item.frame.copy(), item.captured
                    return None, item.captured
        return None, None


class SoundDeviceMicrophone:
    def __init__(self, device=None, samplerate=FS, chunk_frames=1600,
                 queue_depth=8, clock=None):
        self.device = device
        self.samplerate = int(samplerate)
        self.chunk_frames = int(chunk_frames)
        self.clock = clock or time.monotonic
        self.queue = queue.Queue(maxsize=int(queue_depth))
        self.queue_drops = 0
        self.callback_faults = 0
        self.stream = None

    def _callback(self, indata, frames, time_info, status):
        arrival = self.clock()
        captured, clock_fault = map_portaudio_end_to_monotonic(
            arrival, _time_field(time_info, "inputBufferAdcTime"),
            _time_field(time_info, "currentTime"), frames, self.samplerate)
        x = np.asarray(indata)
        if x.ndim != 2 or x.shape[1] < 1:
            return
        reasons = []
        if status:
            reasons.append(str(status))
        if clock_fault:
            reasons.append("audio_clock_mapping")
        fault = bool(status) or clock_fault
        if fault:
            self.callback_faults += 1
        chunk = AudioChunk(x[:, 0].astype(float, copy=True), captured, arrival,
                           fault, ";".join(reasons))
        try:
            self.queue.put_nowait(chunk)
        except queue.Full:
            self.queue_drops += 1
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            chunk = replace(chunk, fault=True,
                            reason=(chunk.reason + ";queue_drop").strip(";"))
            self.queue.put_nowait(chunk)

    def start(self):
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("live microphone capture needs requirements-live.txt") from exc
        self.stream = sd.InputStream(
            device=self.device, channels=1, samplerate=self.samplerate,
            blocksize=self.chunk_frames, dtype="float32", callback=self._callback)
        self.stream.start()

    def read(self, timeout=1.0):
        return self.queue.get(timeout=timeout)

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
                self.stream = None

    def stats(self):
        return {"queue_drops": self.queue_drops,
                "callback_faults": self.callback_faults,
                "queued_chunks": self.queue.qsize()}


class OpenCVCamera:
    def __init__(self, index=0, width=320, height=240, fps=5,
                 buffer=None, clock=None):
        self.index = int(index)
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.buffer = buffer or CameraFrameBuffer()
        self.clock = clock or time.monotonic
        self.stop_event = threading.Event()
        self.thread = None
        self.capture = None
        self.frames = 0
        self.failures = 0

    def _loop(self, cv2):
        while not self.stop_event.is_set():
            ok, frame = self.capture.read()
            captured = self.clock()
            if not ok or frame is None:
                self.failures += 1
                self.stop_event.wait(0.05)
                continue
            if frame.ndim == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if frame.shape != (self.height, self.width):
                frame = cv2.resize(frame, (self.width, self.height),
                                   interpolation=cv2.INTER_AREA)
            self.buffer.push(frame, captured)
            self.frames += 1

    def start(self):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("live camera capture needs requirements-live.txt") from exc
        self.capture = cv2.VideoCapture(self.index)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("camera could not be opened")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, args=(cv2,),
                                       name="camera-capture", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.capture is not None:
            self.capture.release()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.capture = None
        self.thread = None

    def stats(self):
        return {"frames": self.frames, "failures": self.failures}


class LiveHostRuntime:
    def __init__(self, coordinator, board_runner, microphone, camera=None,
                 camera_max_age=0.35, status_callback=None, clock=None):
        self.coordinator = coordinator
        self.board_runner = board_runner
        self.microphone = microphone
        self.camera = camera
        self.camera_max_age = float(camera_max_age)
        self.status_callback = status_callback
        self.clock = clock or time.monotonic
        self.stop_event = threading.Event()
        self.board_thread = None
        self.board_error = None
        self.media_chunks = 0
        self.camera_matches = 0
        self.camera_misses = 0
        self.media_faults = 0

    def _board_main(self):
        try:
            self.board_runner.run(stop_event=self.stop_event)
        except Exception as exc:
            self.board_error = exc
            self.stop_event.set()

    def run(self, max_chunks=None, max_seconds=None):
        self.board_runner.sample_callback = self.coordinator.on_board_sample
        started = self.clock()
        self.stop_event.clear()
        try:
            if self.camera is not None:
                self.camera.start()
            self.microphone.start()
            self.board_thread = threading.Thread(
                target=self._board_main, name="uno-serial", daemon=True)
            self.board_thread.start()
            while not self.stop_event.is_set():
                if max_chunks is not None and self.media_chunks >= max_chunks:
                    break
                if max_seconds is not None and self.clock() - started >= max_seconds:
                    break
                try:
                    chunk = self.microphone.read(timeout=0.25)
                except queue.Empty:
                    if self.board_error is not None:
                        raise RuntimeError("board acquisition stopped") from self.board_error
                    continue
                frame = None
                if self.camera is not None:
                    frame, _ = self.camera.buffer.match(
                        chunk.captured, self.camera_max_age)
                    if frame is None:
                        self.camera_misses += 1
                    else:
                        self.camera_matches += 1
                if chunk.fault:
                    self.media_faults += 1
                result = self.coordinator.push_media(
                    chunk.samples, frame, chunk.captured, arrival=chunk.arrival,
                    media_fault=chunk.fault)
                self.media_chunks += 1
                if self.status_callback is not None:
                    self.status_callback(result, self.stats())
            if self.board_error is not None:
                raise RuntimeError("board acquisition stopped") from self.board_error
            return self.stats()
        finally:
            self.stop_event.set()
            self.microphone.stop()
            if self.camera is not None:
                self.camera.stop()
            if self.board_thread is not None:
                self.board_thread.join(timeout=2.0)
            self.coordinator.close()

    def stats(self):
        return {
            "media_chunks": self.media_chunks,
            "camera_matches": self.camera_matches,
            "camera_misses": self.camera_misses,
            "media_faults": self.media_faults,
            "microphone": self.microphone.stats(),
            "camera": None if self.camera is None else self.camera.stats(),
            "coordinator": self.coordinator.stats(),
        }
