"""Install a pinned Arduino CLI and UNO R4 board core for CI/bench builds."""

import argparse
import pathlib
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.arduino_toolchain import (
    ARDUINO_CLI_VERSION,
    ARDUINO_CORE_VERSION,
    cli_asset,
    verify_sha256,
)


def _extract_cli(archive, root, asset):
    executable = asset["executable"]
    if asset["archive_type"] == "tar":
        with tarfile.open(archive) as handle:
            member = next(
                (
                    item
                    for item in handle.getmembers()
                    if pathlib.PurePosixPath(item.name).name == executable
                ),
                None,
            )
            if member is None:
                raise RuntimeError(
                    "{} not found in {}".format(executable, archive)
                )
            member.name = executable
            handle.extract(member, root, filter="data")
    elif asset["archive_type"] == "zip":
        with zipfile.ZipFile(archive) as handle:
            member = next(
                (
                    name
                    for name in handle.namelist()
                    if pathlib.PurePosixPath(name).name == executable
                ),
                None,
            )
            if member is None:
                raise RuntimeError(
                    "{} not found in {}".format(executable, archive)
                )
            target = root / executable
            with handle.open(member) as source:
                target.write_bytes(source.read())
    else:
        raise RuntimeError(
            "unsupported archive type: {}".format(
                asset["archive_type"]
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-version", default=ARDUINO_CORE_VERSION)
    parser.add_argument("--cli-version", default=ARDUINO_CLI_VERSION)
    parser.add_argument("--cli-sha256")
    parser.add_argument(
        "--cli-asset",
        choices=("linux64", "windows64"),
        help="override automatic host-platform detection",
    )
    args = parser.parse_args()

    try:
        asset = cli_asset(args.cli_asset, args.cli_version)
    except RuntimeError as exc:
        parser.error(str(exc))

    expected_sha256 = args.cli_sha256 or asset["sha256"]
    if expected_sha256 is None:
        parser.error(
            "--cli-sha256 is required for an unrecognized CLI version"
        )

    root = pathlib.Path(__file__).resolve().parents[2] / "arduino-tools"
    root.mkdir(exist_ok=True)
    archive = root / asset["archive_name"]

    with urllib.request.urlopen(asset["url"], timeout=45) as response:
        archive.write_bytes(response.read())

    verify_sha256(archive, expected_sha256)
    _extract_cli(archive, root, asset)

    cli = str(root / asset["executable"])
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

    print(
        "ARDUINO_BOOTSTRAP asset={} cli={} core={}".format(
            asset["asset_id"],
            args.cli_version,
            args.core_version,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
