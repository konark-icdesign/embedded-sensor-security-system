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


def _bench_commands(build_dir):
    build_arg = '"{}"'.format(Path(build_dir))
    common = '--port auto --prepared-build-dir {}'.format(build_arg)
    return {
        "steady": (
            "python scripts/run_board_bench.py {} --seconds 60 "
            "--label usb-idle"
        ).format(common),
        "reconnect": (
            "python scripts/run_board_bench.py {} --seconds 90 "
            "--label usb-reconnect"
        ).format(common),
        "range_example": (
            "python scripts/run_board_bench.py {} --seconds 30 "
            "--label range-static-1m --reference-distance-m 1.0 "
            '--setup-note "flat target, tape measured"'
        ).format(common),
    }


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

    result = dict(result)
    result["bench_commands"] = _bench_commands(result["build_dir"])

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

    commands = result["bench_commands"]
    print("NEXT_STEADY {}".format(commands["steady"]))
    print("NEXT_RECONNECT {}".format(commands["reconnect"]))
    print("NEXT_RANGE_EXAMPLE {}".format(commands["range_example"]))


if __name__ == "__main__":
    main()
