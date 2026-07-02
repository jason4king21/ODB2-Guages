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

    # ---- OBD via python-OBD Async ----
    # obd.Async runs a background thread that continuously polls the watched
    # commands and fires our callbacks with fresh values, so the Qt UI never
    # blocks on a serial round-trip. The callbacks run on that worker thread;
    # they only set QObject properties, whose notify signals Qt delivers to the
    # GUI thread via a queued connection (safe cross-thread).
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

    # --- Async callbacks (invoked on the OBD worker thread) ---
    def on_rpm(r):
        v = r.value
        rpmmeter.currRPM = float(v.magnitude) if v is not None else 0

    def on_speed(r):
        v = r.value
        speedometer.currSpeed = float(v.to("mph").magnitude) if v is not None else 0

    def on_temp(r):
        v = r.value
        temperature.currValue = round(float(v.to("degF").magnitude), 1) if v is not None else 0

    def on_status(r):
        v = r.value
        if v is not None:
            cel.mil = bool(v.MIL)
            cel.dtcCount = int(v.DTC_count)

    # Only the gauges actually shown in the QML are watched, so the background
    # loop cycles as fast as possible. If you restore a gauge to the UI, add its
    # command + callback here so it gets polled again.
    WATCHED = [
        (commands.RPM, on_rpm),
        (commands.SPEED, on_speed),
        (commands.COOLANT_TEMP, on_temp),
        (commands.STATUS, on_status),
    ]

    def start_async():
        """Build an Async connection; watch commands + start the loop if the car is up."""
        try:
            conn = obd.Async(portstr=obd_port, fast=False, timeout=2)
        except Exception as e:
            print("[WARN] Could not open Async OBD connection:", e)
            return None
        report_obd_status(conn)
        if conn.status() == OBDStatus.CAR_CONNECTED:
            try:
                py_obd.get_supported_pids_mode01(conn)
                py_obd.get_supported_pids_mode06(conn)
            except Exception as e:
                print("[WARN] PID discovery failed:", e)
            for cmd, cb in WATCHED:
                conn.watch(cmd, callback=cb)
            conn.start()
        return conn

    def stop_async(conn):
        if conn is None:
            return
        try:
            conn.stop()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    # Connect to OBD and start the background polling loop.
    connection = start_async()

    def tick():
        """Main-thread heartbeat: update the clock and manage (re)connection.
        Live gauge data is pushed by the Async callbacks, not from here."""
        global last_reconnect, connection

        centerScreen.update_now()

        # If not connected, show zeros and try to reconnect (rate-limited).
        if not obd_connected(connection):
            now = datetime.datetime.now().timestamp()
            if now - last_reconnect > 2.0:
                last_reconnect = now
                stop_async(connection)
                connection = start_async()
            set_disconnected_values()

    # Cleanly stop the worker thread when the app quits.
    app.aboutToQuit.connect(lambda: stop_async(connection))

    clock_timer = QTimer()
    clock_timer.timeout.connect(tick)
    clock_timer.start(250)

    sys.exit(app.exec_())
