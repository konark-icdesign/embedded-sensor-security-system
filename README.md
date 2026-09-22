# Room security prototype

I started thinking about this project around 2022 and returned to it in September 2026. The idea is to monitor a room using sound, a camera and motion sensors, then check whether their readings point to the same event.

The target board is the Made-in-India Arduino UNO Ek R4 WiFi. Rev-D now freezes the first buildable sensing set as Panasonic EKMC1601111 PIR, Hi-Link HLK-LD2412 radar and an HC-SR04-33 electrical-type ultrasonic module, alongside the microphone/camera path. The results recorded here still come from simulation and software tests until the breadboard/perfboard stage is measured.

## How it works

An unusual sound puts the system into YELLOW and opens an investigation. It checks camera and sensor activity within a four-second window. Sound alone cannot cause RED. Sound with PIR and radar can, although that combination can also produce false alarms.

The recorder keeps five seconds before the trigger and eight seconds after it. Each incident has its own timestamps and evidence files.

Python runs the simulation, camera processing, recording and delivery. A C implementation handles audio features, anomaly scoring and corroboration. Arduino C++ handles sensor filtering and a local fallback alarm if the PC stops responding. MATLAB provides a separate numerical check.

The camera tests currently use generated grayscale images. Infrared detection and person recognition have not been validated.

## Where it stands

The Python tests, C/C++ checks and MATLAB reference have run on GitHub. The UNO R4 WiFi firmware compiles. Continuous sessions test successive incidents, a network outage, a host restart, PC failure and thunder without movement. Alerts go to a local HTTP test receiver for now.

The earlier simulation covered 52 scenarios with ten noise seeds each:

| Outcome | Trials |
|---|---:|
| Intrusions detected | 160/190 |
| Intrusions missed | 30/190 |
| False alerts on non-intrusions | 20/330 |

A later audio experiment changed the quiet-room calibration. On a separate synthetic set, soft-step detections improved from 0/20 to 20/20. Very soft steps were still mostly missed: only 1/20 was detected. There were no flags in the 60 tested quiet, gain-change and fan-change clips.

Real recordings remain a problem. The earlier broad background model missed all three public footstep clips. Both quiet-trained models flagged all 30 public clips, including the normal background examples. Better synthetic results have not solved that.

The [original results](docs/experiment_report.md), [audio comparison](docs/detection_quality.md) and [validation record](docs/validation.md) contain the details. These measurements do not establish accuracy in a real room.

A new [remaining-system resilience simulation](docs/system_resilience_simulation.md) adds 12,000 deterministic synthetic trials for benign multi-sensor activity, sensor dropout/degradation, intrusion during a network/host outage, and buffered event delivery. In that model, 99.09% of intrusion trials reached RED and 99.11% of outage-intrusion trials were detected locally. No benign or sensor-fault trial reached RED. These numbers are not field accuracy: the synthetic benign and intrusion distributions are still intentionally cleaner than a real room, so the next stress test should force much heavier overlap and noise.

A later [hardware-resilience audit](docs/hardware_resilience_audit.md) executed the actual embedded `Core` logic with timing gaps, ultrasonic dropouts and host-health failures. It found and fixed stale range-buffer reuse after sample gaps, over-sensitive ultrasonic history clearing, a heartbeat design that could hide a dead host pipeline, invisible serial sample loss, overly strict audio timestamp continuity, and stale camera-frame comparison after outages. These remain host-executed tests, not electrical or physical validation.

The first [datasheet-based electrical hardware simulation](docs/electrical_hardware_simulation.md) now covers the proposed PIR/radar logic conditioning, HC-SR04 trigger/echo interface, AO3400A alarm switch and ultrasonic temperature error. It rejects direct 3.3 V sensor outputs into the 5 V RA4M1 as not guaranteed and replaces them with a SN74AHCT14 Schmitt interface. This is a deterministic lumped-element electrical model; final vendor-SPICE and bench measurements are still pending.

A second [Rev-B microphone front-end simulation](docs/microphone_frontend_revb.md) now defines a breadboard-oriented analog audio path around a CMA-4544PF-W electret capsule and MCP6022 dual op amp. ngspice measured 24.81 dB gain at 1 kHz, useful roll-off at 60 Hz/8 kHz/16 kHz, 1.965 Vpp output for a 110 dB SPL equivalent input, and exposed a slow 47k/47k virtual-ground candidate that was replaced by 10k/10k. These are circuit-model results, not physical microphone measurements.

