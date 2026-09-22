# Rev-D buildable hardware package

Rev-D freezes the main prototype sensors and converts the earlier generic interface assumptions into a breadboard/perfboard-ready design.

This is still pre-bench engineering. No physical sensor has been measured yet.

## Frozen sensing parts

- PIR: Panasonic **EKMC1601111**
- radar: Hi-Link **HLK-LD2412**
- ultrasonic: SparkFun **SEN-24049 / HC-SR04-33 electrical type**
- logic conditioner: TI **SN74AHCT14N**
- microphone front end: existing Rev-B **CMA-4544PF-W + MCP6022-I/P**
- alarm switch: existing **AO3400A**
- final sensor-rail buck: existing **TPS54202** Rev-C design

The complete prototype BOM is in [bom_revd.md](bom_revd.md).

## Why the PIR changed from the earlier low-power candidate

The earlier electrical work treated the PIR as a generic 3.3 V source and later research considered EKMB1101111.

Rev-D instead selects **EKMC1601111**.

For this mains-powered room-security prototype, its 170 uA standby current is insignificant, while it has two practical advantages:

1. it runs directly from the 5 V sensor rail (published 3-6 V operating range);
2. its published maximum startup stability time is **30 s**, compared with the much longer worst-case startup of the 1 uA EKMB type.

The firmware already inhibits alarm operation for 60 s after boot, so the selected PIR has a conservative startup margin.

Panasonic also states that the digital output is open when not detecting, and during detection the output can support up to 100 uA while maintaining at least Vdd - 0.5 V.

## Sensor-interface correction found during Rev-D

The older Rev-A circuit placed the 100 kOhm idle pulldown on the MCU/filter side of the 10 kOhm series resistor:

```text
sensor OUT --10k--+-- logic
                  |
                 100k
                  |
                 GND
```

That creates a DC divider.

For a 3.3 V output:

```text
Vnode = 3.3 * 100k / (100k + 10k)
      = 3.00 V
```

The circuit passed the earlier AHCT threshold test, but the attenuation is unnecessary.

Rev-D moves the pulldown to the sensor side:

```text
                 100k
                  |
sensor OUT -------+----10k----+---- SN74AHCT14 x2 ---- UNO R4
                  |           |
                 GND         10nF
                              |
                             GND
```

At DC, the AHCT input draws essentially no load, so the 10 kOhm resistor no longer forms a meaningful divider with the 100 kOhm pulldown.

The 10 kOhm / 10 nF network still provides first-order edge/noise filtering:

```text
tau ~= R * C = 100 us
```

Two AHCT inverter stages preserve the original signal polarity.

## Exact-part ngspice result

The Rev-D exact-part model is `hardware/spice/revd_sensor_frontend.cir`.

The passing CI transient run measured:

| Measurement | Result |
|---|---:|
| EKMC worst-case filtered HIGH | **4.4697 V** |
| EKMC conditioned HIGH to UNO | **4.4000 V** |
| EKMC modeled source current | **48.03 uA** |
| EKMC RC node crossing 2.1 V | **62.86 us** |
| LD2412 filtered HIGH | **3.2778 V** |
| LD2412 conditioned HIGH to UNO | **4.4000 V** |
| LD2412 RC node crossing 2.1 V | **101.16 us** |

All Rev-D electrical acceptance checks passed.

The modeled EKMC current remains below the 100 uA output-current limit used by Panasonic for the detection-output specification.

The conditioned 4.4 V logic level is intentionally conservative: it corresponds to the SN74AHCT14 guaranteed light-load HIGH region rather than assuming an ideal 5.0 V output.

## PIR electrical loading

At the worst guaranteed EKMC detection output used in the Rev-D model:

```text
Vout(min) = 5.0 - 0.5 = 4.5 V
Rpull     = 100 kOhm
```

The static pulldown current is:

```text
I = 4.5 / 100k = 45 uA
```

This is below Panasonic's 100 uA maximum output-current condition.

The SN74AHCT14 adds only a very small DC input current compared with that budget.

## Radar interface

HLK-LD2412 is powered from the 5 V sensor rail.

The manufacturer specifies:

- average current around 90 mA;
- supply capability greater than 200 mA;
- 3.3 V GPIO output;
- GPIO and UART interfaces;
- default UART rate 115200 baud;
- nominal range up to 9 m.

