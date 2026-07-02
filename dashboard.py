import os, sys, datetime, logging
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, Qt, pyqtProperty, QTimer, pyqtSlot
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQuick import QQuickView
import py_obd, obd
from obd import commands, OBDStatus
import serial, pynmea2

# python-OBD logs a "could not open port" ERROR on every reconnect attempt.
# We surface connection state ourselves via report_obd_status(), so silence the
# library's per-retry spam (CRITICAL) to keep a hardware-less dev run readable.
logging.getLogger("obd").setLevel(logging.CRITICAL)

connection = None
last_reconnect = 0.0
_last_obd_status = None  # only print OBD status when it changes

def get_serial_ports():
    # os.uname() only exists on POSIX; guard so this runs on Windows too.
    is_pi = False
    if hasattr(os, "uname"):
        machine = os.uname().machine
        is_pi = machine.startswith("arm") or machine.startswith("aarch")

    # Ports/paths can be overridden via environment variables so the same
    # code runs on the Pi (defaults) or on a dev machine with no hardware.
    gps_port = os.environ.get("GPS_PORT", "/dev/ttyACM0")
    obd_port = os.environ.get("OBD_PORT", "/dev/rfcomm0")

    # QML lives alongside this script; don't hardcode a user's home dir.
    default_qml = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.qml")
    qml_file = os.environ.get("DASH_QML", default_qml)

    print("[INFO] Detected Raspberry Pi:", is_pi)
    print("[INFO] GPS Port:", gps_port)
    print("[INFO] OBD Port:", obd_port)
    print("[INFO] QML Path:", qml_file)
    return gps_port, obd_port, qml_file


# — Helper Classes —

def set_update_rate(port="/dev/ttyACM0", rate_ms=100):
    cmd = f"$PMTK220,{rate_ms}*"
    cs = 0
    for c in cmd[1:]:
        cs ^= ord(c)
    full = f"{cmd}{cs:02X}\r\n"
    try:
        with serial.Serial(port, 9600, timeout=1) as s:
            s.write(full.encode())
    except Exception as e:
        # No GPS attached (e.g. dev machine) — skip rather than crash.
        print(f"[WARN] Could not set GPS update rate on {port}: {e}")


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

    def __init__(self, port="/dev/ttyACM0", baud=115200, parent=None):
        super().__init__(parent)
        try:
            self.port = serial.Serial(port, baudrate=baud, timeout=1)
        except Exception as e:
            # No GPS attached — run without live speed instead of crashing.
            print(f"[WARN] GPS serial port {port} unavailable: {e}")
            self.port = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_speed)
        self.timer.start(100)

    def read_speed(self):
        if self.port is None:
            return
        try:
            raw = self.port.readline().decode('ascii', errors='ignore').strip()
            if raw.startswith('$GPRMC'):
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
        self._maxRPM = 10000.0   # true RPM (gauge sweeps 0..10000)
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


# — Utility Functions —

def make_connection(port: str):
    # VPW/Class2 tends to be more reliable with fast=False and a slightly longer timeout.
    # Returns None when the adapter/port isn't present (e.g. dev machine).
    try:
        return obd.OBD(portstr=port, fast=False, timeout=2)
    except Exception as e:
        print(f"[WARN] Could not open OBD connection on {port}: {e}")
        return None


def obd_connected(conn) -> bool:
    return conn is not None and conn.status() == OBDStatus.CAR_CONNECTED


def report_obd_status(conn) -> None:
    # Print only on change so a disconnected dev run doesn't spam every 2s.
    global _last_obd_status
    status = conn.status() if conn else "No connection"
    if status != _last_obd_status:
        print("OBD status:", status)
        _last_obd_status = status


