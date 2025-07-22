import os, sys
import time
import random
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, Qt, pyqtProperty, QThread, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType
from PyQt5 import QtCore, QtGui
from PyQt5.QtQuick import QQuickView
import datetime
import time
import py_obd
import obd
from obd import commands, OBDStatus, OBD
import serial, pynmea2


def make_connection():
    connection = obd.OBD(portstr="COM4", check_voltage=False)
    return connection, connection.status() == OBDStatus.CAR_CONNECTED


class CheckEngine(QObject):
    milChanged = pyqtSignal()
    dtcCountChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._mil = False
        self._dtc_count = 0

    @pyqtProperty(bool, notify=milChanged)
    def mil(self):
        return self._mil

    @mil.setter
    def mil(self, value):
        self._mil = value
        self.milChanged.emit()

    @pyqtProperty(int, notify=dtcCountChanged)
    def dtcCount(self):
        return self._dtc_count

    @dtcCount.setter
    def dtcCount(self, value):
        self._dtc_count = value
        self.dtcCountChanged.emit()

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
                try:
                    msg = pynmea2.parse(raw)
                    knots = msg.spd_over_grnd
                    speed = float(knots)*1.15078 if knots is not None else 0.0
                except:
                    speed = 0.0
                self.speedUpdated.emit(speed)
            else:
                # No RMC line—emit 0 to reset stale data
                self.speedUpdated.emit(0.0)
        except (pynmea2.ParseError, serial.SerialException):
            pass
        self.speedUpdated.emit(0.0)
    
    def check_stale(self):
        if time.time() - self.last_emit > 5:
            self.speedUpdated.emit(0.0)

class Speedometer(QObject):
    speedChanged = QtCore.pyqtSignal()  # This actually doesn't do anything since qml doesn't have a function. But just keep it in case.

    def __init__(self, parent=None):
        super(Speedometer, self).__init__(parent)
        self._maxSpeed = 160.0
        self._minSpeed = 0.0
        self._currSpeed = 0.0

    @pyqtProperty(float, notify=speedChanged)
    def currSpeed(self):
        return self._currSpeed

    @currSpeed.setter
    def currSpeed(self, value):
        self._currSpeed = value
        self.speedChanged.emit()

    @QtCore.pyqtSlot(float)
    def updateSpeed(self, value):
        self.currSpeed = value

    @pyqtProperty(float)
    def maxSpeed(self):
        return self._maxSpeed

    @pyqtProperty(float)
    def minSpeed(self):
        return self._minSpeed

    @QtCore.pyqtSlot(float, float, float)
    def setAllValues(self, currSpeed, maxSpeed, minSpeed):
        self._currSpeed = currSpeed
        self._maxSpeed = maxSpeed
        self._minSpeed = minSpeed
        self.speedChanged.emit()


class RPM_meter(QObject):
    RPMChanged = QtCore.pyqtSignal()  # This actually doesn't do anything since qml doesn't have a function. But just keep it in case.

    def __init__(self, parent=None):
        super(RPM_meter, self).__init__(parent)
        self._maxRPM = 10.0
        self._minRPM = 0.0
        self._currRPM = 0.0

    @pyqtProperty(float, notify=RPMChanged)
    def currRPM(self):
        return self._currRPM

    @currRPM.setter
    def currRPM(self, value):
        self._currRPM = value
        self.RPMChanged.emit()

    @pyqtProperty(float)
    def maxRPM(self):
        return self._maxRPM

    @pyqtProperty(float)
    def minRPM(self):
        return self._minRPM

    @QtCore.pyqtSlot(float, float, float)
    def setAllValues(self, currRPM, maxRPM, minRPM):
        self._currRPM = currRPM
        self._maxRPM = maxRPM
        self._minRPM = minRPM
        self.RPMChanged.emit()


class BarMeter(QObject):
    currValueChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(BarMeter, self).__init__(parent)
        self._currValue = 0.0
        self._maxSpeed = 0.0
        self._minSpeed = 0.0

    @pyqtProperty(float, notify=currValueChanged)
    def currValue(self):
        return self._currValue

    @currValue.setter
    def currValue(self, value):
        self._currValue = value
        self.currValueChanged.emit()

    @pyqtProperty(float)
    def maxValue(self):
        return self._maxSpeed

    @pyqtProperty(float)
    def minValue(self):
        return self._minSpeed

    def setCurrValue(self, value):
        self._currValue = value
        self.currValueChanged.emit()

    @QtCore.pyqtSlot(float, float, float)
    def setAllValues(self, currValue, maxValue, minValue):
        self._currValue = currValue
        self._maxSpeed = maxValue
        self._minSpeed = minValue
        self.currValueChanged.emit()


