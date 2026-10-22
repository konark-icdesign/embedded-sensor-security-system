"""Pinned Arduino toolchain metadata used for UNO R4 builds."""

import hashlib
from pathlib import Path
import platform

ARDUINO_CLI_VERSION = "1.5.1"
ARDUINO_CLI_LINUX64_SHA256 = (
    "28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b"
)
ARDUINO_CLI_WINDOWS64_SHA256 = (
    "fabe42e0eb04d00e776a66178299ff95a46c623dbc260f997e58fd514853dd40"
)
ARDUINO_CORE_VERSION = "1.6.0"
UNO_R4_WIFI_FQBN = "arduino:renesas_uno:unor4wifi"


_ASSETS = {
    "linux64": {
        "system": "Linux",
        "machines": {"x86_64", "amd64"},
        "suffix": "Linux_64bit.tar.gz",
        "sha256": ARDUINO_CLI_LINUX64_SHA256,
        "archive_type": "tar",
        "executable": "arduino-cli",
    },
    "windows64": {
        "system": "Windows",
        "machines": {"amd64", "x86_64"},
        "suffix": "Windows_64bit.zip",
        "sha256": ARDUINO_CLI_WINDOWS64_SHA256,
        "archive_type": "zip",
        "executable": "arduino-cli.exe",
    },
}


def detect_cli_asset_id(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    for asset_id, metadata in _ASSETS.items():
        if (
            metadata["system"].lower() == str(system).lower()
            and machine in metadata["machines"]
        ):
            return asset_id
    raise RuntimeError(
        "unsupported Arduino CLI host platform: {} {}".format(
            system,
            machine,
        )
    )


def cli_asset(asset_id=None, version=ARDUINO_CLI_VERSION):
    asset_id = asset_id or detect_cli_asset_id()
    try:
        metadata = _ASSETS[asset_id]
    except KeyError as exc:
        raise RuntimeError(
            "unsupported Arduino CLI asset: {}".format(asset_id)
        ) from exc

    archive_name = "arduino-cli_{}_{}".format(
        version,
        metadata["suffix"],
    )
    return {
        "asset_id": asset_id,
        "archive_name": archive_name,
        "url": (
            "https://github.com/arduino/arduino-cli/releases/download/"
            "v{version}/{archive_name}"
        ).format(
            version=version,
            archive_name=archive_name,
        ),
        "sha256": (
            metadata["sha256"]
            if str(version) == ARDUINO_CLI_VERSION
            else None
        ),
        "archive_type": metadata["archive_type"],
        "executable": metadata["executable"],
        "system": metadata["system"],
    }


def cli_linux64_url(version=ARDUINO_CLI_VERSION):
    return cli_asset("linux64", version)["url"]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path, expected):
    actual = sha256_file(path)
    if actual.lower() != str(expected).lower():
        raise ValueError(
            "SHA-256 mismatch for {}: expected {}, got {}".format(
                path, expected, actual
            )
        )
    return actual
