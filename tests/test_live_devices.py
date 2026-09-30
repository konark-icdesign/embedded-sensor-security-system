import queue
import tempfile
import unittest
import numpy as np

from src.board_serial import BoardSerialAdapter
from src.dsp import Baseline
from src.live_devices import AudioChunk, CameraFrameBuffer, LiveHostRuntime, SoundDeviceMicrophone, map_portaudio_end_to_monotonic
from src.live_pipeline import CombinedAcquisitionCoordinator


def wire(seq, ms, p=0, m=0, u=0):
    return f"S,{seq},{ms},{p},{m},{u},1.2,1,0,1,0,0,0"


class Info:
    inputBufferAdcTime = 4.9
    currentTime = 5.0


class FakeBoardRunner:
    def __init__(self, samples):
        self.samples = list(samples)
        self.sample_callback = None
    def run(self, stop_event=None):
        for s in self.samples:
            self.sample_callback(s)
        if stop_event is not None:
            stop_event.wait(.2)
        return {}


class FakeMicrophone:
    def __init__(self, chunks):
        self.q = queue.Queue()
        for c in chunks:
            self.q.put(c)
    def start(self): pass
    def read(self, timeout=1.0): return self.q.get(timeout=timeout)
    def stop(self): pass
    def stats(self):
        return {"queue_drops": 0, "callback_faults": 0,
                "queued_chunks": self.q.qsize()}


class FakeCamera:
    def __init__(self, buffer):
        self.buffer = buffer
    def start(self): pass
    def stop(self): pass
    def stats(self): return {"frames": 1, "failures": 0}


class LiveDeviceTests(unittest.TestCase):
    def test_portaudio_clock_maps_buffer_end(self):
        captured, fault = map_portaudio_end_to_monotonic(
            100.020, 4.9, 5.0, 1600, 16000)
        self.assertFalse(fault)
        self.assertAlmostEqual(captured, 100.020, places=6)

    def test_impossible_mapping_falls_back_and_faults(self):
        captured, fault = map_portaudio_end_to_monotonic(
            100.0, 0.0, 10.0, 1600, 16000)
        self.assertTrue(fault)
        self.assertEqual(captured, 100.0)

    def test_microphone_queue_overflow_marks_chunk_faulty(self):
        mic = SoundDeviceMicrophone(queue_depth=1, clock=lambda: 100.0)
        data = np.zeros((1600, 1), dtype=np.float32)
        mic._callback(data, 1600, Info(), "")
        mic._callback(data, 1600, Info(), "")
        chunk = mic.read(timeout=.1)
        self.assertTrue(chunk.fault)
        self.assertIn("queue_drop", chunk.reason)
        self.assertEqual(mic.queue_drops, 1)

    def test_camera_buffer_never_uses_future_frame(self):
        b = CameraFrameBuffer()
        b.push(np.ones((2, 2), dtype=np.uint8), 10.0)
        b.push(np.ones((2, 2), dtype=np.uint8)*2, 10.2)
        frame, stamp = b.match(10.1, max_age=.3)
        self.assertEqual(stamp, 10.0)
        self.assertTrue(np.all(frame == 1))
        stale, stamp = b.match(10.5, max_age=.2)
        self.assertIsNone(stale)
        self.assertEqual(stamp, 10.2)

    def test_runtime_feeds_real_roomstream(self):
        a = BoardSerialAdapter()
        board = a.ingest(wire(0, 1000, p=1), 10.010)
        audio = .01*np.sin(2*np.pi*440*np.arange(1600)/16000.0)
        chunks = [
            AudioChunk(audio, board.captured+.05, board.captured+.055),
            AudioChunk(audio, board.captured+.10, board.captured+.105,
                       fault=True, reason="simulated_overflow"),
        ]
        buf = CameraFrameBuffer()
        buf.push(np.full((120,160),80,dtype=np.uint8), board.captured+.04)
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(
                td, Baseline(np.zeros(9), np.ones(9), threshold=999.0))
            rt = LiveHostRuntime(c, FakeBoardRunner([board]),
                                 FakeMicrophone(chunks), FakeCamera(buf))
            stats = rt.run(max_chunks=2)
            self.assertEqual(stats["media_chunks"], 2)
            self.assertEqual(stats["camera_matches"], 2)
            self.assertEqual(stats["media_faults"], 1)
            self.assertEqual(stats["coordinator"]["media_forwarded"], 2)
            self.assertEqual(stats["coordinator"]["media_fault_packets"], 1)


if __name__ == "__main__":
    unittest.main()
