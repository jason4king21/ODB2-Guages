"""
py_obd.py - Helper functions for python-OBD dashboards

Key fixes vs prior version:
- Removed accidental second definition of query_match_pids() that overwrote the real one.
- Safer query helpers (handle None responses).
- Defaults return 0 / empty values (better for a dash vs "44").
- Battery now reports CONTROL_MODULE_VOLTAGE (if supported); fuel level is its own function.
- Logging goes to /tmp/output.txt to reduce SD wear on Raspberry Pi.
"""

from obd import OBDCommand
from obd.utils import bytes_to_int
from obd.protocols import ECU
import obd
from typing import Any, Optional

LOG_PATH = "/tmp/output.txt"


def _log(msg: str) -> None:
    try:
        with open(LOG_PATH, "a") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        # Never let logging crash the dash
        pass


def query_match_pids(connection: obd.OBD, pidlist: list[str], command: obd.OBDCommand) -> str:
    """
    Query bitfield PIDs (e.g., PIDS_A/B/C or MIDS_A/B/...) and log supported items.
    Returns a string of 0/1 bits, or "" on failure.
    """
    try:
        resp = connection.query(command)
        response = resp.value
        if response is None:
            _log(f"[WARN] Supported PID query returned None for {command}")
            return ""

        bit_string = "".join("1" if bit else "0" for bit in response)

        _log(f"Command: {command}")
        _log(f"Length of bit response: {len(response)}")
        _log(f"Length of name list: {len(pidlist)}")
        _log(f"Supported bits: {bit_string}")

        for index, bit in enumerate(response):
            if bit:
                pid_index = index + 1  # 1-based
                if 1 <= pid_index <= len(pidlist):
                    pid_name = pidlist[pid_index - 1]
                    _log(f"  {command} bit {pid_index:02X}: {pid_name}")

        return bit_string
    except Exception as e:
        _log(f"[ERROR] Error receiving supported PIDs for {command}: {e}")
        return ""


def _value_or_default(resp: Any, default: Any) -> Any:
    if resp is None:
        return default
    try:
        v = resp.value
        if v is None:
            return default
        # Pint Quantity or python-OBD objects often have .magnitude
        if hasattr(v, "magnitude"):
            return v.magnitude
        return v
    except Exception:
        return default


def query_obd(connection: obd.OBD, command: obd.OBDCommand, default_value: float, error_message: str) -> float:
    """Query an OBD command and return a numeric magnitude; default on errors."""
    try:
        resp = connection.query(command)
        return float(_value_or_default(resp, default_value))
    except Exception as e:
        _log(f"[ERROR] {error_message}: {e}")
        return float(default_value)


def query_speed_mph(connection: obd.OBD, command: obd.OBDCommand, default_value: float, error_message: str) -> float:
    """Query a speed command and return mph; default on errors."""
    try:
        resp = connection.query(command)
        if resp.value is None:
            return float(default_value)
        return float(resp.value.to("mph").magnitude)
    except Exception as e:
        _log(f"[ERROR] {error_message}: {e}")
        return float(default_value)


