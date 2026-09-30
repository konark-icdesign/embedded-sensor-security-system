"""Run live UNO R4 USB acquisition on the HP-side host."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.board_live import BoardLiveRunner, format_health


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="auto",
                        help="COM port/device path, or 'auto' for conservative discovery")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=0.25)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    parser.add_argument("--status-seconds", type=float, default=2.0)
    parser.add_argument("--raw-log", default="results/live/board_raw.jsonl")
    parser.add_argument("--parsed-log", default="results/live/board_samples.jsonl")
    args = parser.parse_args()

    runner = BoardLiveRunner(
        port=args.port,
        baudrate=args.baud,
        timeout=args.timeout,
        reconnect_delay=args.reconnect_delay,
        status_interval=args.status_seconds,
        raw_log=args.raw_log,
        parsed_log=args.parsed_log,
        status_callback=lambda status: print(format_health(status), flush=True),
    )
    try:
        runner.run()
    except KeyboardInterrupt:
        print("Stopped by user.", flush=True)


if __name__ == "__main__":
    main()
