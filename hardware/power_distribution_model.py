#!/usr/bin/env python3
"""Rev-C low-voltage power-distribution calculations.

This is a datasheet-based sizing/checking model. It complements, but does not
replace, the ngspice transient circuits in hardware/spice/.
"""

from math import ceil

VIN = 12.0
VOUT = 5.0
EFF = 0.90
FSW = 500_000.0

# Deliberately conservative design envelope until the exact alarm and all
# sensor variants are physically measured.
SENSOR_BASE_A = 0.15
SENSOR_STEP_A = 1.00
UNO_BASE_A = 0.12
UNO_PEAK_A = 0.25
ALARM_A = 0.50
ANALOG_A = 0.004

# TI load-step capacitor sizing equation:
# C > 2 * dI / (fsw * dV)
ALLOWABLE_DV = 0.25  # 5% of 5 V
DELTA_I = SENSOR_STEP_A - SENSOR_BASE_A
C_MIN_F = 2.0 * DELTA_I / (FSW * ALLOWABLE_DV)

TI_REFERENCE_COUT_F = 44e-6
SELECTED_ANALOG_C_F = 220e-6
ANALOG_FEED_R = 10.0

BUCK_INPUT_BASE_A = VOUT * SENSOR_BASE_A / (VIN * EFF)
BUCK_INPUT_PEAK_A = VOUT * SENSOR_STEP_A / (VIN * EFF)

PEAK_12V_BUS_A = UNO_PEAK_A + BUCK_INPUT_PEAK_A + ALARM_A
SUPPLY_2A_MARGIN_A = 2.0 - PEAK_12V_BUS_A
SUPPLY_3A_MARGIN_A = 3.0 - PEAK_12V_BUS_A

STAR_ANALOG_RETURN_R = 0.02
SHARED_RETURN_R = 0.10
STAR_ANALOG_SHIFT_V = ANALOG_A * STAR_ANALOG_RETURN_R
SHARED_ALARM_SHIFT_V = (ALARM_A + ANALOG_A) * SHARED_RETURN_R

ANALOG_DC_DROP_V = ANALOG_A * ANALOG_FEED_R
ANALOG_RAIL_NOMINAL_V = VOUT - ANALOG_DC_DROP_V
ANALOG_TAU_S = ANALOG_FEED_R * SELECTED_ANALOG_C_F

print("Rev-C power-distribution sizing")
print(f"TPS54202 fsw used:                 {FSW/1000:.0f} kHz")
print(f"5 V load step:                     {SENSOR_BASE_A:.2f} -> {SENSOR_STEP_A:.2f} A")
print(f"minimum C for <=250 mV step:       {C_MIN_F*1e6:.2f} uF")
print(f"TI 5 V reference COUT:             {TI_REFERENCE_COUT_F*1e6:.0f} uF")
print(f"buck input current at 0.15 A/5 V:  {BUCK_INPUT_BASE_A:.3f} A")
print(f"buck input current at 1.00 A/5 V:  {BUCK_INPUT_PEAK_A:.3f} A")
print(f"design-envelope 12 V peak current: {PEAK_12V_BUS_A:.3f} A")
print(f"12 V / 2 A remaining margin:       {SUPPLY_2A_MARGIN_A:.3f} A")
print(f"12 V / 3 A remaining margin:       {SUPPLY_3A_MARGIN_A:.3f} A")
print(f"analog rail DC estimate:           {ANALOG_RAIL_NOMINAL_V:.3f} V")
print(f"analog RC isolation tau:           {ANALOG_TAU_S*1000:.2f} ms")
print(f"star analog-ground shift:          {STAR_ANALOG_SHIFT_V*1000:.3f} mV")
print(f"shared alarm-ground shift:         {SHARED_ALARM_SHIFT_V*1000:.1f} mV")

assert C_MIN_F < TI_REFERENCE_COUT_F
assert PEAK_12V_BUS_A < 2.0
assert ANALOG_RAIL_NOMINAL_V > 4.9
assert STAR_ANALOG_SHIFT_V < 0.001
assert SHARED_ALARM_SHIFT_V > 0.040
