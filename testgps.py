import serial
import pynmea2
import time

def convert_knots_to_mph(knots: float) -> float:
    return knots * 1.15078  # standard conversion :contentReference[oaicite:1]{index=1}

def main(port="COM5", baud=9600):
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1)
        print(f"Listening on {port} @ {baud} baud...")
    except serial.SerialException as e:
        print("Unable to open port:", e)
        return

    while True:
        try:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if not line:
                continue

            print("RAW:", line)

            # Check for RMC sentence, which includes speed
            if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                msg = pynmea2.parse(line)
                speed_knots = msg.spd_over_grnd or 0.0
                speed_mph = convert_knots_to_mph(float(speed_knots))
                print(f"RMC parsed: time={msg.timestamp}, lat={msg.latitude}, lon={msg.longitude}, speed={speed_mph:.2f} MPH")

            # Optional: display VTG for speed via another sentence
            elif line.startswith('$GPVTG') or line.startswith('$GNVTG'):
                msg = pynmea2.parse(line)
                speed_knots = msg.spd_over_grnd or 0.0
                speed_kmph = msg.spd_over_grnd_kmph or 0.0
                speed_mph = convert_knots_to_mph(float(speed_knots))
                print(f"VTG parsed: {speed_knots} knots, {speed_kmph} km/h, {speed_mph:.2f} MPH")

        except pynmea2.ParseError as e:
            print("Parse error:", e)
            continue
        except Exception as e:
            print("Unexpected error:", e)
            break

        time.sleep(0.1)

if __name__ == "__main__":
    main()

