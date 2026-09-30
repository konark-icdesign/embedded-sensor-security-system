import unittest

from src.board_serial import BoardSerialAdapter
from src.board_sync import BoardMediaSynchronizer


def wire(seq, ms, p=0, m=0, u=0, valid=1, degraded=0, fallback=0):
    metres = "1.200" if valid else "nan"
    return (
        f"S,{seq},{ms},{p},{m},{u},{metres},{valid},0,1,{degraded},"
        f"{fallback},0"
    )


class BoardMediaSynchronizerTests(unittest.TestCase):
    def test_matches_latest_non_future_sample(self):
        adapter = BoardSerialAdapter()
        sync = BoardMediaSynchronizer(max_age=.15)
        a = adapter.ingest(wire(0, 1000, p=1), 10.010)
        b = adapter.ingest(wire(1, 1100, m=1), 10.115)
        sync.ingest(a)
        sync.ingest(b)

        early = sync.match(a.captured + .050)
        late = sync.match(b.captured + .040)
        self.assertTrue(early.matched)
        self.assertTrue(early.physical["P"])
        self.assertFalse(early.physical["M"])
        self.assertTrue(late.matched)
        self.assertTrue(late.physical["M"])

    def test_future_sample_is_not_used(self):
        adapter = BoardSerialAdapter()
        sync = BoardMediaSynchronizer()
        sample = adapter.ingest(wire(0, 1000, p=1), 10.010)
        sync.ingest(sample)
        match = sync.match(sample.captured - .001)
        self.assertFalse(match.matched)
        self.assertEqual(match.reason, "no_board_sample")
        self.assertTrue(match.physical["fault"])

    def test_stale_sample_becomes_fault_and_does_not_reuse_flags(self):
        adapter = BoardSerialAdapter()
        sync = BoardMediaSynchronizer(max_age=.15)
        sample = adapter.ingest(wire(0, 1000, p=1, m=1, u=1), 10.010)
        sync.ingest(sample)
        match = sync.match(sample.captured + .151)
        self.assertFalse(match.matched)
        self.assertEqual(match.reason, "stale_board_sample")
        self.assertEqual(match.physical, {"P": False, "M": False, "U": False, "fault": True})
        self.assertFalse(match.fallback)

    def test_reboot_clears_pre_reboot_buffer(self):
        adapter = BoardSerialAdapter()
        sync = BoardMediaSynchronizer(max_age=.15)
        old = adapter.ingest(wire(100, 50000, p=1), 100.010)
        sync.ingest(old)
        reboot = adapter.ingest(wire(0, 100, m=1), 100.250)
        sync.ingest(reboot)

        self.assertEqual(sync.stats()["session_changes"], 1)
        self.assertEqual(sync.stats()["buffered_samples"], 1)
        self.assertEqual(sync.session, reboot.session)
        match = sync.match(reboot.captured + .010)
        self.assertTrue(match.matched)
        self.assertFalse(match.physical["P"])
        self.assertTrue(match.physical["M"])

    def test_fallback_provenance_passes_only_on_fresh_match(self):
        adapter = BoardSerialAdapter()
        sync = BoardMediaSynchronizer(max_age=.15)
        sample = adapter.ingest(wire(0, 1000, fallback=1), 10.010)
        sync.ingest(sample)
        self.assertTrue(sync.match(sample.captured + .010).fallback)
        self.assertFalse(sync.match(sample.captured + .200).fallback)


if __name__ == "__main__":
    unittest.main()
