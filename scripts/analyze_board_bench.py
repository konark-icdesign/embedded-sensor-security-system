"""Analyze one Rev-F/bench capture without inventing pass thresholds."""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bench_analysis import analyze_board_bench_files


def _stored_reference_distance(parsed_path):
    metadata_path = Path(parsed_path).parent / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("metadata.json is not valid JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json is not a JSON object")
    value = metadata.get("reference_distance_m")
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            "metadata reference_distance_m must be finite and positive"
        )
    return value


def resolve_reference_distance(parsed_path, explicit=None):
    stored = _stored_reference_distance(parsed_path)
    if explicit is None:
        return stored
    explicit = float(explicit)
    if not math.isfinite(explicit) or explicit <= 0:
        raise ValueError("reference distance must be finite and positive")
    if (
        stored is not None
        and not math.isclose(stored, explicit, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise ValueError(
            "explicit reference distance conflicts with metadata.json"
        )
    return explicit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed", required=True)
    parser.add_argument("--raw", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--reference-distance-m", type=float)
    args = parser.parse_args()

    try:
        reference_distance_m = resolve_reference_distance(
            args.parsed,
            explicit=args.reference_distance_m,
        )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))

    result = analyze_board_bench_files(
        args.parsed,
        args.raw,
        reference_distance_m=reference_distance_m,
    )
    rendered = json.dumps(result, indent=2)
    print(rendered)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
