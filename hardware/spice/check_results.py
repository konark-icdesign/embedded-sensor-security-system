#!/usr/bin/env python3
"""Fail CI when the SPICE circuits violate the intended electrical envelope."""
from pathlib import Path
import math
import re

ROOT = Path("results/spice")


def measurement(log_name, key):
    text = (ROOT / log_name).read_text(encoding="utf-8", errors="replace")
    match = re.search(
        rf"(?mi)^\s*{re.escape(key)}\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)",
        text,
    )
    if not match:
        raise SystemExit(f"missing SPICE measurement {key} in {log_name}")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise SystemExit(f"non-finite SPICE measurement {key}={value}")
    return value


sensor_cross = measurement("sensor_interface.log", "t_filter_cross")
sensor_out = measurement("sensor_interface.log", "t_out_cross")
sensor_high = measurement("sensor_interface.log", "filtered_high")
logic_high = measurement("sensor_interface.log", "output_high")

echo_cross = measurement("echo_interface.log", "t_echo_4v")
echo_high = measurement("echo_interface.log", "d5_high")

gate_cross = measurement("alarm_driver.log", "gate_4p5")
load_current = abs(measurement("alarm_driver.log", "load_current_on"))
drain_on = measurement("alarm_driver.log", "drain_on")
drain_peak = measurement("alarm_driver.log", "drain_peak")

mic_out60_max = measurement("microphone_frontend.log", "out60_max")
mic_out60_min = measurement("microphone_frontend.log", "out60_min")
mic_out1k_max = measurement("microphone_frontend.log", "out1k_max")
mic_out1k_min = measurement("microphone_frontend.log", "out1k_min")
mic_out8k_max = measurement("microphone_frontend.log", "out8k_max")
mic_out8k_min = measurement("microphone_frontend.log", "out8k_min")
mic_out16k_max = measurement("microphone_frontend.log", "out16k_max")
mic_out16k_min = measurement("microphone_frontend.log", "out16k_min")
mic_line1k_max = measurement("microphone_frontend.log", "line1k_max")
mic_line1k_min = measurement("microphone_frontend.log", "line1k_min")
mic_audio_max = measurement("microphone_frontend.log", "audio_max")
mic_audio_min = measurement("microphone_frontend.log", "audio_min")
mic_vmid_steady = measurement("microphone_frontend.log", "vmid_steady")
mic_audio_pp = mic_audio_max - mic_audio_min

mic_vmid_fast_99 = measurement("microphone_vmid_startup.log", "vmid_fast_99")
mic_vmid_slow_99 = measurement("microphone_vmid_startup.log", "vmid_slow_99")
mic_vmid_fast_250m = measurement("microphone_vmid_startup.log", "vmid_fast_250m")
mic_vmid_slow_250m = measurement("microphone_vmid_startup.log", "vmid_slow_250m")

# Small-signal channels are driven with 10 mV peak, so gain is Vpp / 20 mV.
mic_gain_60 = (mic_out60_max - mic_out60_min) / 0.020
mic_gain_1k = (mic_out1k_max - mic_out1k_min) / 0.020
mic_gain_8k = (mic_out8k_max - mic_out8k_min) / 0.020
mic_gain_16k = (mic_out16k_max - mic_out16k_min) / 0.020
mic_line_gain_1k = (mic_line1k_max - mic_line1k_min) / 0.020

mic_gain_60_db = 20.0 * math.log10(mic_gain_60)
mic_gain_1k_db = 20.0 * math.log10(mic_gain_1k)
mic_gain_8k_db = 20.0 * math.log10(mic_gain_8k)
mic_gain_16k_db = 20.0 * math.log10(mic_gain_16k)
mic_line_gain_1k_db = 20.0 * math.log10(mic_line_gain_1k)