class Labels(QObject):
    currValueChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(Labels, self).__init__(parent)
        self._currValue = 0.0

    @pyqtProperty(float, notify=currValueChanged)
    def currValue(self):
        return self._currValue

    @currValue.setter
    def currValue(self, value):
        self._currValue = value
        self.currValueChanged.emit()

    @QtCore.pyqtSlot(float, float, float)
    def setAllValues(self, currValue):
        self._currValue = currValue
        self.currValueChanged.emit()

class stringLabels(QObject):
    currValueChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._currValue = "Name"

    @pyqtProperty(str, notify=currValueChanged)
    def currValue(self):
        return self._currValue

    @currValue.setter
    def currValue(self, str):
        self._currValue = str
        self.currValueChanged.emit()


class CenterScreenWidget(QObject):
    currTimeChanged = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super(CenterScreenWidget, self).__init__(parent)
        self._currTime = datetime.datetime.now().strftime("%I:%M %p")
        self._currDate = datetime.datetime.now().strftime("%m/%d/%Y")

    @pyqtProperty(str, notify=currTimeChanged)
    def currTime(self):
        return self._currTime

    @currTime.setter
    def currTime(self, value):
        self._currTime = value
        self.currTimeChanged.emit()

    @pyqtProperty(str, notify=currTimeChanged)
    def currDate(self):
        return self._currDate

    @currDate.setter
    def currDate(self, value):
        self._currDate = value
        self.currTimeChanged.emit()

def change_val():
    random_float = random.uniform(0, 160)
    random_rpm = random.uniform(0, 10)
    random_int = random.randint(0, 300)

    random_battery = random.randint(0, 100)
    temperature.currValue = random_int
    speedometer.currSpeed = random_float
    battery_capacity.currValue = random_battery
    rpmmeter.currRPM = random_rpm

    centerScreen.currTime = datetime.datetime.now().strftime("%I:%M %p")
    centerScreen.currDate = datetime.datetime.now().strftime("%m/%d/%Y")

class ZeroToSixtyTimer(QtCore.QObject):
    # Signal to notify QML when the timing is complete
    timer_finished = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.start_time = None
        self.is_timing = False

    def start_timer(self):
        """Start the timer only if it's not already running."""
        if not self.is_timing:
            self.start_time = time.time()
            self.is_timing = True

    def stop_timer(self):
        """Stop the timer and emit the finished signal."""
        if self.is_timing:
            elapsed_time = time.time() - self.start_time
            self.is_timing = False
            self.timer_finished.emit(f"{elapsed_time:.2f} seconds")
    
    def cancel_timer(self):
        """Cancel the timer."""
        self.is_timing = False

    def to60(self, currSpeed_func):
        """Start timing when car starts moving, stop when it reaches or exceeds 60 mph."""
        self.start_timer()

        while self.is_timing:
            curr_speed = currSpeed_func()  # Get the current speed
            
            # Start timing when speed transitions from 0 to above 0
            if curr_speed > 0 and self.start_time is None:
                self.start_timer()
            
            # Stop timing when speed reaches or exceeds 60 mph
            if curr_speed >= 60:
                self.stop_timer()
                break
            
            # Sleep briefly to simulate real-time checking
            time.sleep(0.1)

def start_zero_to_sixty():
    timer.to60(speedometer.currSpeed)

def on_timer_finished(time):
    print(f"0-60 Time: {time}")  # Log the time in the console

def receiver(connection, speedometer, temperature, battery_capacity, rpmmeter):

    # Get data from OBD
    speed = py_obd.get_speed(connection)
    rpm = py_obd.get_rpm(connection)
    temp = py_obd.get_temperature(connection)
    battery_level = py_obd.get_battery(connection)

    # Update PyQT Objects with data
    speedometer.currSpeed = speed
    rpmmeter.currRPM = rpm
    temperature.currValue = temp
    battery_capacity.currValue = battery_level

    centerScreen.currTime = datetime.datetime.now().strftime("%I:%M %p")
    centerScreen.currDate = datetime.datetime.now().strftime("%m/%d/%Y")

