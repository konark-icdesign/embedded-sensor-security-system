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
    return (
        f"S,{seq},{ms},{p},{m},{u},{value},{valid},0,1,{degraded},"
        f"{fallback},0"
    )


class FakeStream:
    instances = []

    def __init__(self, directory):
        self.directory = Path(directory)
        self.records = []
        self.closed = False
        FakeStream.instances.append(self)

    def push(self, seq, captured, audio, frame, physical, session,
             arrival=None, fallback=False):
        self.records.append({
            "seq": seq,
            "captured": captured,
            "audio": audio,
            "frame": frame,
            "physical": dict(physical),
            "session": session,
            "arrival": arrival,
            "fallback": fallback,
        })
        return {"accepted": True, "state": "GREEN", "id": None, "closed": None}

    def close(self):
        self.closed = True


class CombinedAcquisitionTests(unittest.TestCase):
    def setUp(self):
        FakeStream.instances = []

    def test_media_waits_until_board_state_exists(self):
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            result = c.push_media([0.0], None, 10.0, 10.01)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"], "waiting_for_board")
            self.assertEqual(len(FakeStream.instances), 0)
            c.close()

    def test_media_has_own_sequence_when_one_board_sample_is_reused(self):
        adapter = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            b = adapter.ingest(wire(7, 1000, p=1), 10.010)
            c.on_board_sample(b)
            a = c.push_media([0.0], None, b.captured + .020, b.captured + .025)
            d = c.push_media([0.0], None, b.captured + .050, b.captured + .055)
            self.assertTrue(a["accepted"] and d["accepted"])
            self.assertEqual([r["seq"] for r in FakeStream.instances[0].records], [1, 2])
            self.assertEqual([r["session"] for r in FakeStream.instances[0].records],
                             [b.session, b.session])
            c.close()

    def test_stale_board_state_is_forwarded_only_as_fault(self):
        adapter = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            b = adapter.ingest(wire(0, 1000, p=1, m=1, u=1, fallback=1), 10.010)
            c.on_board_sample(b)
            result = c.push_media([0.0], None, b.captured + .151, b.captured + .155)
            record = FakeStream.instances[0].records[-1]
            self.assertTrue(result["accepted"])
            self.assertFalse(result["board_match"]["matched"])
            self.assertEqual(record["physical"],
                             {"P": False, "M": False, "U": False, "fault": True})
            self.assertFalse(record["fallback"])
            self.assertEqual(c.stats()["stale_board_packets"], 1)
            c.close()

    def test_reboot_closes_old_stream_and_resets_media_sequence(self):
        adapter = BoardSerialAdapter()
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, None, stream_factory=FakeStream)
            old = adapter.ingest(wire(50, 60000, p=1), 100.010)
            c.on_board_sample(old)
            first = c.push_media([0.0], None, old.captured + .020)
            reboot = adapter.ingest(wire(0, 120, m=1), 100.300)
            c.on_board_sample(reboot)
            self.assertTrue(FakeStream.instances[0].closed)
            second = c.push_media([0.0], None, reboot.captured + .020)
            self.assertEqual(first["media_seq"], 1)
            self.assertEqual(second["media_seq"], 1)
            self.assertNotEqual(first["session"], second["session"])
            self.assertEqual(c.stats()["stream_rotations"], 1)
            self.assertEqual(len(FakeStream.instances), 2)
            c.close()

    def test_real_roomstream_receives_synchronized_physical_flags(self):
        adapter = BoardSerialAdapter()
        model = Baseline(np.zeros(9), np.ones(9), threshold=999.0)
        t = np.arange(1600) / 16000.0
        audio = 0.01 * np.sin(2 * np.pi * 440 * t)
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, model)
            b = adapter.ingest(wire(0, 1000, p=1, u=1), 10.010)
            c.on_board_sample(b)
            result = c.push_media(audio, None, b.captured + .050, b.captured + .055)
            self.assertTrue(result["accepted"])
            history = c.current_stream.journal.history()
            self.assertEqual(len(history), 1)
            self.assertTrue(history[0]["flags"]["P"])
            self.assertTrue(history[0]["flags"]["U"])
            self.assertFalse(history[0]["flags"]["M"])
            c.close()

    def test_reboot_creates_separate_persistent_journal_directories(self):
        adapter = BoardSerialAdapter()
        model = Baseline(np.zeros(9), np.ones(9), threshold=999.0)
        audio = np.sin(2 * np.pi * 440 * np.arange(1600) / 16000.0) * .01
        with tempfile.TemporaryDirectory() as td:
            c = CombinedAcquisitionCoordinator(td, model)
            old = adapter.ingest(wire(10, 20000, p=1), 20.010)
            c.on_board_sample(old)
            c.push_media(audio, None, old.captured + .050)
            new = adapter.ingest(wire(0, 100, m=1), 20.300)
            c.on_board_sample(new)
            c.push_media(audio, None, new.captured + .050)
            paths = dict(c.stats()["session_directories"])
            c.close()

            self.assertEqual(set(paths), {old.session, new.session})
            old_db = Path(paths[old.session]) / "journal.sqlite"
            new_db = Path(paths[new.session]) / "journal.sqlite"
            self.assertTrue(old_db.exists() and new_db.exists())
            with sqlite3.connect(old_db) as db:
                old_payload = json.loads(db.execute(
                    "SELECT payload FROM history ORDER BY stamp LIMIT 1"
                ).fetchone()[0])
            with sqlite3.connect(new_db) as db:
                new_payload = json.loads(db.execute(
                    "SELECT payload FROM history ORDER BY stamp LIMIT 1"
                ).fetchone()[0])
            self.assertEqual(old_payload["session"], old.session)
            self.assertEqual(new_payload["session"], new.session)


if __name__ == "__main__":
    unittest.main()