The local fallback path uses the GPIO output through the same Rev-D RC + AHCT conditioner.

A later firmware stage should use the UART as well. GPIO alone cannot prove that the radar communication path is healthy or expose its measured distance/engineering data.

## Ultrasonic interface

The current D4/D5 circuit remains:

```text
UNO D4 -- 220R --> TRIG

ECHO -- 1k --+--> UNO D5
             |
            100pF
             |
            GND

D5 ---- 100k ---- GND
```

The HC-SR04-33 electrical reference supports 3.3-5 V operation, approximately 15 mA working current, a >=10 us trigger pulse and a nominal 2 cm to 4 m range.

The firmware still uses a 30 ms echo timeout and treats no echo as invalid data rather than zero distance.

## Breadboard/perfboard split

Do not put every block on a solderless breadboard just to say it was breadboarded.

### Suitable for solderless breadboard

- SN74AHCT14N input conditioning
- MCP6022 microphone front end
- LEDs and status logic
- low-current RC networks
- sensor connectors for short bench wiring

### Use a daughterboard/perfboard/PCB

- Panasonic PIR mechanical mounting: Panasonic recommends PCB mounting
- AO3400A: SOT-23 adapter/daughterboard
- TPS54202 switching regulator: short power loops and layout matter
- high-current alarm path
- final star-ground distribution

For early testing, the sensor 5 V rail may come from a bench supply or a known-good buck board. That does not change the final Rev-C TPS54202 design.

## Test points

The prototype should expose these labelled test points:

| TP | Signal | Expected use |
|---|---|---|
| TP1 | 12V_BUS | input-supply sag during alarm |
| TP2 | SENSOR_5V | sensor rail transient/ripple |
| TP3 | ANALOG_5V | filtered microphone supply |
| TP4 | VMID_2V5 | microphone virtual ground |
| TP5 | MIC_PREAMP | biased microphone waveform |
| TP6 | PIR_RAW | EKMC raw output before RC |
| TP7 | PIR_FILTERED | RC node before AHCT |
| TP8 | PIR_R4 | conditioned 5 V logic |
| TP9 | RADAR_RAW | LD2412 3.3 V GPIO |
| TP10 | RADAR_R4 | conditioned 5 V logic |
| TP11 | US_ECHO | ultrasonic echo after protection |
| TP12 | ALARM_GATE | MOSFET gate waveform |
| TP13 | ALARM_DRAIN | switched load node |
| TP14 | ANALOG_GND | analog return |
| TP15 | POWER_STAR | reference for ground-shift measurement |

## Bench measurements required

The first physical pass should record:

1. EKMC startup output for at least 60 s.
2. EKMC output HIGH voltage with the 100 kOhm pulldown fitted.
3. LD2412 5 V current: idle, moving person and stationary-person states.
4. LD2412 GPIO HIGH/LOW voltages.
5. Ultrasonic invalid-echo rate at known distances.
6. 5 V rail and analog ground while the alarm is switched.
7. Microphone gain/noise with alarm off and on.
8. AHCT input and output edges at TP7/TP8 and TP9/TP10.
9. USB disconnect while UNO remains powered through VIN.

These measurements replace assumptions in Rev-A through Rev-D one by one.

## Sources

- Panasonic EKMC1601111 product page: https://na.industrial.panasonic.com/products/sensors/lineup/sensors-automotive-industrial-applications/series/149463/model/149603
- Panasonic EKMC reference specification: https://industrial.panasonic.com/cdbs/www-data/pdf/EWA0000/bltn_eng_ekmc160611_ast-ind-247327.pdf
- Hi-Link LD2412 product page: https://www.hlktech.net/index.php?cateid=768&id=1199
- Hi-Link LD2412 manual: https://r0.hlktech.com/download/HLK-LD2412-24G/1/HLK%20LD2412%E7%94%9F%E5%91%BD%E5%AD%98%E5%9C%A8%E6%84%9F%E5%BA%94%E6%A8%A1%E7%BB%84%E8%AF%B4%E6%98%8E%E4%B9%A6%20V1.02%20.pdf
- HC-SR04-33 electrical reference: https://cdn.sparkfun.com/assets/a/8/9/c/a/HC-SR04-33_Datasheet.pdf
- TI SN74AHCT14: https://www.ti.com/product/SN74AHCT14
