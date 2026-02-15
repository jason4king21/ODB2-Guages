import os, sys, datetime, glob, time
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, Qt, pyqtProperty, QTimer, pyqtSlot
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQuick import QQuickView

import py_obd, obd
from obd import commands, OBDStatus

import serial, pynmea2
from serial.tools import list_ports


# ----------------------------
# Serial auto-detection helpers
# ----------------------------

def list_serial_candidates():
    """
    Return candidate serial device paths.
    Prefer /dev/serial/by-id/* (stable), then fall back to /dev/ttyUSB* and /dev/ttyACM*.
    Also includes symlinks from PySerial list_ports where applicable.
    """
    candidates = []

    # Stable by-id first
    candidates.extend(sorted(glob.glob("/dev/serial/by-id/*")))

    # Common kernel device names
    candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))
    candidates.extend(sorted(glob.glob("/dev/ttyACM*")))

    # Add anything else PySerial sees (can include symlinks/extra devices)
    try:
        for p in list_ports.comports(include_links=True):
            if p.device and p.device.startswith("/dev/"):
                candidates.append(p.device)
    except Exception:
        pass

    # De-dupe preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def looks_like_nmea_line(line: str) -> bool:
    # GNSS talkers often start with $GP, $GN, $GL, $GA, etc. NMEA typically contains a checksum '*'
    return line.startswith(("$GP", "$GN", "$GL", "$GA")) and "*" in line


def find_gps_port(baud_candidates=(9600, 115200), probe_seconds=1.5):
    """
    Try each candidate port + baud, read lines, and accept the first that produces parsable NMEA.
    Returns (port, baud) or (None, None).
    """
    for dev in list_serial_candidates():
        for baud in baud_candidates:
            try:
                with serial.Serial(dev, baudrate=baud, timeout=0.2) as s:
                    end = time.time() + probe_seconds
                    while time.time() < end:
                        raw = s.readline().decode("ascii", errors="ignore").strip()
                        if not raw:
                            continue
                        if looks_like_nmea_line(raw):
                            try:
                                # Validate by parsing; will throw on malformed sentences
                                pynmea2.parse(raw)
                                print(f"[INFO] GPS detected on {dev} @ {baud}")
                                return dev, baud
                            except Exception:
                                pass
            except Exception:
                pass

    return None, None


def find_obd_port(timeout=1.0):
    """
    Try python-OBD on each candidate serial port.
    Returns port string or None.
    """
    candidates = list_serial_candidates()

    # First pass: explicit probe
    for dev in candidates:
        try:
            conn = obd.OBD(portstr=dev, timeout=timeout, fast=False, check_voltage=False)

            if conn.status() in (OBDStatus.CAR_CONNECTED, OBDStatus.OBD_CONNECTED):
                # Verify with a lightweight query
                r = conn.query(commands.RPM)
                if not r.is_null():
                    print(f"[INFO] OBD detected on {dev}")
                    conn.close()
                    return dev

            conn.close()
        except Exception:
            pass

    # Fallback: let python-OBD autoscan (picks first connection it finds)
    try:
        conn = obd.OBD(timeout=timeout, fast=False, check_voltage=False)
        dev = conn.port_name() if hasattr(conn, "port_name") else None
        if dev:
            print(f"[INFO] OBD auto-scan selected {dev}")
        conn.close()
        return dev
    except Exception:
        return None


def get_serial_ports():
    """
    Decide QML path + auto-detect GPS and OBD ports.
    """
    is_pi = os.uname().machine.startswith(("arm", "aarch"))
    qml_file = "/home/kyle/ODB2-Guages/dashboard.qml" if is_pi else os.path.join(os.getcwd(), "dashboard.qml")

    gps_port, gps_baud = find_gps_port()
    obd_port = find_obd_port()

    print("[INFO] Detected Raspberry Pi:", is_pi)
    print("[INFO] GPS Port:", gps_port, "baud:", gps_baud)
    print("[INFO] OBD Port:", obd_port)
    print("[INFO] QML Path:", qml_file)

    if not gps_port:
        raise RuntimeError(
            "GPS adapter not found.\n"
            "Tip: run `ls -l /dev/serial/by-id/` and verify the GPS is present.\n"
            "Also verify baud rate (common: 9600 or 115200)."
        )

    if not obd_port:
        raise RuntimeError(
            "OBD adapter not found.\n"
            "Tip: make sure ignition is ON and run `ls -l /dev/serial/by-id/`.\n"
            "If using ELM327 USB, it should appear as ttyUSB* or in by-id."
        )

    return gps_port, gps_baud, obd_port, qml_file


# ----------------------------
# Helper Classes / Functions
# ----------------------------