def poll_speed(connection):
    # speed = py_obd.get_speed(connection)
    # speedometer.currSpeed = speed
    # Setup GPS reader
    gps = GPSSpeedReader("COM5")
    gps.speedUpdated.connect(speedometer.updateSpeed)

def poll_rpm(connection):
    rpm = py_obd.get_rpm(connection)
    rpmmeter.currRPM = rpm / 1000

def poll_coolantTemp(connection):
    temp = py_obd.get_temperature(connection)
    temperature.currValue = temp

def poll_fuel(connection):
    fuel = py_obd.get_battery(connection)
    battery_capacity.currValue = fuel
    fuelLevelLabel.currValue = fuel

def poll_time():
    centerScreen.currTime = datetime.datetime.now().strftime("%I:%M %p")
    centerScreen.currDate = datetime.datetime.now().strftime("%m/%d/%Y")

def poll_intake_pressure(connection):
    pressure = py_obd.get_intake_pressure(connection)
    intakePressureLabel.currValue = pressure

def poll_intake_temp(connection):
    temp = py_obd.get_intake_temp(connection)
    intakeTempLabel.currValue = temp

def poll_runtime(connection):
    runtime = py_obd.get_runtime(connection)
    # Convert to HH:MM:SS
    # Calculate hours, minutes, and seconds
    hours = runtime // 3600  # Integer division to get the hours
    remaining_seconds = runtime % 3600
    minutes = remaining_seconds // 60  # Integer division to get the minutes
    secs = remaining_seconds % 60  # Remainder to get the seconds

    # Format as HH:MM:SS with integer values and zero-padding
    time_elapsed = f"{int(hours):02}:{int(minutes):02}:{int(secs):02}"

    # Assign the formatted time to the runtimeLabel.currValue
    runtimeLabel.currValue = time_elapsed

def poll_fuel_type(connection):
    type = py_obd.get_fuel_type(connection)
    fuelTypeLabel.currValue = type

def poll_throttle_pos(connection):
    pos = py_obd.get_throttle_pos(connection)
    throttlePosLabel.currValue = pos

def poll_absolute_load(connection):
    load = py_obd.get_absolute_load(connection)
    absoluteLoadLabel.currValue = load
    
def poll_engine_load(connection):
    load = py_obd.get_engine_load(connection)
    engineLoadLabel.currValue = load


