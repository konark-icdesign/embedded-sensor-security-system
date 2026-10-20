import unittest

from scripts.run_board_bench import _firmware_identity_state


class BenchFirmwareProvenanceTests(unittest.TestCase):
    def test_missing_identity_is_explicit(self):
        self.assertEqual(
            _firmware_identity_state({}),
            "missing",
        )

    def test_unstamped_firmware_is_explicit(self):
        self.assertEqual(
            _firmware_identity_state({
                "firmware_ids_seen": ["UNSTAMPED"]
            }),
            "unstamped",
        )

    def test_single_stamped_identity_is_reported(self):
        self.assertEqual(
            _firmware_identity_state({
                "firmware_ids_seen": ["gabc-sdef"]
            }),
            "reported",
        )

    def test_identity_change_during_capture_is_not_hidden(self):
        self.assertEqual(
            _firmware_identity_state({
                "firmware_ids_seen": ["gold-s111", "gnew-s222"]
            }),
            "changed-during-capture",
        )


if __name__ == "__main__":
    unittest.main()