def set_update_rate(port, rate_ms=100):
    # PMTK220 is common for MediaTek-based GPS units; harmless if unsupported (device may ignore).
    cmd = f"$PMTK220,{rate_ms}*"
    cs = 0
    for c in cmd[1:]:
        cs ^= ord(c)
    full = f"{cmd}{cs:02X}\r\n"
    with serial.Serial(port, 9600, timeout=1) as s:
        s.write(full.encode())


class CheckEngine(QObject):
    milChanged = pyqtSignal()
    dtcCountChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._mil = False
        self._dtc_count = 0

    @pyqtProperty(bool, notify=milChanged)
    def mil(self): return self._mil

    @mil.setter
    def mil(self, v): self._mil = v; self.milChanged.emit()

    @pyqtProperty(int, notify=dtcCountChanged)
    def dtcCount(self): return self._dtc_count

    @dtcCount.setter
    def dtcCount(self, v): self._dtc_count = v; self.dtcCountChanged.emit()


class GPSSpeedReader(QObject):
    speedUpdated = pyqtSignal(float)

    def __init__(self, port, baud=115200, parent=None):
        super().__init__(parent)
        self._ser = serial.Serial(port, baudrate=baud, timeout=1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_speed)
        self.timer.start(100)

    def read_speed(self):
        try:
            raw = self._ser.readline().decode('ascii', errors='ignore').strip()

            # Many modules output $GPRMC or $GNRMC (GN = multi-constellation)
            if raw.startswith(("$GPRMC", "$GNRMC")):
                msg = pynmea2.parse(raw)
                speed_knots = msg.spd_over_grnd or 0
                speed_mph = speed_knots * 1.15078
                self.speedUpdated.emit(round(speed_mph))
        except Exception:
            pass


class Speedometer(QObject):
    speedChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._minSpeed = 0.0
        self._maxSpeed = 160.0
        self._currSpeed = 0.0

    @pyqtProperty(float, notify=speedChanged)
    def currSpeed(self): return self._currSpeed
    @currSpeed.setter
    def currSpeed(self, v): self._currSpeed = v; self.speedChanged.emit()

    @pyqtSlot(float)
    def updateSpeed(self, v): self.currSpeed = v

    @pyqtProperty(float)
    def maxSpeed(self): return self._maxSpeed
    @pyqtProperty(float)
    def minSpeed(self): return self._minSpeed


class RPMMeter(QObject):
    RPMChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._minRPM = 0.0
        self._maxRPM = 10.0
        self._currRPM = 0.0

    @pyqtProperty(float, notify=RPMChanged)
    def currRPM(self): return self._currRPM
    @currRPM.setter
    def currRPM(self, v): self._currRPM = v; self.RPMChanged.emit()

    @pyqtProperty(float)
    def maxRPM(self): return self._maxRPM
    @pyqtProperty(float)
    def minRPM(self): return self._minRPM


class BarMeter(QObject):
    currValueChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._minValue = 0.0
        self._maxValue = 0.0
        self._currValue = 0.0

    @pyqtProperty(float, notify=currValueChanged)
    def currValue(self): return self._currValue
    @currValue.setter
    def currValue(self, v): self._currValue = v; self.currValueChanged.emit()

    @pyqtProperty(float)
    def maxValue(self): return self._maxValue
    @pyqtProperty(float)
    def minValue(self): return self._minValue


class StringLabel(QObject):
    currValueChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._currValue = ""

    @pyqtProperty(str, notify=currValueChanged)
    def currValue(self): return self._currValue
    @currValue.setter
    def currValue(self, v): self._currValue = v; self.currValueChanged.emit()


class CenterScreenWidget(QObject):
    currTimeChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._currTime = ""
        self._currDate = ""
        self.update_now()

    @pyqtProperty(str, notify=currTimeChanged)
    def currTime(self): return self._currTime
    @currTime.setter
    def currTime(self, v): self._currTime = v; self.currTimeChanged.emit()

    @pyqtProperty(str, notify=currTimeChanged)
    def currDate(self): return self._currDate
    @currDate.setter
    def currDate(self, v): self._currDate = v; self.currTimeChanged.emit()

    def update_now(self):
        now = datetime.datetime.now()
        self.currTime = now.strftime("%I:%M %p")
        self.currDate = now.strftime("%m/%d/%Y")


# ----------------------------
# Utility Functions
# ----------------------------

def make_connection(obd_port):
    conn = obd.OBD(portstr=obd_port, check_voltage=False)
    return conn, conn.status() == OBDStatus.CAR_CONNECTED