def get_supported_pids_mode01(connection: obd.OBD) -> None:
    cmd1 = obd.commands.PIDS_A
    cmd2 = obd.commands.PIDS_B
    cmd3 = obd.commands.PIDS_C

    pid_list1 = [
        "STATUS", "FREEZE_DTC", "FUEL_STATUS", "ENGINE_LOAD", "COOLANT_TEMP",
        "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "SHORT_FUEL_TRIM_2", "LONG_FUEL_TRIM_2",
        "FUEL_PRESSURE", "INTAKE_PRESSURE", "RPM", "SPEED", "TIMING_ADVANCE",
        "INTAKE_TEMP", "MAF", "THROTTLE_POS", "AIR_STATUS", "O2_SENSORS", "O2_B1S1",
        "O2_B1S2", "O2_B1S3", "O2_B1S4", "O2_B2S1", "O2_B2S2", "O2_B2S3", "O2_B2S4",
        "OBD_COMPLIANCE", "O2_SENSORS_ALT", "AUX_INPUT_STATUS", "RUN_TIME", "PIDS_B"
    ]

    pid_list2 = [
        "DISTANCE_W_MIL", "FUEL_RAIL_PRESSURE_VAC", "FUEL_RAIL_PRESSURE_DIRECT",
        "O2_S1_WR_VOLTAGE", "O2_S2_WR_VOLTAGE", "O2_S3_WR_VOLTAGE", "O2_S4_WR_VOLTAGE",
        "O2_S5_WR_VOLTAGE", "O2_S6_WR_VOLTAGE", "O2_S7_WR_VOLTAGE", "O2_S8_WR_VOLTAGE",
        "COMMANDED_EGR", "EGR_ERROR", "EVAPORATIVE_PURGE", "FUEL_LEVEL", "WARMUPS_SINCE_DTC_CLEAR",
        "DISTANCE_SINCE_DTC_CLEAR", "EVAP_VAPOR_PRESSURE", "BAROMETRIC_PRESSURE",
        "O2_S1_WR_CURRENT", "O2_S2_WR_CURRENT", "O2_S3_WR_CURRENT", "O2_S4_WR_CURRENT",
        "O2_S5_WR_CURRENT", "O2_S6_WR_CURRENT", "O2_S7_WR_CURRENT", "O2_S8_WR_CURRENT",
        "CATALYST_TEMP_B1S1", "CATALYST_TEMP_B2S1", "CATALYST_TEMP_B1S2", "CATALYST_TEMP_B2S2",
        "PIDS_C"
    ]

    pid_list3 = [
        "STATUS_DRIVE_CYCLE", "CONTROL_MODULE_VOLTAGE", "ABSOLUTE_LOAD", "COMMANDED_EQUIV_RATIO",
        "RELATIVE_THROTTLE_POS", "AMBIENT_AIR_TEMP", "THROTTLE_POS_B", "THROTTLE_POS_C",
        "ACCELERATOR_POS_D", "ACCELERATOR_POS_E", "ACCELERATOR_POS_F", "THROTTLE_ACTUATOR",
        "RUN_TIME_MIL", "TIME_SINCE_DTC_CLEARED", "unsupported", "MAX_MAF", "FUEL_TYPE",
        "ETHANOL_PERCENT", "EVAP_VAPOR_PRESSURE_ABS", "EVAP_VAPOR_PRESSURE_ALT",
        "SHORT_O2_TRIM_B1", "LONG_O2_TRIM_B1", "SHORT_O2_TRIM_B2", "LONG_O2_TRIM_B2",
        "FUEL_RAIL_PRESSURE_ABS", "RELATIVE_ACCEL_POS", "HYBRID_BATTERY_REMAINING",
        "OIL_TEMP", "FUEL_INJECT_TIMING", "FUEL_RATE"
    ]

    query_match_pids(connection, pid_list1, cmd1)
    query_match_pids(connection, pid_list2, cmd2)
    query_match_pids(connection, pid_list3, cmd3)


def get_supported_pids_mode06(connection: obd.OBD) -> None:
    commands_and_mids = {
        "MIDS_A": {
            "cmd": obd.commands.MIDS_A,
            "mids": [
                "MONITOR_O2_B1S1", "MONITOR_O2_B1S2", "MONITOR_O2_B1S3", "MONITOR_O2_B1S4",
                "MONITOR_O2_B2S1", "MONITOR_O2_B2S2", "MONITOR_O2_B2S3", "MONITOR_O2_B2S4",
                "MONITOR_O2_B3S1", "MONITOR_O2_B3S2", "MONITOR_O2_B3S3", "MONITOR_O2_B3S4",
                "MONITOR_O2_B4S1", "MONITOR_O2_B4S2", "MONITOR_O2_B4S3", "MONITOR_O2_B4S4",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "MIDS_B"
            ],
        },
        "MIDS_B": {
            "cmd": obd.commands.MIDS_B,
            "mids": [
                "MONITOR_CATALYST_B1", "MONITOR_CATALYST_B2", "MONITOR_CATALYST_B3",
                "MONITOR_CATALYST_B4", "unsupported", "unsupported",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "unsupported", "unsupported", "unsupported", "unsupported",
                "MONITOR_EGR_B1", "MONITOR_EGR_B2", "MONITOR_EGR_B3", "MONITOR_EGR_B4",
                "MONITOR_VVT_B1", "MONITOR_VVT_B2", "MONITOR_VVT_B3", "MONITOR_VVT_B4",
                "MONITOR_EVAP_150", "MONITOR_EVAP_090", "MONITOR_EVAP_040",
                "MONITOR_EVAP_020", "MONITOR_PURGE_FLOW", "unsupported",
                "unsupported", "MIDS_C"
            ],
        },
        "MIDS_C": {"cmd": obd.commands.MIDS_C, "mids": ["MIDS_D"]},  # keep short; still logs bits
        "MIDS_D": {"cmd": obd.commands.MIDS_D, "mids": ["MIDS_E"]},
        "MIDS_E": {"cmd": obd.commands.MIDS_E, "mids": ["MIDS_F"]},
        "MIDS_F": {"cmd": obd.commands.MIDS_F, "mids": ["MIDS_G"]},
    }

    for value in commands_and_mids.values():
        query_match_pids(connection, value["mids"], value["cmd"])


