# HP t640 setup

The intended PC is an HP t640 with 8 GB RAM, an NVMe SSD and Windows 10 22H2. No workload measurements have been taken on it yet.

## Software

| Software | Purpose |
|---|---|
| Python 3.12, NumPy, SciPy and Matplotlib | Run the current simulation and plots |
| sounddevice + PortAudio | Optional Rev-I live microphone capture |
| OpenCV | Optional Rev-I webcam capture |
| Arduino IDE 2 | Compile and later upload the board sketch |
| Arduino UNO R4 Boards core 1.6.0 | Reproduce the recorded target build |
| MATLAB, with a suitable licence | Reproduce the reference already verified on GitHub; HP performance is unmeasured |
| GCC and Make | Run the native C++ checks; optional for the first Python run |
| FFmpeg | Optional synthetic MP4 export |

Start with Python and the README commands. Use one seed before trying ten. The project does not currently need Simulink, a neural-network stack or an MQTT broker.

MathWorks' R2026a requirements list 8 GB RAM minimum, 16 GB recommended and support for Windows 10 22H2. That establishes software eligibility, not measured performance on this PC. Installation size depends on selected products. [Official requirements](https://www.mathworks.com/support/requirements/matlab-system-requirements.html).

## Windows steps

1. Put the repository in a folder such as `C:\ECE\night-security`.
2. Create the virtual environment and install the README dependencies. For live microphone/webcam capture install `requirements-live.txt` instead of only `requirements.txt`. If necessary, use `py -3.12` instead of `python` when creating it.
3. Download the audio subset, run one seed and inspect `results/scenario_results.csv`.
4. For MATLAB, generate the fixtures with Python first, then run `addpath('matlab'); run_full_simulation`.
5. In Arduino IDE, install Arduino UNO R4 Boards, select UNO R4 WiFi and compile the sketch. Wiring and upload checks are in `hardware.md`.

Close Serial Monitor before another program opens the same COM port.

## Initial live-processing targets

These are proposed settings for a later hardware test:

| Input | Setting |
|---|---|
| Audio | 16 kHz mono, 2048-sample frame, 1024-sample hop |
| Camera | Resize to 320x240 grayscale and process at 5 frames/s |
| Sensor telemetry | 10 samples/s over USB serial at 115200 baud |
| Recording | Bounded pre/post-event buffers |

Ten seconds of raw grayscale frames at those settings takes 3.84 MB; the same duration of 16-bit mono audio takes 0.32 MB. Program memory and decoding buffers are additional.

The simulation uses 160x120 generated frames. Its execution time does not measure webcam decoding or performance on the HP. Measure dropped frames, memory use and processing delay when live acquisition is added.


## Rev-I live acquisition command

After connecting the UNO and host devices:

    python scripts/run_live_room.py --port auto --camera-index 0 --seconds 60

Use --audio-device to choose a non-default microphone. Use --no-camera to test serial + microphone first. Each invocation creates a new timestamped evidence directory. The current quiet-room model is synthetic and is not calibrated to the HP microphone or intended room.
