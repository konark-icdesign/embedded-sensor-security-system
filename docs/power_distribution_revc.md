# Rev-C power distribution and ground-return design

This stage moves the security prototype from separate circuit blocks toward a buildable low-voltage power architecture.

The goal is not to claim a finished PSU. It is to answer, before breadboarding:

1. how the UNO R4, sensors, analog front end and alarm should be powered;
2. whether the provisional 12 V / 5 V load envelope has useful margin;
3. whether the alarm current can corrupt the microphone/sensor ground;
4. what decoupling and return topology should be carried into the prototype.

The executable sizing model is:

`hardware/power_distribution_model.py`

The transient circuit cases are:

- `hardware/spice/power_distribution_star.cir`
- `hardware/spice/power_distribution_shared_return.cir`

Both are run by the electrical CI.

## Source devices and constraints

### Arduino UNO R4 WiFi

Arduino specifies 6-24 V on VIN / the DC jack. The board contains its own ISL854102 buck converter from VIN to the 5 V board rail. USB is a separate 5 V input path through a Schottky diode.

Source:
https://docs.arduino.cc/hardware/uno-r4-wifi
https://docs.arduino.cc/resources/schematics/ABX00087-schematics.pdf

This means the local fallback controller does not need to depend on HP USB power. Rev-C powers the UNO independently through VIN while USB can remain a data connection.

### External 5 V sensor rail

Rev-C uses the TI TPS54202 as the provisional external 5 V regulator.

TI specifies:

- 4.5-28 V input;
- 2 A continuous output;
- 500 kHz nominal switching frequency;
- 5 ms internal soft-start;
- peak-current-mode control;
- integrated synchronous MOSFETs.

For the published 5 V design, TI gives a starting point of:

- 15 uH output inductor;
- 44 uF output capacitance;
- 100 kOhm / 13.3 kOhm feedback divider;
- 75 pF feed-forward capacitor.

TI also recommends more than 10 uF local input ceramic decoupling and notes that about 47 uF additional bulk capacitance is a typical choice when the input source is several inches away.

Source:
https://www.ti.com/lit/ds/symlink/tps54202.pdf

Rev-C therefore does **not** route the PIR/radar/ultrasonic/audio electronics through the UNO regulator.

## Provisional architecture

```text
                       certified 12 V DC adapter
                                 |
                           input protection
                                 |
                            bulk capacitor
                                 |
             +-------------------+------------------+
             |                   |                  |
             |                   |                  |
         UNO R4 VIN        TPS54202 5 V        alarm branch
             |              sensor rail           fuse
       onboard buck             |                  |
             |             PIR / radar             |
        local fallback     ultrasonic / logic    MOSFET
                                |                  |
                                +----10R----+      siren
                                           |
                                       analog 5 V
                                           |
                                      220 uF + 100 nF
                                           |
                                  microphone front end
```

The alarm current has its **own return to the power star point**. It must not flow through the microphone/sensor ground conductor.

## Sizing envelope used for simulation

The physical modules and alarm are not all frozen yet, so these are deliberately conservative design-envelope values, not measured currents:

| Branch | Base | Stress state |
|---|---:|---:|
| UNO VIN equivalent input | 0.12 A | 0.25 A |
| external 5 V sensor rail | 0.15 A | 1.00 A |
| alarm on 12 V bus | 0 A | 0.50 A |
| analog front end | 0.004 A | 0.004 A |

The model assumes 90% conversion efficiency for the 12 V -> 5 V power-budget calculation.

At 1 A on the 5 V rail:

```text
equivalent 12 V input current ~= 0.463 A
```

With the UNO and 0.5 A alarm stress added:

```text
design-envelope 12 V peak ~= 1.213 A
```

This is below 2 A, but Rev-C reserves a **12 V / 3 A regulated adapter** as the prototype target because the real siren current and future peripherals are not frozen. The extra rating is margin, not a claim that the current design consumes 3 A.

No mains wiring is part of the project; use an approved external low-voltage adapter.

## Output-capacitor calculation

TI gives the load-step sizing relationship:

```text
Cout > 2 * delta_I / (fsw * delta_V)
```

For the Rev-C stress step:

```text
delta_I = 1.00 - 0.15 = 0.85 A
fsw     = 500 kHz
delta_V = 0.25 V  (5% of 5 V)
```

the simple minimum is:

```text
Cout > 13.6 uF
```

That does **not** replace loop-stability/layout requirements. TI's 5 V reference uses 44 uF, so Rev-C keeps **44 uF effective output capacitance as the minimum design target**.

For real ceramic capacitors, DC-bias derating must be checked. "Two 22 uF parts" is not automatically 44 uF effective at 5 V.

## First SPICE pass and issue found

The first star-ground transient model used 30 mOhm for the digital power return.