# ---- Individual getters used by dashboard ----

def get_speed(connection: obd.OBD) -> float:
    return query_speed_mph(connection, obd.commands.SPEED, 0.0, "Error receiving speed")


def get_rpm(connection: obd.OBD) -> float:
    # Returns RPM (dashboard divides by 1000 to display "x1000")
    return query_obd(connection, obd.commands.RPM, 0.0, "Error receiving RPM")


def get_temperature(connection: obd.OBD) -> float:
    # python-OBD returns coolant temp in °C; convert to °F for the dash
    try:
        r = connection.query(obd.commands.COOLANT_TEMP)
        if r is None or r.value is None:
            return 0.0
        # Pint Quantity supports .to("degF")
        return float(r.value.to("degF").magnitude).__round__(1)
    except Exception:
        return 0.0


def get_fuel_level(connection: obd.OBD) -> float:
    # 0-100 (%)
    return round(query_obd(connection, obd.commands.FUEL_LEVEL, 0.0, "Error receiving fuel level"), 0)


def get_battery_voltage(connection: obd.OBD) -> float:
    # Typical running 13.5-14.6V, key-on ~12.0-12.8V
    return round(query_obd(connection, obd.commands.CONTROL_MODULE_VOLTAGE, 0.0, "Error receiving module voltage"), 1)


# Backwards-compatible name used by your dashboard originally
def get_battery(connection: obd.OBD) -> float:
    return get_battery_voltage(connection)


def get_intake_pressure(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.INTAKE_PRESSURE, 0.0, "Error receiving intake pressure")


def get_intake_temp(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.INTAKE_TEMP, 0.0, "Error receiving intake temperature")


def get_runtime(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.RUN_TIME, 0.0, "Error receiving engine runtime")


def get_throttle_pos(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.THROTTLE_POS, 0.0, "Error receiving throttle position")


def get_absolute_load(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.ABSOLUTE_LOAD, 0.0, "Error receiving absolute load")


def get_engine_load(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.ENGINE_LOAD, 0.0, "Error receiving engine load")


def get_barometric_pressure(connection: obd.OBD) -> float:
    return query_obd(connection, obd.commands.BAROMETRIC_PRESSURE, 0.0, "Error receiving barometric pressure")


def get_accelerator_pos(connection: obd.OBD) -> float:
    # Use one of the accelerator position PIDs if supported; fall back to 0
    return query_obd(connection, obd.commands.ACCELERATOR_POS_D, 0.0, "Error receiving accelerator position")


def get_fuel_type(connection: obd.OBD) -> str:
    try:
        resp = connection.query(obd.commands.FUEL_TYPE)
        if resp.value is None:
            return ""
        return str(resp.value)
    except Exception as e:
        _log(f"[ERROR] Error receiving fuel type: {e}")
        return ""


def _decode_gm_oil_pressure(messages):
    """
    Decode GM enhanced PID 22115C response.

    Typical response payload:
      62 11 5C A
    where A is the value byte.

    Formula widely reported for 2005 GM trucks:
      psi = (A * 0.65) - 17.5
    """
    if not messages:
        return None
    try:
        data = messages[0].data  # bytearray
        # Look for: 62 11 5C A
        if len(data) >= 4 and data[0] == 0x62 and data[1] == 0x11 and data[2] == 0x5C:
            A = data[3]
        else:
            # Fallback: last byte as A
            A = data[-1]

        psi = (A * 0.65) - 17.5
        if psi < 0:
            psi = 0.0
        return float(psi)
    except Exception:
        return None

# Define the custom command once
GM_OIL_PRESSURE = OBDCommand(
    "GM_OIL_PRESSURE",
    "GM Enhanced Oil Pressure (psi) via Mode 22 PID 115C",
    "22115C",
    4,                       # bytes_returned (positional)
    _decode_gm_oil_pressure,
    ecu=ECU.ENGINE,
    fast=False
)

def get_oil_pressure(connection):
    """
    Returns oil pressure in PSI using GM enhanced Mode 22 PID 22115C.
    """
    try:
        r = connection.query(GM_OIL_PRESSURE)
        if r is None or r.value is None:
            return 0.0
        return float(r.value)
    except Exception:
        return 0.0
