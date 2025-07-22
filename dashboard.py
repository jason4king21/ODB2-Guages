import os, sys, datetime
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, Qt, pyqtProperty, QThread, QTimer, pyqtSlot
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQuick import QQuickView
import py_obd, obd
from obd import commands, OBDStatus
import serial, pynmea2

# — Helper Classes —

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

    def __init__(self, port="COM5", baud=9600, parent=None):
        super().__init__(parent)
        self.port = serial.Serial(port, baudrate=baud, timeout=1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_speed)
        self.timer.start(1000)

    def read_speed(self):
        try:
            raw = self.port.readline().decode('ascii', errors='ignore').strip()
            if raw.startswith('$GPRMC'):
                msg = pynmea2.parse(raw)
                knots = msg.spd_over_grnd
                speed = float(knots) * 1.15078 if knots else 0.0
                self.speedUpdated.emit(speed)
        except:
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


# — Utility Functions —

def make_connection():
    conn = obd.OBD(portstr="COM4", check_voltage=False)
    return conn, conn.status() == OBDStatus.CAR_CONNECTED


# — Main Application —

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = QQuickView()
    engine = view.engine()
    engine.addImportPath(os.path.join(os.getcwd(), "qml"))

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
    gps = GPSSpeedReader("COM5")

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

    view.setSource(QUrl('dashboard.qml'))
    view.show()

    # Connect to OBD
    connection, car_ready = make_connection()
    print("Car connected:", car_ready)
    py_obd.get_supported_pids_mode01(connection)
    py_obd.get_supported_pids_mode06(connection)

    # Wire GPS -> Speedometer
    gps.speedUpdated.connect(speedometer.updateSpeed)

    def update_all():
        centerScreen.update_now()

        if car_ready:
            resp = connection.query(commands.STATUS)
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
            cel.mil = False
            cel.dtcCount = 0

    poll_timer = QTimer()
    poll_timer.timeout.connect(update_all)
    poll_timer.start(200)

    sys.exit(app.exec_())