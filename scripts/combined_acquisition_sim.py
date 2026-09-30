"""Deterministic Rev-H combined board/audio/camera coordinator simulation."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.board_serial import BoardSerialAdapter
from src.dsp import Baseline
from src.live_pipeline import CombinedAcquisitionCoordinator


def wire(seq, ms, p=0, m=0, u=0, valid=1, degraded=0, fallback=0):
    value = "1.200" if valid else "nan"
    return (
        f"S,{seq},{ms},{p},{m},{u},{value},{valid},0,1,{degraded},"
        f"{fallback},0"
    )


def read_history(directory):
    with sqlite3.connect(Path(directory) / "journal.sqlite") as db:
        return [
            json.loads(row[0])
            for row in db.execute("SELECT payload FROM history ORDER BY stamp")
        ]


def run():
    adapter = BoardSerialAdapter()
    model = Baseline(np.zeros(9), np.ones(9), threshold=999.0)
    t = np.arange(1600) / 16000.0
    audio = 0.01 * np.sin(2 * np.pi * 440 * t)

    with tempfile.TemporaryDirectory() as td:
        c = CombinedAcquisitionCoordinator(td, model)

        waiting = c.push_media(audio, None, 99.900, 99.905)

        b0 = adapter.ingest(wire(100, 60000, p=1), 100.010)
        c.on_board_sample(b0)
        first = c.push_media(audio, None, b0.captured + .050, b0.captured + .055)
        second = c.push_media(audio, None, b0.captured + .080, b0.captured + .085)
        stale = c.push_media(audio, None, b0.captured + .200, b0.captured + .205)

        reboot = adapter.ingest(wire(0, 120, m=1, u=1, fallback=1), 100.400)
        c.on_board_sample(reboot)
        after = c.push_media(audio, None, reboot.captured + .050, reboot.captured + .055)

        stats = c.stats()
        directories = dict(stats["session_directories"])
        c.close()

        old_history = read_history(directories[b0.session])
        new_history = read_history(directories[reboot.session])

    checks = {
        "media_before_board_is_not_invented": (
            not waiting["accepted"] and waiting["reason"] == "waiting_for_board"
        ),
        "one_board_sample_can_feed_multiple_media_packets": (
            first["media_seq"] == 1 and second["media_seq"] == 2
        ),
        "fresh_physical_flags_reach_roomstream": (
            old_history[0]["flags"]["P"] is True
            and old_history[0]["flags"]["M"] is False
        ),
        "stale_physical_state_is_cleared_to_health_fault": (
            stale["board_match"]["reason"] == "stale_board_sample"
            and old_history[-1]["flags"]["P"] is False
            and old_history[-1]["flags"]["M"] is False
            and old_history[-1]["flags"]["U"] is False
            and old_history[-1]["health"] is True
        ),
        "reboot_rotates_incident_journal": (
            stats["stream_rotations"] == 1
            and b0.session != reboot.session
            and len(directories) == 2
        ),
        "new_session_resets_media_sequence": after["media_seq"] == 1,
        "post_reboot_state_is_isolated": (
            len(new_history) == 1
            and new_history[0]["session"] == reboot.session
            and new_history[0]["flags"]["M"] is True
            and new_history[0]["flags"]["U"] is True
            and new_history[0]["fallback"] is True
        ),
    }
    return {
        "scope": (
            "deterministic Rev-H combined acquisition coordination using synthetic "
            "audio and simulated board packets; no physical microphone, camera, "
            "UNO R4, USB or HP t640 measurements"
        ),
        "checks": checks,
        "passed": all(checks.values()),
        "coordinator_stats": stats,
        "old_session_history_packets": len(old_history),
        "new_session_history_packets": len(new_history),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/combined_acquisition_simulation.json")
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