A third [Rev-C power-distribution simulation](docs/power_distribution_revc.md) now links the UNO VIN supply, a provisional TPS54202 5 V sensor rail, the analog microphone rail and the alarm branch. Under the stated stress envelope, the star-ground model kept VIN at or above 11.695 V, the 5 V sensor rail at or above 4.940 V and the analog rail at or above 4.907 V. A deliberately shared alarm/microphone return created about 50.39 mV of ground movement, so that wiring topology is rejected. The regulator itself is still a datasheet-based closed-loop abstraction rather than a full vendor switching model.

A fourth [Rev-D buildable hardware pass](docs/revd_buildable_hardware.md) freezes exact prototype sensors and updates the PIR/radar input network for those datasheets. It selects EKMC1601111 rather than the earlier ultra-low-power PIR candidate because the security node does not need microamp battery operation and the EKMC has a much shorter specified startup-stability window. Rev-D also fixes an unnecessary DC divider in the generic sensor input by moving the 100 kOhm idle pulldown ahead of the 10 kOhm RC series resistor. In the exact-part ngspice run, the worst-case EKMC channel reached 4.4697 V before conditioning and 4.4 V at the modeled AHCT output while drawing 48.03 uA; the LD2412 channel reached 3.2778 V before conditioning and 4.4 V after it. All Rev-D electrical checks passed. The [Rev-D BOM](docs/bom_revd.md) separates breadboard-friendly circuits from blocks that need a daughterboard/PCB.

## Running it

Use Python 3.12. From the project folder on Windows:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts/fetch_real_audio.py
python run_simulation.py --seeds 1
python scripts/system_resilience_sim.py
python -m unittest discover -s tests -p "test_*.py" -v
make hardware-stress
make electrical-sim
```

On Linux or macOS, activate with `source .venv/bin/activate`. Use `--seeds 10` for the longer scenario run. The audio download needs internet access.

For the continuous simulation with the C backend, use Linux with GCC and Make:

```text
make incident-build
python run_incidents.py --c-library build/libdetection.so
```

The continuous runner uses the newer room profile by default. Add `--audio-profile legacy` to compare the previous calibration. Choose a fresh output directory with `--output` when rerunning; existing incident evidence is preserved.

More commands are in [reproduction](docs/reproduction.md) and [the incident workflow](docs/incidents.md).

## What is left

The next stage is circuit and firmware verification; physical assembly comes after that. The [electronics plan](docs/electronics_plan.md) records the Ek R4 pin allocation, component choices still open, and simulator limitations. A complete online R4 circuit simulation has not run: neither Wokwi nor Renesas's published online-simulator list includes the RA4M1.

The live USB acquisition service, microphone and camera integration, and acquisition-time checks remain unfinished. Later, room recordings will be needed to calibrate and evaluate the detector using separate recording sessions.

Very quiet footsteps, warm moving objects and activity outside the room still need work. A real notification endpoint also needs to be connected and tested.

Results should distinguish simulation, individual component tests, combined hardware tests and tests in the intended room.

## Notes and records

The [debugging history](docs/debugging_history.md) records the problems found, fixes and remaining failures. Important original run outputs are committed in [the evidence archive](evidence/github/), including checksums and source run IDs.

- [System design](docs/architecture.md)
- [DSP calculations](docs/dsp_maths.md)
- [Hardware and wiring](docs/hardware.md)
- [Hardware resilience audit](docs/hardware_resilience_audit.md)
- [Electrical hardware simulation](docs/electrical_hardware_simulation.md)
- [Rev-B microphone front end](docs/microphone_frontend_revb.md)
- [Rev-C power distribution](docs/power_distribution_revc.md)
- [Rev-D buildable hardware](docs/revd_buildable_hardware.md)
- [Rev-D prototype BOM](docs/bom_revd.md)
- [HP t640 setup](docs/hp_setup.md)
- [Learning and validation tasks](docs/learning_and_validation.md)

I used AI assistance for implementation, debugging and documentation. The linked logs record the tests that were actually run.

Public audio comes from [ESC-50](https://github.com/karolpiczak/ESC-50); its licence and recording attributions are kept in `fixtures/esc50/LICENSE`. No project-wide licence has been selected for the original code.
