from pathlib import Path
import tempfile
import unittest

from src.firmware_identity import (
    build_context_sha256,
    build_identity,
    build_recipe_context,
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

    def test_build_recipe_changes_runtime_build_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text(
                "void setup() {}\n",
                encoding="utf-8",
            )
            base = build_recipe_context(
                cli_version="1.5.1",
                core_version="1.6.0",
                fqbn="arduino:renesas_uno:unor4wifi",
                cli_asset_id="linux64",
                cli_executable_sha256="a" * 64,
            )
            changed = dict(base)
            changed["arduino_core_version"] = "1.6.1"

            first = build_identity(
                root,
                revision="1234567890abcdef",
                dirty=False,
                build_context=base,
            )
            second = build_identity(
                root,
                revision="1234567890abcdef",
                dirty=False,
                build_context=changed,
            )

        self.assertNotEqual(first["build_id"], second["build_id"])
        self.assertIn("-b", first["build_id"])
        self.assertEqual(
            first["source_sha256"],
            second["source_sha256"],
        )

    def test_build_context_hash_is_key_order_independent(self):
        left = {"b": "two", "a": "one"}
        right = {"a": "one", "b": "two"}
        self.assertEqual(
            build_context_sha256(left),
            build_context_sha256(right),
        )

    def test_writer_creates_header_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.ino").write_text("void setup() {}\n", encoding="utf-8")
            context = build_recipe_context(
                cli_version="1.5.1",
                core_version="1.6.0",
                fqbn="arduino:renesas_uno:unor4wifi",
                cli_asset_id="linux64",
                cli_executable_sha256="a" * 64,
            )
            identity = write_identity_files(
                root,
                revision="abcdef1234567890",
                dirty=False,
                build_context=context,
            )
            header = (root / "build_identity.h").read_text(encoding="utf-8")
            manifest = (
                root / "firmware_build_identity.json"
            ).read_text(encoding="utf-8")

        self.assertIn(identity["build_id"], header)
        self.assertIn(identity["source_sha256"], manifest)
        self.assertIn(identity["build_context_sha256"], manifest)
        self.assertIn("-b", identity["build_id"])


if __name__ == "__main__":
    unittest.main()