# — Main Application —

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = QQuickView()
    engine = view.engine()
    engine.addImportPath(os.path.join(os.getcwd(), "qml"))

    gps_port, obd_port, qml_file = get_serial_ports()

    # Instantiate
    temperature = BarMeter()
    battery_capacity = BarMeter()       # now shows module voltage (V)
    speedometer = Speedometer()
    rpmmeter = RPMMeter()
    centerScreen = CenterScreenWidget()
    intakePressureLabel = BarMeter()
    intakeTempLabel = BarMeter()
    runtimeLabel = StringLabel()
    fuelLevelLabel = BarMeter()         # now updated (%)
    fuelTypeLabel = StringLabel()
    engineLoadLabel = BarMeter()
    throttlePosLabel = BarMeter()
    barometricPressureLabel = BarMeter()
    throttleAcceleratorLabel = BarMeter()
    absoluteLoadLabel = BarMeter()
    cel = CheckEngine()
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

    # Connect to OBD
    connection = make_connection(obd_port)
    report_obd_status(connection)

    # Only attempt PID discovery if connected (and never let it crash the UI)
    if obd_connected(connection):
        try:
            py_obd.get_supported_pids_mode01(connection)
            py_obd.get_supported_pids_mode06(connection)
        except Exception as e:
            print("[WARN] PID discovery failed:", e)

    last_reconnect = 0.0

    def set_disconnected_values():
        speedometer.currSpeed = 0
        rpmmeter.currRPM = 0
        temperature.currValue = 0
        battery_capacity.currValue = 0
        engineLoadLabel.currValue = 0
        throttlePosLabel.currValue = 0
        barometricPressureLabel.currValue = 0
        intakeTempLabel.currValue = 0
        intakePressureLabel.currValue = 0
        absoluteLoadLabel.currValue = 0
        fuelLevelLabel.currValue = 0
        oilPressureLabel.currValue = 0
        # Show "disconnected" by turning MIL on (optional)
        cel.mil = True
        cel.dtcCount = 0

    def _update_status():
        resp = connection.query(commands.STATUS)
        if resp and resp.value:
            cel.mil = bool(resp.value.MIL)
            cel.dtcCount = int(resp.value.DTC_count)

    # Slow-changing readouts: one is refreshed per tick (round-robin) so the
    # primary gauges (speed & RPM) aren't stuck waiting on ~13 serial
    # round-trips every cycle. Each entry is (target_obj, attr, getter).
    slow_updates = [
        (None, None, _update_status),   # MIL / DTC count
        (temperature, "currValue", py_obd.get_temperature),
        (battery_capacity, "currValue", py_obd.get_battery_voltage),
        (engineLoadLabel, "currValue", py_obd.get_engine_load),
        (throttlePosLabel, "currValue", py_obd.get_throttle_pos),
        (barometricPressureLabel, "currValue", py_obd.get_barometric_pressure),
        (intakePressureLabel, "currValue", py_obd.get_intake_pressure),
        (intakeTempLabel, "currValue", py_obd.get_intake_temp),
        (absoluteLoadLabel, "currValue", py_obd.get_absolute_load),
        (fuelLevelLabel, "currValue", py_obd.get_fuel_level),
        (oilPressureLabel, "currValue", py_obd.get_oil_pressure),
    ]
    slow_index = 0

    def update_all():
        global last_reconnect, connection, slow_index

        centerScreen.update_now()

        # If not connected, try to reconnect (rate-limited)
        if not obd_connected(connection):
            now = datetime.datetime.now().timestamp()
            if now - last_reconnect > 2.0:
                last_reconnect = now
                try:
                    if connection:
                        connection.close()
                except Exception:
                    pass
                connection = make_connection(obd_port)
                report_obd_status(connection)

            set_disconnected_values()
            return

        # Fast path: refresh the two primary gauges every tick.
        # True RPM straight from the ECU (no scaling).
        rpmmeter.currRPM = py_obd.get_rpm(connection) or 0
        # Vehicle speed (mph) from the PCM instead of GPS.
        speedometer.currSpeed = py_obd.get_speed(connection) or 0

        # Slow path: refresh exactly one secondary readout this tick.
        obj, attr, getter = slow_updates[slow_index]
        if obj is None:
            getter()
        else:
            setattr(obj, attr, getter(connection) or 0)
        slow_index = (slow_index + 1) % len(slow_updates)

    poll_timer = QTimer()
    poll_timer.timeout.connect(update_all)
    # 50 ms floor; on real hardware the OBD round-trips govern the actual rate,
    # this just removes idle gap between cycles so gauges refresh as fast as the bus allows.
    poll_timer.start(50)

    sys.exit(app.exec_())
