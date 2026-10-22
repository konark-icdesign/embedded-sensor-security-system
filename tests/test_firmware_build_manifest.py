import json
from pathlib import Path
import tempfile
import unittest

from src.arduino_toolchain import (
    ARDUINO_CLI_LINUX64_SHA256,
    ARDUINO_CLI_VERSION,
    ARDUINO_CLI_WINDOWS64_SHA256,
    cli_asset,
    cli_linux64_url,
    detect_cli_asset_id,
    verify_sha256,
)
from src.firmware_build_manifest import (
    build_manifest,
    collect_artifacts,
    verify_manifest_artifacts,
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

    def test_windows_x64_asset_is_pinned(self):
        self.assertEqual(
            detect_cli_asset_id("Windows", "AMD64"),
            "windows64",
        )
        asset = cli_asset("windows64")
        self.assertEqual(
            asset["archive_name"],
            "arduino-cli_1.5.1_Windows_64bit.zip",
        )
        self.assertEqual(
            asset["sha256"],
            ARDUINO_CLI_WINDOWS64_SHA256,
        )
        self.assertEqual(asset["executable"], "arduino-cli.exe")
        self.assertEqual(len(ARDUINO_CLI_WINDOWS64_SHA256), 64)

    def test_linux_x64_asset_detection_is_stable(self):
        self.assertEqual(
            detect_cli_asset_id("Linux", "x86_64"),
            "linux64",
        )

    def test_unsupported_host_is_rejected(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "unsupported Arduino CLI host platform",
        ):
            detect_cli_asset_id("Plan9", "mips")

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
                cli_asset_id="linux64",
            )

        self.assertEqual(manifest["firmware_build_id"], "gabc-sdef")
        self.assertEqual(manifest["arduino_cli_asset"], "linux64")
        self.assertEqual(
            manifest["arduino_cli_archive_sha256"],
            ARDUINO_CLI_LINUX64_SHA256,
        )
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

    def test_windows_manifest_records_windows_cli_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            (artifacts / "night_security.ino.bin").write_bytes(b"binary")
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
                cli_asset_id="windows64",
            )

        self.assertEqual(manifest["arduino_cli_asset"], "windows64")
        self.assertEqual(
            manifest["arduino_cli_archive_sha256"],
            ARDUINO_CLI_WINDOWS64_SHA256,
        )

    def test_verifier_accepts_untampered_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            binary = artifacts / "night_security.ino.bin"
            binary.write_bytes(b"binary")
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
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest) + "\n",
                encoding="utf-8",
            )

            verified = verify_manifest_artifacts(
                manifest_path,
                artifacts,
            )

        self.assertTrue(verified["ok"])
        self.assertEqual(verified["firmware_build_id"], "gabc-sdef")
        self.assertTrue(verified["artifacts"][0]["sha256_ok"])

    def test_verifier_detects_same_size_artifact_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            binary = artifacts / "night_security.ino.bin"
            binary.write_bytes(b"abc")
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
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest) + "\n",
                encoding="utf-8",
            )
            binary.write_bytes(b"abd")

            verified = verify_manifest_artifacts(
                manifest_path,
                artifacts,
            )

        self.assertFalse(verified["ok"])
        self.assertTrue(verified["artifacts"][0]["bytes_ok"])
        self.assertFalse(verified["artifacts"][0]["sha256_ok"])

    def test_verifier_rejects_manifest_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "schema": 1,
                    "firmware_build_id": "gabc-sdef",
                    "artifacts": [{
                        "path": "../outside.bin",
                        "bytes": 1,
                        "sha256": "0" * 64,
                    }],
                }) + "\n",
                encoding="utf-8",
            )
            verified = verify_manifest_artifacts(
                manifest_path,
                artifacts,
            )

        self.assertFalse(verified["ok"])
        self.assertEqual(
            verified["artifacts"][0]["error"],
            "unsafe artifact path",
        )

    def test_manifest_requires_flashable_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "only.elf").write_bytes(b"elf")
            with self.assertRaisesRegex(ValueError, "flashable"):
                collect_artifacts(root)


if __name__ == "__main__":
    unittest.main()
