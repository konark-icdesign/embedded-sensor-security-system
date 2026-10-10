"""Run physical bench preflight checks without starting a capture."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bench_preflight import format_preflight, run_preflight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="auto")
    parser.add_argument("--output-root", default="results/bench")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_preflight(
        port=args.port,
        output_root=args.output_root,
        repo_root=ROOT,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_preflight(result))
        for item in result["serial_ports"]:
            print(
                "PORT device={device} description={description} "
                "manufacturer={manufacturer} product={product}".format(**item)
            )
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
