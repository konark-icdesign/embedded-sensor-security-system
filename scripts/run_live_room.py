"""Run the Rev-I live host stack."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.board_live import BoardLiveRunner, format_health
from src.live_devices import LiveHostRuntime, OpenCVCamera, SoundDeviceMicrophone
from src.live_pipeline import CombinedAcquisitionCoordinator
from src.room_audio import quiet_model

def dev(v):
    try: return int(v)
    except ValueError: return v

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--port",default="auto")
    p.add_argument("--audio-device",type=dev,default=None)
    p.add_argument("--camera-index",type=int,default=0)
    p.add_argument("--no-camera",action="store_true")
    p.add_argument("--seconds",type=float,default=None)
    p.add_argument("--output",default=None)
    a=p.parse_args()
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out=Path(a.output) if a.output else Path("results")/"live-room"/stamp
    if out.exists() and any(out.iterdir()): p.error("output directory must be empty")
    out.mkdir(parents=True,exist_ok=True)
    print("WARNING: synthetic quiet-room baseline; acquisition test only, not validated security accuracy.",flush=True)
    c=CombinedAcquisitionCoordinator(out/"sessions",quiet_model())
    b=BoardLiveRunner(port=a.port,raw_log=out/"transport"/"board_raw.jsonl",
      parsed_log=out/"transport"/"board_samples.jsonl",
      status_callback=lambda s: print(format_health(s),flush=True))
    mic=SoundDeviceMicrophone(device=a.audio_device)
    cam=None if a.no_camera else OpenCVCamera(index=a.camera_index)
    rt=LiveHostRuntime(c,b,mic,cam)
    try:
        print("FINAL",rt.run(max_seconds=a.seconds),flush=True)
    except KeyboardInterrupt:
        print("Stopped by user.",flush=True)
if __name__=="__main__": main()
