"""Stamp the UNO R4 firmware source with a queryable build identity."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.firmware_identity import write_identity_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--firmware-dir",
        default="firmware/night_security",
    )
    parser.add_argument("--revision")
    args = parser.parse_args()

    identity = write_identity_files(
        args.firmware_dir,
        repo_root=ROOT,
        revision=args.revision,
    )
    print(json.dumps(identity, indent=2))


if __name__ == "__main__":
    main()
