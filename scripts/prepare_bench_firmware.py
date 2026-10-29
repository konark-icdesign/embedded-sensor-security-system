"""Build and optionally flash one provenance-bound bench firmware image."""

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
from src.bench_firmware_prepare import prepare_bench_firmware


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--cli-path")
    parser.add_argument(
        "--cli-asset",
        choices=("linux64", "windows64"),
        help="override automatic host-platform detection",
    )
    parser.add_argument("--cli-version", default=ARDUINO_CLI_VERSION)
    parser.add_argument("--core-version", default=ARDUINO_CORE_VERSION)
    parser.add_argument("--fqbn", default=UNO_R4_WIFI_FQBN)
    parser.add_argument("--revision")
    parser.add_argument(
        "--upload-port",
        help="flash the verified prebuilt image to this port; use 'auto' "
        "for unambiguous Arduino discovery",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = prepare_bench_firmware(
            repo_root=ROOT,
            build_dir=args.build_dir,
            manifest_path=args.manifest,
            cli_asset_id=args.cli_asset,
            cli_path=args.cli_path,
            cli_version=args.cli_version,
            core_version=args.core_version,
            fqbn=args.fqbn,
            revision=args.revision,
            upload_port=args.upload_port,
        )
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(
        "FIRMWARE PREPARED build_id={build_id} asset={cli_asset} "
        "cli={cli_version} core={core_version} artifacts={artifact_count} "
        "uploaded={uploaded}".format(**result)
    )
    print("BUILD_DIR {}".format(result["build_dir"]))
    print("MANIFEST {}".format(result["manifest_path"]))
    if result["uploaded"]:
        print("UPLOAD_PORT {}".format(result["upload_port"]))

    port = result["upload_port"] if result["uploaded"] else "auto"
    print(
        "NEXT python scripts/run_board_bench.py --port {} --seconds 60 "
        "--label usb-idle --firmware-build-manifest "{}" "
        "--firmware-artifact-dir "{}"".format(
            port,
            result["manifest_path"],
            result["build_dir"],
        )
    )


if __name__ == "__main__":
    main()
