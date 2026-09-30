"""Deterministic Rev-I host-device runtime simulation."""
import argparse, json, queue, sys, tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.board_serial import BoardSerialAdapter
from src.dsp import Baseline
from src.live_devices import AudioChunk, CameraFrameBuffer, LiveHostRuntime
from src.live_pipeline import CombinedAcquisitionCoordinator

def wire(seq,ms,p=0,m=0,u=0):
    return f"S,{seq},{ms},{p},{m},{u},1.2,1,0,1,0,0,0"

class FakeBoard:
    def __init__(self,s): self.s=s; self.sample_callback=None
    def run(self,stop_event=None):
        self.sample_callback(self.s)
        if stop_event is not None: stop_event.wait(.25)
        return {}
class FakeMic:
    def __init__(self,chunks):
        self.q=queue.Queue()
        for c in chunks: self.q.put(c)
    def start(self): pass
    def read(self,timeout=1): return self.q.get(timeout=timeout)
    def stop(self): pass
    def stats(self): return {"queue_drops":0,"callback_faults":0,"queued_chunks":self.q.qsize()}
class FakeCam:
    def __init__(self,b): self.buffer=b
    def start(self): pass
    def stop(self): pass
    def stats(self): return {"frames":2,"failures":0}

def run():
    a=BoardSerialAdapter()
    b=a.ingest(wire(5,1000,p=1,m=1),50.010)
    wave=.01*np.sin(2*np.pi*440*np.arange(1600)/16000.0)
    chunks=[AudioChunk(wave,b.captured+.05,b.captured+.055),
            AudioChunk(wave,b.captured+.10,b.captured+.105),
            AudioChunk(wave,b.captured+.145,b.captured+.150,True,"simulated_input_overflow")]
    cb=CameraFrameBuffer()
    cb.push(np.full((120,160),70,dtype=np.uint8),b.captured+.04)
    cb.push(np.full((120,160),75,dtype=np.uint8),b.captured+.09)
    with tempfile.TemporaryDirectory() as td:
        c=CombinedAcquisitionCoordinator(td,Baseline(np.zeros(9),np.ones(9),999.0))
        stats=LiveHostRuntime(c,FakeBoard(b),FakeMic(chunks),FakeCam(cb)).run(max_chunks=3)
    checks={
      "all_audio_chunks_forwarded":stats["coordinator"]["media_forwarded"]==3,
      "camera_frame_matched":stats["camera_matches"]==3,
      "no_camera_miss":stats["camera_misses"]==0,
      "audio_fault_propagated":stats["media_faults"]==1 and stats["coordinator"]["media_fault_packets"]==1,
      "board_state_synchronized":stats["coordinator"]["board_sync"]["session"]==b.session}
    return {"scope":"deterministic Rev-I fake devices only; no physical HP t640, webcam, microphone or UNO R4 measurements",
            "checks":checks,"passed":all(checks.values()),"runtime":stats}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",default="results/live_host_runtime_simulation.json"); args=p.parse_args()
    r=run(); t=Path(args.output); t.parent.mkdir(parents=True,exist_ok=True); t.write_text(json.dumps(r,indent=2)); print(json.dumps(r,indent=2))
    if not r["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
