"""Install a pinned Arduino CLI and UNO R4 board core for CI/bench builds."""

import argparse
import pathlib
import subprocess
import sys
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.arduino_toolchain import (
    ARDUINO_CLI_LINUX64_SHA256,
    ARDUINO_CLI_VERSION,
    ARDUINO_CORE_VERSION,
    cli_linux64_url,
    verify_sha256,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-version", default=ARDUINO_CORE_VERSION)
    parser.add_argument("--cli-version", default=ARDUINO_CLI_VERSION)
    parser.add_argument("--cli-sha256")
    args = parser.parse_args()

    expected_sha256 = args.cli_sha256
    if expected_sha256 is None:
        if args.cli_version != ARDUINO_CLI_VERSION:
            parser.error(
                "--cli-sha256 is required for an unrecognized CLI version"
            )
        expected_sha256 = ARDUINO_CLI_LINUX64_SHA256

    root = pathlib.Path(__file__).resolve().parents[2] / "arduino-tools"
    root.mkdir(exist_ok=True)
    archive = root / (
        "arduino-cli_{}_Linux_64bit.tar.gz".format(args.cli_version)
    )
    url = cli_linux64_url(args.cli_version)

    with urllib.request.urlopen(url, timeout=45) as response:
        archive.write_bytes(response.read())

    verify_sha256(archive, expected_sha256)

    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.name == "arduino-cli":
                tar.extract(member, root, filter="data")

    cli = str(root / "arduino-cli")
    commands = [
        [cli, "version"],
        [cli, "core", "update-index"],
        [
            cli,
            "core",
            "install",
            "arduino:renesas_uno@" + args.core_version,
        ],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=240,
        )
        print(result.stdout, result.stderr, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
