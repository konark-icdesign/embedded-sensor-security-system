import math
import unittest
from src.board_serial import BoardPacketError, BoardSerialAdapter, parse_sensor_line


def packet(seq, ms, drops=0, *, p=0, m=0, u=0, metres=3.0, valid=1,
           alarm=0, armed=1, degraded=0, fallback=0):
    value = "nan" if not valid and math.isnan(metres) else str(metres)
    return f"S,{seq},{ms},{p},{m},{u},{value},{valid},{alarm},{armed},{degraded},{fallback},{drops}"


class BoardSerialTests(unittest.TestCase):
    def test_parse_real_wire_shape(self):
        p = parse_sensor_line(packet(7, 61234, p=1, m=1, u=1, metres=1.234))
        self.assertEqual(p.sequence, 7)
        self.assertTrue(p.pir and p.radar and p.near)
        self.assertAlmostEqual(p.range_metres, 1.234)

    def test_arrival_jitter_refines_offset_without_breaking_monotonic_time(self):
        a = BoardSerialAdapter()
        x0 = a.ingest(packet(0, 60000), 100.012)
        x1 = a.ingest(packet(1, 60100), 100.118)
        x2 = a.ingest(packet(2, 60200), 100.210)
        self.assertGreater(x1.captured, x0.captured)
        self.assertGreater(x2.captured, x1.captured)
        self.assertLessEqual(abs((x2.captured - x1.captured) - .1), .005)

    def test_gap_and_board_drop_accounting(self):
        a = BoardSerialAdapter()
        a.ingest(packet(10, 60000), 100.020)
        s = a.ingest(packet(13, 60300, 2), 100.322)
        self.assertEqual(s.missing_before, 2)
        self.assertEqual(s.board_reported_drops_delta, 2)
        self.assertEqual(a.stats()["sequence_gaps"], 2)

    def test_usb_reconnect_gap_keeps_session(self):
        a = BoardSerialAdapter()
        s0 = a.ingest(packet(100, 60000), 50.010)
        s1 = a.ingest(packet(105, 60500, 4), 50.515)
        self.assertEqual(s0.session, s1.session)
        self.assertEqual(s1.missing_before, 4)
        self.assertAlmostEqual(s1.captured - s0.captured, .5, places=9)

    def test_reboot_starts_new_session(self):
        a = BoardSerialAdapter()
        old = a.ingest(packet(400, 90000, 3), 200.010)
        new = a.ingest(packet(0, 120, 0), 200.250)
        self.assertNotEqual(old.session, new.session)
        self.assertEqual(new.missing_before, 0)
        self.assertEqual(a.stats()["reboots"], 1)

    def test_uint32_wrap_is_not_reboot(self):
        a = BoardSerialAdapter()
        first = a.ingest(packet(0xFFFFFFFE, 0xFFFFFF00), 300.010)
        second = a.ingest(packet(1, 0x0000002C), 300.310)
        self.assertEqual(first.session, second.session)
        self.assertEqual(second.missing_before, 2)
        self.assertEqual(a.stats()["reboots"], 0)
        self.assertGreater(second.board_millis_unwrapped, first.board_millis_unwrapped)

    def test_duplicate_and_bad_boolean_rejected(self):
        a = BoardSerialAdapter()
        a.ingest(packet(1, 100), 10.010)
        with self.assertRaises(BoardPacketError):
            a.ingest(packet(1, 200), 10.210)
        with self.assertRaises(BoardPacketError):
            parse_sensor_line("S,2,300,2,0,0,3.0,1,0,1,0,0,0")

    def test_latency_limit_matches_incident_gate(self):
        a = BoardSerialAdapter()
        a.ingest(packet(1, 1000), 10.000)
        with self.assertRaises(BoardPacketError):
            a.ingest(packet(2, 1100), 10.700)

    def test_room_stream_mapping(self):
        a = BoardSerialAdapter()
        s = a.ingest(packet(1, 1000, p=1, m=1, u=1, fallback=1), 10.010)
        fields = s.room_push_fields()
        self.assertEqual(fields["physical"], {"P": True, "M": True, "U": True, "fault": False})
        self.assertTrue(fields["fallback"])
        self.assertEqual(fields["session"], s.session)


if __name__ == "__main__":
    unittest.main()
