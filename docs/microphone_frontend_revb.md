# Rev-B microphone analog front end

This is the first buildable analog-audio block for the room-security prototype. It is intended for breadboard/perfboard bring-up before a PCB.

It is separate from the earlier synthetic audio detector: this document is about the **physical microphone signal chain** that would feed a real audio ADC/interface.

## Selected prototype parts

These are design choices for Rev-B, not claims about hardware already purchased.

| Part | Role | Why selected |
|---|---|---|
| Same Sky/CUI CMA-4544PF-W | electret microphone capsule | pin type, 3 V standard operating voltage, -44 dBV/Pa typical sensitivity, 2.2 kOhm output impedance, 60 dBA SNR, 20 Hz-20 kHz published range |
| Microchip MCP6022-I/P | dual op amp | 8-pin PDIP for breadboard, RRIO, 2.5-5.5 V supply range, 10 MHz GBW, 7 V/us typical slew rate, 8.7 nV/sqrt(Hz) typical noise |
| 1% resistors + film/C0G/quality ceramic capacitors where practical | gain/filter network | keeps the analog response repeatable |

References:
- https://www.sameskydevices.com/product/audio/microphones/electret-condenser-microphones/cma-4544pf-w
- https://www.microchip.com/en-us/product/mcp6022
- https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/20001685E.pdf

## Proposed breadboard circuit

The electret capsule is biased from 3.3 V through 2.2 kOhm. Its AC signal is coupled into a 5 V single-supply preamp.

```text
3.3 V
  |
  2.2k
  |
 electret mic
  |
  +---- 100 nF ---- preamp input
  |
 GND

5 V ---10k---+---10k---GND
             |
           10 uF
             |
            GND
             |
        MCP6022-A buffer
             |
          Vmid = 2.5 V

preamp input ---- 22k ---- Vmid

MCP6022-B:
  non-inverting input = preamp input
  Rg = 2.49k to Vmid
  Rf = 49.9k from output to inverting input

nominal closed-loop gain:
  1 + 49.9k/2.49k = 21.04 V/V

preamp output ---- 3.3k ---- AUDIO_BIASED
                              |
                            5.6 nF
                              |
                            Vmid

AUDIO_BIASED ---- 4.7 uF ---- AUDIO_LINE
                                  |
                                100k
                                  |
                                 GND
```

Also place 100 nF directly across the MCP6022 supply pins.

`AUDIO_BIASED` is centered on about 2.5 V and is suitable for a later ADC stage whose input range is designed around that bias.

`AUDIO_LINE` is AC-coupled for an external audio interface. The exact ADC/audio-interface IC is not frozen yet.

## Why the first virtual-ground values were changed

The first candidate used:

```text
47k / 47k divider
10 uF capacitor
```

That looks attractive because it wastes less current, but its Thevenin resistance is 23.5 kOhm. The simulated bias startup is therefore slow.

The ngspice startup comparison measured:

| Vmid network | 99% settling time | Vmid at 250 ms |
|---|---:|---:|
| 47k / 47k + 10 uF | 1083.2 ms | 1.6335 V |
| 10k / 10k + 10 uF | **231.3 ms** | **2.4828 V** |

So Rev-B uses **10k / 10k + 10 uF**.

This does not matter after the system has been running for seconds, but it removes an unnecessary ~1 s analog-bias transient and gives the midpoint a stiffer source before buffering.

## Frequency-response simulation

The signal path is solved in ngspice. The MCP6022 stage is currently a datasheet-based closed-loop behavioral model rather than Microchip's full transistor/macromodel.

The simulated gain from the microphone Thevenin source to `AUDIO_BIASED` is:

| Frequency | Gain |
|---:|---:|
| 60 Hz | 21.49 dB |
| 1 kHz | **24.81 dB** |
| 8 kHz | 21.35 dB |
| 16 kHz | 16.95 dB |

Therefore:

- 60 Hz is about **3.32 dB below** the 1 kHz gain;
- 8 kHz is about **3.46 dB below** 1 kHz;
- 16 kHz is about **7.86 dB below** 1 kHz.

The nominal op-amp resistor gain is 26.46 dB. The lower measured 1 kHz end-to-end gain is expected because the microphone's 2.2 kOhm source impedance, 22 kOhm bias resistor, coupling network and output filter are included in the circuit.

This gives a useful room-security passband while reducing very-low-frequency rumble and high-frequency content before the ADC/interface.

## 110 dB SPL headroom check

The CMA-4544PF-W typical sensitivity is -44 dBV/Pa.

At 110 dB SPL:

```text
pressure ~= 6.3246 Pa
microphone ~= 39.905 mVrms
           ~= 56.435 mV peak
```

The transient simulation produced:

```text
AUDIO_BIASED minimum = 1.518 V
AUDIO_BIASED maximum = 3.482 V
peak-to-peak         = 1.965 V
bias center          = 2.500 V
```

So the selected gain does not drive the modeled 5 V analog path into either rail at the microphone's published 110 dB maximum-SPL region.

This is **not** a distortion measurement of the real microphone or op amp. The microphone itself has an acoustic overload specification, and the physical circuit still needs bench measurements.

## CI acceptance

The electrical CI now runs:

- `sensor_interface.cir`
- `echo_interface.cir`
- `alarm_driver.cir`
- `microphone_frontend.cir`
- `microphone_vmid_startup.cir`

The microphone checks fail CI if:

- 1 kHz gain moves outside 24.5-26.5 dB;
- 60 Hz is not sufficiently reduced;
- the 8 kHz / 16 kHz roll-off disappears;
- line output no longer tracks the biased output;
- the selected midpoint takes longer than 300 ms to reach 99%;
- the old 47k midpoint unexpectedly behaves as though it were the selected design;
- 110 dB SPL drives the modeled signal too close to either 5 V rail.

The recorded run passed all microphone and existing Rev-A electrical checks.

## What this fixes

The security project previously said "microphone" but had no physical analog signal chain.

Rev-B now defines a concrete prototype path with:

- an exact microphone part;
- an exact breadboard-friendly op amp;
- microphone bias;
- AC coupling;
- virtual-ground generation;
- analog gain;
- low/high frequency shaping;
- an ADC-biased output;
- an AC-coupled external line output;
- automated SPICE regression checks.

It also found and removed the slow 47k/47k midpoint candidate before hardware was built.

## Still not proved

No physical microphone, MCP6022, breadboard, audio interface, oscilloscope or sound-pressure calibration has been tested.

The following remain bench tasks:

1. Measure the real Vmid startup waveform.
2. Measure gain at 60 Hz, 1 kHz, 8 kHz and 16 kHz.
3. Measure microphone DC bias current and capsule voltage.
4. Measure clipping with a known electrical injection before using loud acoustic tests.
5. Measure real noise floor with the microphone connected.
6. Measure 50/60 Hz pickup with breadboard wiring.
7. Compare breadboard response with the ngspice model.
8. Freeze the ADC/audio-interface device and verify its input common-mode/full-scale requirements.
9. Re-test after transferring the circuit from breadboard to PCB.

The current SPICE model validates the first-order topology and margins. It is not a substitute for the physical bench.
