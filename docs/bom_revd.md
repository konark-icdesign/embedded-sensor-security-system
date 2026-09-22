# Rev-D prototype BOM

This is the buildable prototype BOM for the room-security node. It freezes parts where the electrical design is now specific enough to do so. Prices are not requirements and should be rechecked before ordering.

| Qty | Part | Function | Prototype package / note |
|---:|---|---|---|
| 1 | Arduino UNO R4 WiFi / user's UNO Ek R4 WiFi | local controller | existing board |
| 1 | Panasonic EKMC1601111 | PIR motion sensor | through-hole TO-5; 5 V operation in this design |
| 1 | Hi-Link HLK-LD2412 | 24 GHz presence radar | 5 V supply, 3.3 V GPIO OUT; UART reserved for later health/range integration |
| 1 | SparkFun SEN-24049 / HC-SR04-33 | ultrasonic range sensor | 3.3-5 V module, used at 5 V |
| 1 | TI SN74AHCT14N | sensor Schmitt conditioning | PDIP-14; four gates used, two spare |
| 1 | Microchip MCP6022-I/P | microphone preamp + midpoint buffer | PDIP-8 |
| 1 | Same Sky/CUI CMA-4544PF-W | electret microphone | through-hole |
| 1 | AOS AO3400A | alarm low-side switch | SOT-23; use an adapter board for breadboard work |
| 1 | SS34 or suitable Schottky/flyback diode | alarm transient clamp | final part depends on alarm load |
| 1 | TPS54202 | final 12 V -> 5 V sensor buck | **PCB/daughterboard only**; do not build this switching regulator on a solderless breadboard |
| 1 | regulated 12 V / 3 A adapter | prototype system supply | approved external low-voltage adapter; no mains wiring in project |
| 1 | 100 kOhm 1% resistor | PIR idle pulldown | sensor side of series RC |
| 1 | 100 kOhm 1% resistor | radar idle pulldown | sensor side of series RC |
| 2 | 10 kOhm 1% resistor | PIR/radar series RC | after the pulldown node |
| 2 | 10 nF capacitor | PIR/radar RC filter | one per channel |
| 1 | 100 nF capacitor | SN74AHCT14 decoupling | place at IC supply pins |
| 1 | 220 Ohm resistor | ultrasonic TRIG series resistor | D4 -> TRIG |
| 1 | 1 kOhm resistor | ultrasonic ECHO series resistor | ECHO -> D5 |
| 1 | 100 kOhm resistor | ultrasonic ECHO pulldown | MCU side |
| 1 | 100 pF capacitor | ultrasonic ECHO shunt | MCU side |
| 1 | 1.5 kOhm resistor | AO3400A gate resistor | D9 -> gate |
| 1 | 100 kOhm resistor | AO3400A gate pulldown | gate -> GND |
| assorted | 1% resistors / capacitors | microphone and indicator circuits | values in docs/microphone_frontend_revb.md |
| several | 2.54 mm headers / screw terminals / test pins | serviceable prototype wiring | label all test points |
| 1 | small perfboard/PCB for PIR | mechanical support | Panasonic specifies PCB mounting; do not leave the PIR hanging from breadboard jumpers |
| 1 | SOT-23 adapter | AO3400A prototype | breadboard adapter or soldered daughterboard |

## Part-selection notes

### PIR: EKMC1601111 instead of EKMB1101111

The earlier research considered Panasonic EKMB1101111. Rev-D selects **EKMC1601111** because it is still a real Panasonic board-mount PIR intended for security/equipment use, but it is substantially more practical for this prototype:

- 3-6 V operating range;
- 5 m standard detection range;
- digital output;
- 170 uA standby current;
- 100 uA maximum output load during detection;
- **30 s maximum circuit-stability time**.

The existing 60 s firmware startup inhibit is therefore conservative.

The EKMB1101111 remains a valid low-power alternative, but its published worst-case circuit stability time can be much longer and its India distributor price is much higher. Low standby current is not valuable enough here to justify those disadvantages.

### Radar: HLK-LD2412

Rev-D replaces the vague "LD2410-class" assumption with **HLK-LD2412**:

- 24 GHz FMCW presence radar;
- 5 V or 3.3 V module supply;
- input supply capability required >200 mA;
- approximately 90 mA average operating current;
- 3.3 V GPIO output;
- GPIO and UART interfaces;
- default UART 115200 baud;
- up to 9 m nominal sensing distance;
- 0.75 m distance resolution;
- wide-angle indoor coverage.

The local fallback firmware continues to use GPIO OUT. UART is reserved for a later step because it can provide health/configuration/range data that a single GPIO cannot.

### Ultrasonic: HC-SR04-33

Rev-D uses the 3.3-5 V HC-SR04-33 electrical specification already matched by the firmware:

- 10 us trigger pulse;
- roughly 15 mA operating current;
- 2 cm to 4 m nominal range;
- TTL echo pulse proportional to round-trip time.

The module is kept because the existing range filter, timeout handling and electrical simulation are already built around this interface. It is not treated as the sole intrusion sensor.

## Power-prototype rule

The **sensor logic and analog circuits** may be breadboarded.

The **TPS54202 switching regulator should not be built on a solderless breadboard**. Its current loops, inductor, ceramic capacitors and switching node need controlled short connections. For first physical testing use either:

1. a bench 5 V supply for the sensor rail while validating the circuits, or
2. a known-good buck module/EVM for the temporary power source.

The final project PCB can then implement the TPS54202 block using TI's layout guidance.

## Sources

- Panasonic EKMC1601111: https://na.industrial.panasonic.com/products/sensors/lineup/sensors-automotive-industrial-applications/series/149463/model/149603
- Panasonic reference specification: https://industrial.panasonic.com/cdbs/www-data/pdf/EWA0000/bltn_eng_ekmc160611_ast-ind-247327.pdf
- Hi-Link LD2412: https://www.hlktech.net/index.php?cateid=768&id=1199
- Hi-Link LD2412 manual: https://r0.hlktech.com/download/HLK-LD2412-24G/1/HLK%20LD2412%E7%94%9F%E5%91%BD%E5%AD%98%E5%9C%A8%E6%84%9F%E5%BA%94%E6%A8%A1%E7%BB%84%E8%AF%B4%E6%98%8E%E4%B9%A6%20V1.02%20.pdf
- SparkFun HC-SR04-33 datasheet: https://cdn.sparkfun.com/assets/a/8/9/c/a/HC-SR04-33_Datasheet.pdf
- TI SN74AHCT14: https://www.ti.com/product/SN74AHCT14
- Microchip MCP6022: https://www.microchip.com/en-us/product/mcp6022
- AOS AO3400A: https://www.aosmd.com/products/mosfets/low-voltage-mosfets-12v-30v/ao3400a
- TI TPS54202: https://www.ti.com/product/TPS54202
