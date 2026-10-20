import json
from pathlib import Path
import tempfile
import unittest

from src.arduino_toolchain import (
    ARDUINO_CLI_LINUX64_SHA256,
    ARDUINO_CLI_VERSION,
    cli_linux64_url,
    verify_sha256,
)
from src.firmware_build_manifest import (
    build_manifest,
    collect_artifacts,
)


class ArduinoToolchainTests(unittest.TestCase):
    def test_cli_download_is_version_pinned(self):
        url = cli_linux64_url()
        self.assertIn("/v{}/".format(ARDUINO_CLI_VERSION), url)
        self.assertIn(
            "arduino-cli_{}_Linux_64bit.tar.gz".format(
                ARDUINO_CLI_VERSION
            ),
            url,
        )
        self.assertEqual(len(ARDUINO_CLI_LINUX64_SHA256), 64)

    def test_checksum_verification_rejects_wrong_archive(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cli.tar.gz"
            path.write_bytes(b"not the real archive")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_sha256(path, "0" * 64)


class FirmwareBuildManifestTests(unittest.TestCase):
    def test_manifest_hashes_flash_and_elf_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            (artifacts / "night_security.ino.bin").write_bytes(b"binary")
            (artifacts / "night_security.ino.elf").write_bytes(b"elf")
            identity = root / "identity.json"
            identity.write_text(
                json.dumps({
                    "build_id": "gabc-sdef",
                    "source_sha256": "a" * 64,
                    "git_revision": "abc",
                    "git_dirty": False,
                }) + "\n",
                encoding="utf-8",
            )

            manifest = build_manifest(
                artifacts,
                identity,
                cli_version="1.5.1",
                core_version="1.6.0",
                fqbn="arduino:renesas_uno:unor4wifi",
            )

        self.assertEqual(manifest["firmware_build_id"], "gabc-sdef")
        self.assertEqual(manifest["artifact_count"], 2)
        self.assertTrue(any(
            row["path"].endswith(".bin")
            and row["flash_candidate"]
            for row in manifest["artifacts"]
        ))
        self.assertTrue(any(
            row["path"].endswith(".elf")
            and not row["flash_candidate"]
            for row in manifest["artifacts"]
        ))
        self.assertTrue(all(
            len(row["sha256"]) == 64
            for row in manifest["artifacts"]
        ))

    def test_manifest_requires_flashable_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "only.elf").write_bytes(b"elf")
            with self.assertRaisesRegex(ValueError, "flashable"):
                collect_artifacts(root)


if __name__ == "__main__":
    unittest.main()
