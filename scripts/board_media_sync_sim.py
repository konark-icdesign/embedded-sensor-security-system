"""Deterministic Rev-G board/media timestamp synchronization experiment."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.board_serial import BoardSerialAdapter
from src.board_sync import BoardMediaSynchronizer


def wire(seq, ms, p=0, m=0, u=0, valid=1, degraded=0, fallback=0):
    value = "1.200" if valid else "nan"
    return f"S,{seq},{ms},{p},{m},{u},{value},{valid},0,1,{degraded},{fallback},0"


def run():
    adapter = BoardSerialAdapter()
    sync = BoardMediaSynchronizer(max_age=.15)

    b0 = adapter.ingest(wire(0, 60000, p=1), 100.010)
    b1 = adapter.ingest(wire(1, 60100, m=1), 100.114)
    sync.ingest(b0)
    sync.ingest(b1)

    before = sync.match(b0.captured - .001)
    near0 = sync.match(b0.captured + .050)
    near1 = sync.match(b1.captured + .040)
    stale = sync.match(b1.captured + .151)

    reboot = adapter.ingest(wire(0, 120, u=1, fallback=1), 100.500)
    sync.ingest(reboot)
    after = sync.match(reboot.captured + .025)

    checks = {
        "future_board_sample_not_used": not before.matched and before.reason == "no_board_sample",
        "first_media_frame_gets_first_board_state": near0.matched and near0.physical["P"] and not near0.physical["M"],
        "later_media_frame_gets_newer_board_state": near1.matched and near1.physical["M"],
        "stale_board_state_becomes_fault": (
            not stale.matched and stale.reason == "stale_board_sample"
            and stale.physical == {"P": False, "M": False, "U": False, "fault": True}
        ),
        "reboot_flushes_old_session": sync.stats()["session_changes"] == 1 and sync.stats()["buffered_samples"] == 1,
        "post_reboot_state_is_new_session": after.matched and after.physical["U"] and after.fallback,
    }
    return {
        "scope": "deterministic Rev-G timestamp synchronization; no physical audio, camera, USB or sensor measurements",
        "max_age_seconds": sync.max_age,
        "checks": checks,
        "passed": all(checks.values()),
        "sync_stats": sync.stats(),
        "matches": {
            "before": before.as_dict(),
            "near0": near0.as_dict(),
            "near1": near1.as_dict(),
            "stale": stale.as_dict(),
            "after_reboot": after.as_dict(),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/board_media_sync_simulation.json")
    args = parser.parse_args()
    result = run()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
