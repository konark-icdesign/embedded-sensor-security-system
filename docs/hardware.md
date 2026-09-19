# Wiring plan and bench checks

The selected board is the Made-in-India UNO Ek R4 WiFi. See the [electronics plan](electronics_plan.md) for the development order and online simulator check. Physical assembly follows circuit and firmware verification.

These connections are planned for the UNO R4 WiFi sketch. Check the exact sensor modules and their electrical specifications before wiring. No physical test has been recorded. The host-executed controller stress work and bugs found are recorded in [hardware resilience audit](hardware_resilience_audit.md).

The official UNO R4 WiFi uses a 5 V RA4M1 host MCU, with a separate 3.3 V ESP32-S3 radio. The compiled firmware runs on the RA4M1. The simulation does not put camera or audio processing into its 32 KB SRAM. The first datasheet-based electrical interface simulation is documented in [Rev-A electrical hardware simulation](electrical_hardware_simulation.md). Source: https://docs.arduino.cc/hardware/uno-r4-wifi .

| Connection | Sketch pin | Note |
|---|---:|---|
| PIR output | D2 | Rev-A electrical design: 0/3.3 V sensor OUT -> 10 kOhm series, 100 kOhm pulldown, 10 nF shunt -> two SN74AHCT14 gates -> D2. Do not connect a 3.3 V HIGH directly and call it guaranteed. |
| LD2410B/C-class presence OUT | D3 | Same SN74AHCT14 double-inverter conditioner as D2. Exact purchased radar module still has to match the 0/3.3 V OUT assumption. |
| Ultrasonic trigger | D4 | HC-SR04-like TRIG through 220 Ohm series resistor; firmware pulse is 10 us. |
| Ultrasonic echo | D5 | HC-SR04 Echo -> 1 kOhm series -> D5, with 100 kOhm pulldown and 100 pF shunt at the MCU side. UNO R4 main GPIO is a 5 V domain. |
| Green LED | D6 | Series current-limiting resistor |
| Yellow LED | D7 | Series current-limiting resistor |
| Red LED | D8 | Series current-limiting resistor |
| Alarm control | D9 | Rev-A: D9 -> 1.5 kOhm -> AO3400A gate, 100 kOhm gate pulldown. Low-side switch external alarm load; add fuse and SS34 flyback diode for inductive loads. Do not power the alarm from D9. |
| Local reset button | D10 to GND | INPUT_PULLUP; clears local alarm latch |
| PC connection | USB-C | Serial data at 115200 baud |
| Shared reference | GND | All low-voltage sensor grounds need a common reference |

Pinout and supply requirements vary across LD2410, LD2410B, LD2410C and clones. The chosen firmware reads only OUT, not UART. It therefore cannot verify radar frame freshness, configure distance gates, or reliably distinguish a wire stuck low from no presence. Use the exact module manual before wiring: https://www.hlktech.net/ .

## Rev-B microphone front end

The first buildable microphone circuit is now frozen for prototype work and is documented in [Rev-B microphone analog front end](microphone_frontend_revb.md).

Selected prototype parts:

- Same Sky/CUI CMA-4544PF-W electret microphone;
- Microchip MCP6022-I/P dual op amp in PDIP-8;
- 2.2 kOhm microphone bias from 3.3 V;
- 10k/10k + 10 uF 2.5 V midpoint, buffered by one MCP6022 channel;
- 100 nF input coupling and 22 kOhm bias to midpoint;
- 49.9 kOhm / 2.49 kOhm non-inverting gain network;
- 3.3 kOhm / 5.6 nF output low-pass;
- optional 4.7 uF AC-coupled line output.

The selected midpoint network reached 99% in 231.3 ms in ngspice. A 47k/47k candidate took 1083.2 ms and was rejected.

The simulated end-to-end gain is 24.81 dB at 1 kHz. A 110 dB SPL equivalent input remained between 1.518 V and 3.482 V on the 5 V biased output in the current model.

This does **not** mean the physical microphone chain has been validated. The exact ADC/audio-interface stage is still open and the breadboard response/noise/clipping must be measured.

## Power arrangement

For first bench work, USB power is acceptable if we explicitly accept that fallback ends when USB power disappears. For the actual PC-failure demonstration, the Arduino must remain powered independently of the HP. A practical Rev-A arrangement is a supported external low-voltage supply into VIN/barrel while USB is used for data, following the board power guidance. The high-current alarm load must return directly to the supply/star ground rather than through the sensor/microphone ground path. Do not connect arbitrary external 5 V and USB supplies together.

## What the sketch actually does

- It does not block waiting for a PC serial terminal.
- It polls at a nominal 100 ms cadence.
- Echo timeout is bounded at 30 ms after the electrical timing review. A missing echo is invalid, not a valid zero-metre object.
- PIR and radar need three consecutive active samples.
- Range uses a five-sample median plus three consecutive near results.
- The first 60 seconds inhibit alarms while sensors settle.
- `HB` now records transport activity only and does not suppress local fallback. `HEALTH` must come from a host pipeline that has checked fresh acquisition/fusion progress; `UNHEALTHY` explicitly drops host health. `ALARM` latches the local buzzer. `YELLOW` and `GREEN` set the host investigation indication without clearing an alarm. Commands are newline-terminated and length-bounded.
- Missing `HEALTH` for more than two seconds enables physical fallback even if transport-only `HB` messages continue.
- One or two invalid ultrasonic samples do not erase an already-established near state; three consecutive invalid samples clear the range persistence. Every invalid reading is still reported as a range fault.
- A sample gap above 250 ms clears accumulated persistence and the range-buffer cursor.
- The official Renesas watchdog is enabled for four seconds and refreshed by the loop.
- Local button reset clears the alarm; it is not an authenticated access-control system.

Output line:

```text
S,sequence,board_millis,pir_filtered,radar_filtered,near_filtered,range_metres,range_valid,alarm,armed,degraded,fallback_alarm,serial_drops
```

`range_metres` may be `nan`. The PC must honor `range_valid`. The sample sequence advances even when a serial write is skipped, so the host must treat sequence gaps and the cumulative `serial_drops` field as evidence of missing board samples. Opening a port can reset some boards; after reconnection, flush old bytes, establish a new session and remap the board clock. The supplied serial bench tool only displays these fields and sends `HEALTH` for bench operation. It is not the complete continuous acquisition/fusion service.

## Later physical bench sequence

1. Compile and upload with sensors disconnected; confirm boot, status LEDs, serial messages and warm-up.
2. Verify each input separately with a meter/known stimulus. Connect one sensor at a time.
3. Log raw and filtered range while presenting a flat target at measured distances. Record invalid-echo frequency.
4. Measure PIR hold time and retrigger behavior. These depend on the module settings, not just the 0.3-second software persistence.
5. Measure radar responses to empty room, moving fan/curtain, stationary person and activity outside the room.
6. Verify `ALARM` and the local reset button using a low-volume buzzer.
7. Disconnect the PC data link while the board remains powered. Present all three physical stimuli and measure fallback latency.
8. Test board power loss separately. The RAM latch and history do not survive it; the current design cannot claim otherwise.

The latest checked target build after the resilience fixes used 53,996 bytes of flash and 6,920 bytes of global RAM. Stack usage, physical electrical behaviour, processing deadlines and watchdog recovery still need board measurements.

Those byte counts belong to the earlier sketch. The Incident pipeline workflow compiles the revised sketch with core 1.6.0 and reports its current size. The continuous host simulation uses a C++ driver around `core.h`; it does not operate physical pins. The physical serial adapter still needs to carry the fallback-latch provenance now exposed by the core, as well as map board time into the host acquisition clock.