# ----------------------------
# Main Application
# ----------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = QQuickView()
    engine = view.engine()
    engine.addImportPath(os.path.join(os.getcwd(), "qml"))

    gps_port, gps_baud, obd_port, qml_file = get_serial_ports()

    # Optional: set GPS update rate (some devices ignore PMTK)
    try:
        set_update_rate(gps_port, 100)
    except Exception as e:
        print("[WARN] Could not set GPS update rate:", e)

    # Instantiate
    temperature = BarMeter()
    battery_capacity = BarMeter()
    speedometer = Speedometer()
    rpmmeter = RPMMeter()
    centerScreen = CenterScreenWidget()
    intakePressureLabel = BarMeter()
    intakeTempLabel = BarMeter()
    runtimeLabel = StringLabel()
    fuelLevelLabel = BarMeter()
    fuelTypeLabel = StringLabel()
    engineLoadLabel = BarMeter()
    throttlePosLabel = BarMeter()
    barometricPressureLabel = BarMeter()
    throttleAcceleratorLabel = BarMeter()
    absoluteLoadLabel = BarMeter()
    cel = CheckEngine()
    gps = GPSSpeedReader(gps_port, baud=gps_baud)
    oilPressureLabel = BarMeter()

    # Expose to QML
    ctx = engine.rootContext()
    ctx.setContextProperty("speedometer", speedometer)
    ctx.setContextProperty("RPM_Meter", rpmmeter)
    ctx.setContextProperty("temperature", temperature)
    ctx.setContextProperty("battery_capacity", battery_capacity)
    ctx.setContextProperty("intakePressureLabel", intakePressureLabel)
    ctx.setContextProperty("intakeTempLabel", intakeTempLabel)
    ctx.setContextProperty("runtimeLabel", runtimeLabel)
    ctx.setContextProperty("fuelLevelLabel", fuelLevelLabel)
    ctx.setContextProperty("fuelTypeLabel", fuelTypeLabel)
    ctx.setContextProperty("engineLoadLabel", engineLoadLabel)
    ctx.setContextProperty("throttlePosLabel", throttlePosLabel)
    ctx.setContextProperty("barometricPressureLabel", barometricPressureLabel)
    ctx.setContextProperty("throttleAcceleratorLabel", throttleAcceleratorLabel)
    ctx.setContextProperty("absoluteLoadLabel", absoluteLoadLabel)
    ctx.setContextProperty("centerScreen", centerScreen)
    ctx.setContextProperty("checkEngine", cel)
    ctx.setContextProperty("oilPressureLabel", oilPressureLabel)

    view.setSource(QUrl.fromLocalFile(qml_file))
    view.show()

    # Wire GPS -> Speedometer (DO THIS ONCE, not every timer tick)
    gps.speedUpdated.connect(speedometer.updateSpeed)

    # Connect to OBD
    connection, car_ready = make_connection(obd_port)
    print("Car connected:", car_ready)

    if car_ready:
        py_obd.get_supported_pids_mode01(connection)
        py_obd.get_supported_pids_mode06(connection)

    def update_all():
        centerScreen.update_now()

        # If car state might change, you can re-check status occasionally:
        # (optional) car_ready = connection.status() == OBDStatus.CAR_CONNECTED

        if car_ready:
            resp = connection.query(commands.STATUS)
            if not resp.is_null() and resp.value is not None:
                cel.mil = bool(resp.value.MIL)
                cel.dtcCount = int(resp.value.DTC_count)

            rpmmeter.currRPM = (py_obd.get_rpm(connection) or 0) / 1000
            temperature.currValue = py_obd.get_temperature(connection) or 0
            battery_capacity.currValue = py_obd.get_battery(connection) or 0
            engineLoadLabel.currValue = py_obd.get_engine_load(connection) or 0
            throttlePosLabel.currValue = py_obd.get_throttle_pos(connection) or 0
            barometricPressureLabel.currValue = py_obd.get_intake_pressure(connection) or 0
            intakeTempLabel.currValue = py_obd.get_intake_temp(connection) or 0
            absoluteLoadLabel.currValue = py_obd.get_absolute_load(connection) or 0
            oilPressureLabel.currValue = py_obd.get_oil_pressure(connection) or 0
        else:
            # Reset values if disconnected
            rpmmeter.currRPM = 0
            temperature.currValue = 0
            battery_capacity.currValue = 0
            engineLoadLabel.currValue = 0
            throttlePosLabel.currValue = 0
            barometricPressureLabel.currValue = 0
            intakeTempLabel.currValue = 0
            absoluteLoadLabel.currValue = 0
            cel.mil = True
            cel.dtcCount = 10
            oilPressureLabel.currValue = 0

    poll_timer = QTimer()
    poll_timer.timeout.connect(update_all)
    poll_timer.start(100)

    sys.exit(app.exec_())
