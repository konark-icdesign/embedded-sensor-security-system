from pathlib import Path
import tempfile
import unittest

from scripts.prepare_bench_firmware import _bench_commands
from scripts.run_board_bench import (
    _firmware_build_match_state,
    _firmware_identity_state,
    _resolve_firmware_build_paths,
)


class BenchFirmwareProvenanceTests(unittest.TestCase):
    def test_build_match_state_distinguishes_expected_failures(self):
        self.assertEqual(
            _firmware_build_match_state(None, []),
            "not-requested",
        )
        self.assertEqual(
            _firmware_build_match_state("gabc-sdef", []),
            "board-id-missing",
        )
        self.assertEqual(
            _firmware_build_match_state(
                "gabc-sdef",
                ["gold-s111", "gnew-s222"],
            ),
            "multiple-board-ids",
        )
        self.assertEqual(
            _firmware_build_match_state(
                "gabc-sdef",
                ["gwrong-s999"],
            ),
            "mismatch",
        )
        self.assertEqual(
            _firmware_build_match_state(
                "gabc-sdef",
                ["gabc-sdef"],
            ),
            "match",
        )

    def test_prepared_build_dir_resolves_manifest_and_artifacts_together(self):
        with tempfile.TemporaryDirectory() as td:
            build_dir = Path(td) / "prepared build"
            manifest, artifacts, mode = _resolve_firmware_build_paths(
                prepared_build_dir=build_dir,
            )

        self.assertEqual(
            Path(manifest),
            build_dir.resolve() / "firmware_build_manifest.json",
        )
        self.assertEqual(Path(artifacts), build_dir.resolve())
        self.assertEqual(mode, "prepared-build-dir")

    def test_prepared_build_dir_rejects_mixed_legacy_arguments(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot be combined",
        ):
            _resolve_firmware_build_paths(
                prepared_build_dir="prepared",
                firmware_build_manifest="manifest.json",
                firmware_artifact_dir="artifacts",
            )

    def test_partial_legacy_build_binding_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be supplied together",
        ):
            _resolve_firmware_build_paths(
                firmware_build_manifest="manifest.json",
            )

    def test_generated_trial_commands_keep_one_build_and_rediscover_port(self):
        commands = _bench_commands(
            Path("results") / "firmware-build" / "prepared build"
        )

        self.assertEqual(
            set(commands),
            {"steady", "reconnect", "range_example"},
        )
        for command in commands.values():
            self.assertIn("--port auto", command)
            self.assertIn("--prepared-build-dir", command)
            self.assertIn('"results/firmware-build/prepared build"', command)
            self.assertNotIn("--firmware-build-manifest", command)
            self.assertNotIn("--firmware-artifact-dir", command)

        self.assertIn("--label usb-idle", commands["steady"])
        self.assertIn("--label usb-reconnect", commands["reconnect"])
        self.assertIn("--reference-distance-m 1.0", commands["range_example"])

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
