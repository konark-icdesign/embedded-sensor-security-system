"""Analyze one Rev-F/bench capture without inventing pass thresholds."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bench_analysis import analyze_board_bench_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed", required=True)
    parser.add_argument("--raw", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = analyze_board_bench_files(args.parsed, args.raw)
    rendered = json.dumps(result, indent=2)
    print(rendered)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
