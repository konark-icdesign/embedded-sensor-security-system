"""Write a compiled UNO R4 firmware artifact manifest."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.arduino_toolchain import (
    ARDUINO_CLI_VERSION,
    ARDUINO_CORE_VERSION,
    UNO_R4_WIFI_FQBN,
)
from src.firmware_build_manifest import build_manifest, write_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument(
        "--identity",
        default="firmware/night_security/firmware_build_identity.json",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--cli-version", default=ARDUINO_CLI_VERSION)
    parser.add_argument(
        "--cli-asset",
        choices=("linux64", "windows64"),
        help="override automatic host-platform detection",
    )
    parser.add_argument("--core-version", default=ARDUINO_CORE_VERSION)
    parser.add_argument("--fqbn", default=UNO_R4_WIFI_FQBN)
    args = parser.parse_args()

    try:
        manifest = build_manifest(
            args.artifact_dir,
            args.identity,
            cli_version=args.cli_version,
            core_version=args.core_version,
            fqbn=args.fqbn,
            cli_asset_id=args.cli_asset,
        )
    except ValueError as exc:
        parser.error(str(exc))

    write_manifest(args.output, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
