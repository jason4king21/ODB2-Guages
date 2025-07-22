#!/usr/bin/env python3
import serial
import pynmea2
import time

class ReadLine:
    def __init__(self, s):
        self.buf = bytearray()
        self.s = s

    def readline(self):
        i = self.buf.find(b"\n")
        if i >= 0:
            line = self.buf[:i+1]
            self.buf = self.buf[i+1:]
            return line
        while True:
            size = max(1, min(2048, self.s.in_waiting))
            data = self.s.read(size)
            i = data.find(b"\n")
            if i >= 0:
                line = self.buf + data[:i+1]
                self.buf[:] = data[i+1:]
                return line
            else:
                self.buf.extend(data)


def test_gps(port="COM5", baud=115200, duration=30):
    print(f"Listening on {port} @ {baud} baud for {duration} seconds…")
    ser = serial.Serial(port, baudrate=baud, timeout=1)
    rl = ReadLine(ser)
    while True:
        raw = rl.readline().decode('ascii', errors='ignore')
        if raw.startswith("$GPRMC"):
            msg = pynmea2.parse(raw)
            speed_knots = msg.spd_over_grnd or 0
            speed_mph = speed_knots * 1.15078
            print(f"{speed_mph:.2f} MPH")

if __name__ == "__main__":
    test_gps()
