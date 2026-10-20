from pathlib import Path
import tempfile
import unittest

from src.firmware_identity import (
    build_identity,
    source_sha256,
    write_identity_files,
)


class FirmwareIdentityTests(unittest.TestCase):
    def test_source_hash_changes_when_firmware_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text("void setup() {}\n", encoding="utf-8")
            (root / "core.h").write_text("#pragma once\n", encoding="utf-8")
            first, files = source_sha256(root)
            (root / "core.h").write_text(
                "#pragma once\n// changed\n",
                encoding="utf-8",
            )
            second, _ = source_sha256(root)

        self.assertEqual(files, ["core.h", "main.ino"])
        self.assertNotEqual(first, second)

    def test_generated_identity_files_do_not_change_source_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text("void setup() {}\n", encoding="utf-8")
            first, _ = source_sha256(root)
            (root / "build_identity.h").write_text(
                '#define SECURITY_FIRMWARE_BUILD_ID "old"\n',
                encoding="utf-8",
            )
            (root / "firmware_build_identity.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            second, _ = source_sha256(root)

        self.assertEqual(first, second)

    def test_build_id_contains_revision_source_hash_and_dirty_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text("void setup() {}\n", encoding="utf-8")
            identity = build_identity(
                root,
                revision="1234567890abcdef",
                dirty=True,
            )

        self.assertTrue(identity["build_id"].startswith("g1234567890ab-s"))
        self.assertTrue(identity["build_id"].endswith("-dirty"))
        self.assertEqual(identity["git_revision"], "1234567890abcdef")

    def test_writer_creates_header_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text("void setup() {}\n", encoding="utf-8")
            identity = write_identity_files(
                root,
                revision="abcdef1234567890",
                dirty=False,
            )
            header = (root / "build_identity.h").read_text(encoding="utf-8")
            manifest = (
                root / "firmware_build_identity.json"
            ).read_text(encoding="utf-8")

        self.assertIn(identity["build_id"], header)
        self.assertIn(identity["source_sha256"], manifest)


if __name__ == "__main__":
    unittest.main()
