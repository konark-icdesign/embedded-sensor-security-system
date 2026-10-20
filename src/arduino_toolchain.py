"""Pinned Arduino toolchain metadata used for UNO R4 builds."""

import hashlib
from pathlib import Path

ARDUINO_CLI_VERSION = "1.5.1"
ARDUINO_CLI_LINUX64_SHA256 = (
    "28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b"
)
ARDUINO_CORE_VERSION = "1.6.0"
UNO_R4_WIFI_FQBN = "arduino:renesas_uno:unor4wifi"


def cli_linux64_url(version=ARDUINO_CLI_VERSION):
    return (
        "https://github.com/arduino/arduino-cli/releases/download/"
        "v{version}/arduino-cli_{version}_Linux_64bit.tar.gz"
    ).format(version=version)


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