star_vin_min = measurement("power_distribution_star.log", "vin_min")
star_rail5_min = measurement("power_distribution_star.log", "rail5_min")
star_rail5_max = measurement("power_distribution_star.log", "rail5_max")
star_analog5_min = measurement("power_distribution_star.log", "analog5_min")
star_analog5_max = measurement("power_distribution_star.log", "analog5_max")
star_analog_ground_peak = measurement("power_distribution_star.log", "analog_ground_peak")
star_alarm_ground_peak = measurement("power_distribution_star.log", "alarm_ground_peak")
star_vin_at_peak = measurement("power_distribution_star.log", "vin_at_peak")

shared_vin_min = measurement("power_distribution_shared_return.log", "vin_min")
shared_rail5_min = measurement("power_distribution_shared_return.log", "rail5_min")
shared_analog5_min = measurement("power_distribution_shared_return.log", "analog5_min")
shared_ground_peak = measurement("power_distribution_shared_return.log", "shared_ground_peak")
shared_ground_quiet = measurement("power_distribution_shared_return.log", "shared_ground_quiet")
shared_ground_alarm = measurement("power_distribution_shared_return.log", "shared_ground_alarm")

# All pulse sources rise at t=1 ms in these netlists.
sensor_delay = sensor_cross - 1e-3
sensor_logic_delay = sensor_out - 1e-3
echo_delay = echo_cross - 1e-3
gate_delay = gate_cross - 1e-3

checks = {
    "sensor_filtered_high_2p8_to_3p05_V": 2.8 <= sensor_high <= 3.05,
    "conditioned_R4_logic_high_above_4V": logic_high >= 4.0,
    "sensor_RC_crossing_80_to_150_us": 80e-6 <= sensor_delay <= 150e-6,
    "conditioned_output_crossing_under_160_us": 0 <= sensor_logic_delay <= 160e-6,
    "echo_high_above_R4_VIH": echo_high >= 4.0,
    "echo_4V_crossing_under_1_us": 0 <= echo_delay <= 1e-6,
    "alarm_gate_4p5_under_10_us": 0 <= gate_delay <= 10e-6,
    "alarm_current_about_0p5A": 0.45 <= load_current <= 0.55,
    "alarm_MOSFET_on_drop_under_100mV": 0 <= drain_on <= 0.100,
    "flyback_peak_under_15V_in_model": 0 <= drain_peak <= 15.0,
    "microphone_1k_gain_24p5_to_26p5dB": 24.5 <= mic_gain_1k_db <= 26.5,
    "microphone_60Hz_at_least_2p5dB_below_1k": mic_gain_60_db <= mic_gain_1k_db - 2.5,
    "microphone_8k_rolloff_2_to_4dB": 2.0 <= mic_gain_1k_db - mic_gain_8k_db <= 4.0,
    "microphone_16k_at_least_6dB_below_1k": mic_gain_16k_db <= mic_gain_1k_db - 6.0,
    "microphone_line_out_tracks_audio_at_1k": abs(mic_line_gain_1k_db - mic_gain_1k_db) <= 0.2,
    "microphone_selected_vmid_99_under_0p30s": 0 < mic_vmid_fast_99 < 0.30,
    "microphone_old_47k_vmid_is_slow": mic_vmid_slow_99 > 0.90,
    "microphone_selected_vmid_near_settled_by_250ms": mic_vmid_fast_250m > 2.45,
    "microphone_old_vmid_not_settled_by_250ms": mic_vmid_slow_250m < 1.8,
    "microphone_vmid_settled_near_2p5V": 2.45 <= mic_vmid_steady <= 2.50,
    "microphone_110dB_no_low_rail_clip": mic_audio_min > 1.0,
    "microphone_110dB_no_high_rail_clip": mic_audio_max < 4.0,
    "microphone_110dB_output_pp_reasonable": 1.8 <= mic_audio_pp <= 2.4,
    "power_star_12V_bus_stays_above_11p5V": star_vin_min > 11.5,
    "power_star_5V_sensor_rail_stays_above_4p90V": star_rail5_min > 4.90,
    "power_star_5V_sensor_rail_stays_below_5p05V": star_rail5_max < 5.05,
    "power_star_analog_rail_stays_above_4p85V": star_analog5_min > 4.85,
    "power_star_analog_ground_shift_under_5mV": abs(star_analog_ground_peak) < 0.005,
    "power_star_alarm_return_shift_under_25mV": abs(star_alarm_ground_peak) < 0.025,
    "power_shared_return_creates_over_40mV_ground_shift": abs(shared_ground_peak) > 0.040,
    "power_shared_alarm_adds_over_35mV_shift": abs(shared_ground_alarm - shared_ground_quiet) > 0.035,
    "power_shared_5V_rail_itself_still_regulated": shared_rail5_min > 4.90,
    "power_shared_analog_supply_not_collapsed": shared_analog5_min > 4.80,
}

