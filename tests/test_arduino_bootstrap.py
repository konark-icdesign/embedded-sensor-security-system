import pathlib
import tarfile
import tempfile
import unittest
import zipfile

from scripts.bootstrap_arduino import _extract_cli
from src.arduino_toolchain import cli_asset


class ArduinoBootstrapExtractionTests(unittest.TestCase):
    def test_extracts_windows_executable_from_verified_zip_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            archive = root / "cli.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("nested/arduino-cli.exe", b"windows-cli")

            _extract_cli(archive, root, cli_asset("windows64"))

            self.assertEqual(
                (root / "arduino-cli.exe").read_bytes(),
                b"windows-cli",
            )

    def test_extracts_linux_executable_from_tar_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / "arduino-cli"
            source.write_bytes(b"linux-cli")
            archive = root / "cli.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                handle.add(source, arcname="nested/arduino-cli")
            source.unlink()

            _extract_cli(archive, root, cli_asset("linux64"))

            self.assertEqual(
                (root / "arduino-cli").read_bytes(),
                b"linux-cli",
            )


if __name__ == "__main__":
    unittest.main()
