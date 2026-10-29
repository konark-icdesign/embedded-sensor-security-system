import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from src.arduino_toolchain import sha256_file
from src.bench_firmware_prepare import (
    parse_cli_version,
    parse_installed_core_version,
    prepare_bench_firmware,
)


class FakeArduinoRunner:
    def __init__(self, cli_version="1.5.1", core_version="1.6.0"):
        self.cli_version = cli_version
        self.core_version = core_version
        self.commands = []

    def __call__(
        self,
        command,
        *,
        cwd,
        text,
        capture_output,
        timeout,
    ):
        self.commands.append(list(command))
        args = list(command)[1:]

        if args == ["version"]:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "arduino-cli Version: {} Commit: test Date: test\n"
                ).format(self.cli_version),
                stderr="",
            )

        if args == ["core", "list"]:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "ID Installed Latest Name\n"
                    "arduino:renesas_uno {} {} Arduino UNO R4 Boards\n"
                ).format(self.core_version, self.core_version),
                stderr="",
            )

        if args and args[0] == "compile":
            output_index = args.index("--output-dir") + 1
            output = Path(args[output_index])
            output.mkdir(parents=True, exist_ok=True)
            (output / "night_security.ino.bin").write_bytes(b"binary")
            (output / "night_security.ino.elf").write_bytes(b"elf")
            return SimpleNamespace(returncode=0, stdout="compiled\n", stderr="")

        if args and args[0] == "upload":
            return SimpleNamespace(returncode=0, stdout="uploaded\n", stderr="")

        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="unexpected fake command",
        )


def make_repo(root):
    repo = root / "repo"
    firmware = repo / "firmware" / "night_security"
    firmware.mkdir(parents=True)
    (firmware / "night_security.ino").write_text(
        "void setup() {}\nvoid loop() {}\n",
        encoding="utf-8",
    )

    tools = root / "arduino-tools"
    tools.mkdir()
    cli = tools / "arduino-cli"
    cli.write_bytes(b"fake-arduino-cli")
    return repo, cli


class BenchFirmwarePrepareTests(unittest.TestCase):
    def test_parses_cli_and_core_versions(self):
        self.assertEqual(
            parse_cli_version(
                "arduino-cli Version: 1.5.1 Commit: abc Date: now"
            ),
            "1.5.1",
        )
        self.assertEqual(
            parse_installed_core_version(
                "ID Installed Latest Name\n"
                "arduino:renesas_uno 1.6.0 1.6.1 Arduino UNO R4 Boards\n"
            ),
            "1.6.0",
        )

    def test_prepare_hashes_actual_cli_and_compiled_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, cli = make_repo(root)
            build_dir = repo / "results" / "firmware-build" / "test"
            runner = FakeArduinoRunner()

            result = prepare_bench_firmware(
                repo_root=repo,
                build_dir=build_dir,
                cli_asset_id="linux64",
                revision="abc123def456789",
                runner=runner,
            )

            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )

        self.assertTrue(result["ok"])
        self.assertFalse(result["uploaded"])
        self.assertEqual(result["artifact_count"], 2)
        self.assertEqual(result["cli_version"], "1.5.1")
        self.assertEqual(result["core_version"], "1.6.0")
        self.assertEqual(
            manifest["arduino_cli_executable_sha256"],
            sha256_file(cli),
        )
        self.assertEqual(manifest["arduino_cli_asset"], "linux64")
        self.assertEqual(manifest["artifact_count"], 2)
        self.assertTrue(any(
            row["path"].endswith(".bin")
            and row["flash_candidate"]
            for row in manifest["artifacts"]
        ))

    def test_upload_auto_uses_exact_prebuilt_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, _ = make_repo(root)
            build_dir = repo / "results" / "firmware-build" / "test"
            runner = FakeArduinoRunner()

            result = prepare_bench_firmware(
                repo_root=repo,
                build_dir=build_dir,
                cli_asset_id="linux64",
                revision="abc123def456789",
                upload_port="auto",
                runner=runner,
                port_resolver=lambda: "COM7",
            )

            upload = next(
                command
                for command in runner.commands
                if len(command) > 1 and command[1] == "upload"
            )

        self.assertTrue(result["uploaded"])
        self.assertEqual(result["upload_port"], "COM7")
        self.assertIn("COM7", upload)
        self.assertEqual(
            Path(upload[upload.index("--input-dir") + 1]),
            build_dir.resolve(),
        )

    def test_rejects_wrong_cli_version_before_compile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, _ = make_repo(root)
            runner = FakeArduinoRunner(cli_version="1.5.0")

            with self.assertRaisesRegex(
                RuntimeError,
                "Arduino CLI version mismatch",
            ):
                prepare_bench_firmware(
                    repo_root=repo,
                    build_dir=repo / "results" / "firmware-build" / "test",
                    cli_asset_id="linux64",
                    revision="abc123def456789",
                    runner=runner,
                )

        self.assertFalse(any(
            len(command) > 1 and command[1] == "compile"
            for command in runner.commands
        ))

    def test_rejects_wrong_core_version_before_compile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, _ = make_repo(root)
            runner = FakeArduinoRunner(core_version="1.5.0")

            with self.assertRaisesRegex(
                RuntimeError,
                "UNO R4 core version mismatch",
            ):
                prepare_bench_firmware(
                    repo_root=repo,
                    build_dir=repo / "results" / "firmware-build" / "test",
                    cli_asset_id="linux64",
                    revision="abc123def456789",
                    runner=runner,
                )

        self.assertFalse(any(
            len(command) > 1 and command[1] == "compile"
            for command in runner.commands
        ))

    def test_refuses_nonempty_build_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, _ = make_repo(root)
            build_dir = repo / "results" / "firmware-build" / "test"
            build_dir.mkdir(parents=True)
            (build_dir / "stale.bin").write_bytes(b"stale")

            with self.assertRaisesRegex(
                RuntimeError,
                "build directory is not empty",
            ):
                prepare_bench_firmware(
                    repo_root=repo,
                    build_dir=build_dir,
                    cli_asset_id="linux64",
                    revision="abc123def456789",
                    runner=FakeArduinoRunner(),
                )


if __name__ == "__main__":
    unittest.main()