def poll_cel(conn, cel):
    resp = conn.query(commands.STATUS)
    if resp and resp.value is not None:
        cel.mil = bool(resp.value.MIL)
        cel.dtcCount = int(resp.value.DTC_count)
    else:
        cel.mil = False
        cel.dtcCount = 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = QQuickView()
    view.setSource(QUrl('dashboard.qml'))
    engine = view.engine()

      # Add the directory where your QML files are located
    engine.addImportPath(os.path.join(os.getcwd(), "qml"))  # or .venv path


    # Create classes for each component
    temperature = BarMeter()
    battery_capacity = BarMeter()
    speedometer = Speedometer()
    rpmmeter = RPM_meter()
    centerScreen = CenterScreenWidget()

    # Top labels, first row
    intakePressureLabel = Labels()
    intakeTempLabel = Labels()
    runtimeLabel = stringLabels()
    fuelLevelLabel = Labels()
    fuelTypeLabel = stringLabels()

    # Top labels, second row
    engineLoadLabel = Labels()
    throttlePosLabel = Labels()
    barometricPressureLabel = Labels()
    throttleAcceleratorLabel = Labels()
    absoluteLoadLabel = Labels()

    timer = ZeroToSixtyTimer()

    monitor_Boost_Pressure_B1_Object = object

    with open('output.txt', 'w') as f:
        pass
    

    cel = CheckEngine()
    engine.rootContext().setContextProperty("checkEngine", cel)

    # Sets the object for the qml to refer to. Only needs to be done once for each object.
    engine.rootContext().setContextProperty("speedometer", speedometer)
    engine.rootContext().setContextProperty("temperature", temperature)
    engine.rootContext().setContextProperty("battery_capacity", battery_capacity)
    engine.rootContext().setContextProperty("RPM_Meter", rpmmeter)
    engine.rootContext().setContextProperty("centerScreen", centerScreen)

    # Sets context properties for 1st row
    engine.rootContext().setContextProperty("intakePressureLabel", intakePressureLabel)
    engine.rootContext().setContextProperty("intakeTempLabel", intakeTempLabel)
    engine.rootContext().setContextProperty("runtimeLabel", runtimeLabel)
    engine.rootContext().setContextProperty("fuelLevelLabel", fuelLevelLabel)
    engine.rootContext().setContextProperty("fuelTypeLabel", fuelTypeLabel)

    # Sets context properties for 2nd row
    engine.rootContext().setContextProperty("engineLoadLabel", engineLoadLabel)
    engine.rootContext().setContextProperty("throttlePosLabel", throttlePosLabel)
    engine.rootContext().setContextProperty("barometricPressureLabel", barometricPressureLabel)
    engine.rootContext().setContextProperty("throttleAcceleratorLabel", throttleAcceleratorLabel)
    engine.rootContext().setContextProperty("absoluteLoadLabel", absoluteLoadLabel)

    engine.rootContext().setContextProperty("monitor_Boost_Pressure_B1", monitor_Boost_Pressure_B1_Object)
    engine.rootContext().setContextProperty("zeroToSixtyTimer", timer)

    # Set initial values
    speedometer.setAllValues(0.0, 160.0, 0.0)
    speedometer.currSpeed = 0
    temperature.setAllValues(0.0, 300.0, 0.0)
    temperature.currValue = 270.0
    battery_capacity.setAllValues(0.0, 100.0, 0.0)
    battery_capacity.currValue = 50.0
    rpmmeter.setAllValues(0.0, 8.0, 0.0)

    # Sets initial values for 1st row
    intakeTempLabel.setAllValues(0.0)
    intakePressureLabel.setAllValues(0.0)
    runtimeLabel.currValue = "00:00:00"
    fuelLevelLabel.setAllValues(0.0)
    fuelTypeLabel.currValue = "Gasoline"
    engineLoadLabel.setAllValues(0.0)

    view.update()
    view.show()

    # connection = obd.OBD() # auto-connects to USB or RF port
    
    connection, car_ready = make_connection()
    print("Car connected:", car_ready)

    # print(connection.status())
    # obd.logger.setLevel(obd.logging.DEBUG)
    py_obd.get_supported_pids_mode01(connection)
    py_obd.get_supported_pids_mode06(connection)

    speed_timer = QTimer()
    rpm_timer = QTimer()
    battery_timer = QTimer()
    temperature_timer = QTimer()
    date_timer = QTimer()
    intpressure_timer = QTimer()
    inttemp_timer = QTimer()
    runtime_timer = QTimer()
    load_timer = QTimer()
    throttlepos_timer = QTimer()
    engine_load_timer = QTimer()

    response = connection.query(commands.STATUS)
    mil_status = response.value.MIL       # True/False for Check Engine
    dtc_count = response.value.DTC_count  # Number of codes currently stored

    speed_timer.timeout.connect(lambda: poll_speed(connection))
    rpm_timer.timeout.connect(lambda: poll_rpm(connection))
    battery_timer.timeout.connect(lambda: poll_fuel(connection))
    battery_timer.timeout.connect(lambda: poll_cel(connection, cel))
    temperature_timer.timeout.connect(lambda: poll_coolantTemp(connection))
    date_timer.timeout.connect(lambda: poll_time())
    intpressure_timer.timeout.connect(lambda: poll_intake_pressure(connection))
    inttemp_timer.timeout.connect(lambda: poll_intake_temp(connection))
    runtime_timer.timeout.connect(lambda: poll_runtime(connection))
    load_timer.timeout.connect(lambda: poll_absolute_load(connection))
    throttlepos_timer.timeout.connect(lambda: poll_throttle_pos(connection))
    engine_load_timer.timeout.connect(lambda: poll_engine_load(connection))

    poll_fuel_type(connection)
    speed_timer.start(200) # Polling rate of speed 200 ms
    rpm_timer.start(200) # Polling rate of rpm 200 ms
    battery_timer.start(5000) # Polling rate of speed 5 s
    temperature_timer.start(5000) # Polling rate of speed 5 s
    date_timer.start(1000) # Polling rate of date and time 1 s
    intpressure_timer.start(1000)
    inttemp_timer.start(1000)
    runtime_timer.start(500)
    load_timer.start(1000)
    throttlepos_timer.start(500)
    engine_load_timer.start(1000)
    


    # timer = QTimer()
    # timer.timeout.connect(lambda: receiver(connection, speedometer, temperature, battery_capacity, rpmmeter)
    # timer.start(500)
    

    sys.exit(app.exec_())