The 5 V regulator input-current step caused the digital power ground to move enough that the analog-to-digital ground difference could approach the same scale we are trying to eliminate.

That exposed an important layout requirement: "star ground" is not enough if the star legs themselves have unnecessarily high impedance.

Rev-C was changed to model:

```text
power-regulator return : 5 mOhm
UNO return             : 10 mOhm
analog return          : 10 mOhm
alarm return           : 30 mOhm, separate branch
```

These are design targets for a short/wide PCB or solid distribution wiring, **not measured breadboard resistances**.

The acceptance test was also corrected to measure both the minimum and maximum analog-to-power ground difference. The first checker looked only at MAX and could hide a larger negative excursion.

That checker bug was fixed before merge.

## Final ngspice results

The stress timing deliberately overlaps:

- the 0.15 -> 1.00 A 5 V load step;
- the 0 -> 0.50 A alarm load;
- the UNO input-current increase.

The current passing ngspice run measured:

| Measurement | Star-return result |
|---|---:|
| 12 V bus minimum | **11.695 V** |
| 5 V sensor rail minimum | **4.940 V** |
| 5 V sensor rail maximum | **4.991 V** |
| filtered analog rail minimum | **4.907 V** |
| filtered analog rail maximum | **4.951 V** |
| analog-to-power ground minimum | **-2.36 mV** |
| analog-to-power ground maximum | **-0.23 mV** |
| worst analog-to-power ground magnitude | **2.36 mV** |
| alarm-return ground rise | **15.00 mV** |

All Rev-C star-ground electrical acceptance checks passed.

## Shared-return comparison

A second circuit intentionally makes a bad prototype choice: the 0.5 A alarm current and microphone/analog return share a 0.10 Ohm return.

The same load sequence produced:

| Measurement | Shared-return result |
|---|---:|
| 12 V bus minimum | 11.695 V |
| 5 V sensor rail minimum | 4.940 V |
| filtered analog rail minimum | 4.870 V |
| analog/alarm ground differential peak | **50.39 mV** |
| differential before alarm | -2.26 mV |
| differential during alarm | **47.77 mV** |

The regulator rail itself still looks healthy. The failure mechanism is **ground movement**, not a dramatic 5 V rail collapse.

That matters for this project because the microphone detector is trying to distinguish small analog signals. Tens of millivolts of return-path movement are large compared with many microphone-level signals and can corrupt ADC measurements or create switching artifacts.

Therefore the alarm/siren return must not share the microphone return path.

## Analog rail isolation

The analog branch uses:

```text
5 V sensor rail
   |
  10 Ohm
   |
 analog 5 V
   |
 220 uF
   |
 analog ground

+ 100 nF local high-frequency decoupling
```

At the provisional 4 mA analog load:

```text
DC drop ~= 40 mV
nominal analog rail ~= 4.96 V
RC time constant ~= 2.2 ms
```

The full transient model reached a minimum of 4.907 V under the overlapping stress case.

The 10 Ohm resistor is appropriate only because this branch is intentionally low-current. Do not place radar, ultrasonic modules or the alarm behind this resistor.

## Prototype wiring rule

For the breadboard/perfboard stage, treat the system as separate current domains:

```text
                         STAR / supply return
                       /        |         \
                      /         |          \
                 alarm GND   digital GND   analog GND
                    |           |              |
                 MOSFET       UNO / 5V       mic/op-amp
                 siren        sensors
```

The grounds still share the same electrical reference. "Star" here means the high alarm current does not travel through the analog return conductor before reaching the common point.

## What this simulation proves

Within the stated abstraction and load envelope:

- independent VIN power for the UNO is compatible with the board's published input range;
- the provisional 12 V bus retains margin under the overlapping stress case;
- the 5 V sensor rail remains inside the chosen acceptance window;
- local analog RC filtering keeps the microphone rail above 4.9 V;
- a low-impedance star return keeps analog-to-power ground movement to a few millivolts in the model;
- sharing the alarm and microphone return produces about 50 mV of modeled ground movement and is rejected.

## What it does not prove

The TPS54202 itself is represented as a datasheet-based closed-loop power-source abstraction with the external rail impedance/capacitance modeled in ngspice. This is **not** TI's full transistor/switching macro-model.

The following still require physical or higher-fidelity validation:

- actual 12 V adapter source impedance and transient response;
- actual UNO VIN current with Wi-Fi, LED matrix and serial activity;
- exact radar/PIR/ultrasonic current waveforms;
- exact alarm/siren startup and steady current;
- effective ceramic capacitance at DC bias;
- TPS54202 switching ripple, compensation and EMI on the real PCB;
- breadboard/contact resistance;
- oscilloscope measurement of analog-ground movement during alarm switching;
- physical brownout and USB-disconnect tests.

The next prototype should measure those values rather than replacing the present design envelope with guesses.
