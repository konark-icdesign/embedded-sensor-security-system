"""Summarize multiple verified ultrasonic static-distance captures."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_board_bench import verify_capture
from src.range_characterization import (
    build_characterization,
    characterize_capture,
    characterization_csv,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "captures",
        nargs="+",
        help="two or more bench capture directories",
    )
    parser.add_argument("--output-json")
    parser.add_argument("--output-csv")
    args = parser.parse_args()

    if len(args.captures) < 2:
        parser.error("provide at least two capture directories")

    trials = []
    try:
        for capture in args.captures:
            integrity = verify_capture(capture)
            trials.append(characterize_capture(capture, integrity))
    except ValueError as exc:
        parser.error(str(exc))

    result = build_characterization(trials)
    rendered = json.dumps(result, indent=2)
    print(rendered)

    if args.output_json:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")

    if args.output_csv:
        target = Path(args.output_csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            characterization_csv(result),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
