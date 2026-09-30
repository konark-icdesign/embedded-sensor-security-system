import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

import numpy as np

from src.board_serial import BoardSerialAdapter
from src.live_pipeline import CombinedAcquisitionCoordinator
from src.dsp import Baseline


def wire(seq, ms, p=0, m=0, u=0, valid=1, degraded=0, fallback=0):
    value = "1.200" if valid else "nan"
    return f"S,{seq},{ms},{p},{m},{u},{value},{valid},0,1,{degraded},{fallback},0"


class FakeStream:
    instances = []
    def __init__(self, directory):
        self.directory = Path(directory)
        self.records = []
        self.closed = False
        FakeStream.instances.append(self)
    def push(self, seq, captured, audio, frame, physical, session,
             arrival=None, fallback=False):
        self.records.append({"seq": seq, "captured": captured, "audio": audio,
            "frame": frame, "physical": dict(physical), "session": session,
            "arrival": arrival, "fallback": fallback})
        return {"accepted": True, "state": "GREEN", "id": None, "closed": None}
    def close(self):
        self.closed = True


class CombinedAcquisitionTests(unittest.TestCase):
    def setUp(self):
        FakeStream.instances = []

    def test_media_waits_until_board_state_exists(self):
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            r = c.push_media([0.0], None, 10.0, 10.01)
            self.assertFalse(r["accepted"])
            self.assertEqual(r["reason"], "waiting_for_board")
            c.close()

    def test_media_has_own_sequence_when_one_board_sample_is_reused(self):
        a = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            b = a.ingest(wire(7, 1000, p=1), 10.010)
            c.on_board_sample(b)
            x = c.push_media([0.0], None, b.captured+.020, b.captured+.025)
            y = c.push_media([0.0], None, b.captured+.050, b.captured+.055)
            self.assertTrue(x["accepted"] and y["accepted"])
            self.assertEqual([r["seq"] for r in FakeStream.instances[0].records], [1, 2])
            c.close()

    def test_stale_board_state_is_forwarded_only_as_fault(self):
        a = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            b = a.ingest(wire(0, 1000, p=1, m=1, u=1, fallback=1), 10.010)
            c.on_board_sample(b)
            r = c.push_media([0.0], None, b.captured+.151, b.captured+.155)
            rec = FakeStream.instances[0].records[-1]
            self.assertFalse(r["board_match"]["matched"])
            self.assertEqual(rec["physical"],
                             {"P": False, "M": False, "U": False, "fault": True})
            self.assertFalse(rec["fallback"])
            c.close()

    def test_reboot_rotation_is_deferred_to_media_thread(self):
        a = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            old = a.ingest(wire(50, 60000, p=1), 100.010)
            c.on_board_sample(old)
            first = c.push_media([0.0], None, old.captured+.020)
            reboot = a.ingest(wire(0, 120, m=1), 100.300)
            c.on_board_sample(reboot)
            self.assertFalse(FakeStream.instances[0].closed)
            second = c.push_media([0.0], None, reboot.captured+.020)
            self.assertTrue(FakeStream.instances[0].closed)
            self.assertEqual(first["media_seq"], 1)
            self.assertEqual(second["media_seq"], 1)
            self.assertEqual(c.stats()["stream_rotations"], 1)
            c.close()

    def test_media_fault_marks_packet_health(self):
        a = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            b = a.ingest(wire(0, 1000, p=1), 10.010)
            c.on_board_sample(b)
            r = c.push_media([0.0], None, b.captured+.020,
                             b.captured+.025, media_fault=True)
            self.assertTrue(r["media_fault"])
            self.assertTrue(FakeStream.instances[0].records[-1]["physical"]["fault"])
            self.assertEqual(c.stats()["media_fault_packets"], 1)
            c.close()

    def test_real_roomstream_receives_synchronized_physical_flags(self):
        a = BoardSerialAdapter()
        model = Baseline(np.zeros(9), np.ones(9), threshold=999.0)
        audio = .01*np.sin(2*np.pi*440*np.arange(1600)/16000.0)
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, model)
            b = a.ingest(wire(0, 1000, p=1, u=1), 10.010)
            c.on_board_sample(b)
            self.assertTrue(c.push_media(audio, None, b.captured+.050,
                                         b.captured+.055)["accepted"])
            h = c.current_stream.journal.history()
            self.assertTrue(h[0]["flags"]["P"])
            self.assertTrue(h[0]["flags"]["U"])
            self.assertFalse(h[0]["flags"]["M"])
            c.close()

    def test_reboot_creates_separate_persistent_journal_directories(self):
        a = BoardSerialAdapter()
        model = Baseline(np.zeros(9), np.ones(9), threshold=999.0)
        audio = .01*np.sin(2*np.pi*440*np.arange(1600)/16000.0)
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, model)
            old = a.ingest(wire(10, 20000, p=1), 20.010)
            c.on_board_sample(old)
            c.push_media(audio, None, old.captured+.050)
            new = a.ingest(wire(0, 100, m=1), 20.300)
            c.on_board_sample(new)
            c.push_media(audio, None, new.captured+.050)
            paths = dict(c.stats()["session_directories"])
            c.close()
            with sqlite3.connect(Path(paths[old.session])/"journal.sqlite") as db:
                oldp = json.loads(db.execute(
                    "SELECT payload FROM history ORDER BY stamp LIMIT 1").fetchone()[0])
            with sqlite3.connect(Path(paths[new.session])/"journal.sqlite") as db:
                newp = json.loads(db.execute(
                    "SELECT payload FROM history ORDER BY stamp LIMIT 1").fetchone()[0])
            self.assertEqual(oldp["session"], old.session)
            self.assertEqual(newp["session"], new.session)


if __name__ == "__main__":
    unittest.main()