print("SPICE acceptance measurements")
print(f"sensor RC 2.1V crossing delay: {sensor_delay * 1e6:.3f} us")
print(f"conditioned output 4V delay:    {sensor_logic_delay * 1e6:.3f} us")
print(f"filtered sensor HIGH:           {sensor_high:.4f} V")
print(f"conditioned logic HIGH:         {logic_high:.4f} V")
print(f"HC-SR04 D5 4V delay:            {echo_delay * 1e9:.1f} ns")
print(f"HC-SR04 D5 HIGH:                {echo_high:.4f} V")
print(f"alarm gate 4.5V delay:          {gate_delay * 1e6:.3f} us")
print(f"alarm load current:             {load_current:.4f} A")
print(f"alarm MOSFET drain ON:          {drain_on * 1e3:.2f} mV")
print(f"flyback drain peak:             {drain_peak:.3f} V")
print(f"microphone gain @ 60 Hz:        {mic_gain_60_db:.2f} dB")
print(f"microphone gain @ 1 kHz:        {mic_gain_1k_db:.2f} dB")
print(f"microphone gain @ 8 kHz:        {mic_gain_8k_db:.2f} dB")
print(f"microphone gain @ 16 kHz:       {mic_gain_16k_db:.2f} dB")
print(f"microphone line gain @ 1 kHz:   {mic_line_gain_1k_db:.2f} dB")
print(f"selected Vmid 99% settle:       {mic_vmid_fast_99 * 1e3:.1f} ms")
print(f"47k candidate Vmid 99% settle:  {mic_vmid_slow_99 * 1e3:.1f} ms")
print(f"selected Vmid @ 250 ms:         {mic_vmid_fast_250m:.4f} V")
print(f"47k candidate Vmid @ 250 ms:    {mic_vmid_slow_250m:.4f} V")
print(f"microphone Vmid steady:         {mic_vmid_steady:.4f} V")
print(f"110 dB SPL audio min/max:       {mic_audio_min:.3f} / {mic_audio_max:.3f} V")
print(f"110 dB SPL audio p-p:           {mic_audio_pp:.3f} V")
print(f"Rev-C star VIN minimum:          {star_vin_min:.3f} V")
print(f"Rev-C star 5V rail min/max:      {star_rail5_min:.3f} / {star_rail5_max:.3f} V")
print(f"Rev-C star analog rail min/max:  {star_analog5_min:.3f} / {star_analog5_max:.3f} V")
print(f"Rev-C star analog ground peak:   {star_analog_ground_peak * 1e3:.2f} mV")
print(f"Rev-C star alarm ground peak:    {star_alarm_ground_peak * 1e3:.2f} mV")
print(f"Rev-C shared VIN minimum:        {shared_vin_min:.3f} V")
print(f"Rev-C shared 5V rail minimum:    {shared_rail5_min:.3f} V")
print(f"Rev-C shared analog rail min:    {shared_analog5_min:.3f} V")
print(f"Rev-C shared ground peak:        {shared_ground_peak * 1e3:.2f} mV")
print(f"Rev-C shared quiet/alarm shift:  {shared_ground_quiet * 1e3:.2f} / {shared_ground_alarm * 1e3:.2f} mV")

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
if failed:
    raise SystemExit("SPICE electrical acceptance failed: " + ", ".join(failed))

print("ALL SPICE ELECTRICAL ACCEPTANCE CHECKS PASSED")
