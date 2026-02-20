import time
import serial

PORT = "/dev/rfcomm0"

# Try common ELM baudrates. OBDLink LX usually works with 115200 or 38400 over SPP.
BAUDS = [115200, 38400, 9600]

# A small "likely" list. We'll expand if needed.
# Format is the 2-byte PID after the "22" service.
CANDIDATES = [
    "115C",  # (example oil pressure many GM) - keep as sanity check if you already did it
    "11A6", "11A7", "11A8",
    "1A00", "1A01", "1A02",
    "1940", "1941", "1942",
    "2000", "2001",
    "10A6", "10A7",
    "1460", "1461",
    "2F00", "2F01",  # sometimes related, depends on module
]

def read_until_prompt(ser, timeout=1.2):
    ser.timeout = 0.2
    end = time.time() + timeout
    buf = b""
    while time.time() < end:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if b">" in buf:
                break
    return buf.decode(errors="ignore")

def cmd(ser, s, delay=0.15):
    ser.write((s + "\r").encode())
    time.sleep(delay)
    out = read_until_prompt(ser)
    return out

def init_elm(ser):
    # Basic, stable ELM settings for raw work
    print(cmd(ser, "ATZ", 0.8))
    print(cmd(ser, "ATE0"))   # echo off
    print(cmd(ser, "ATL0"))   # linefeeds off
    print(cmd(ser, "ATS0"))   # spaces off
    print(cmd(ser, "ATH1"))   # headers on (helps identify real replies)
    print(cmd(ser, "ATSP0"))  # auto protocol
    # Optional: faster adaptive timing
    print(cmd(ser, "ATAT2"))
    print(cmd(ser, "ATST64"))  # timeout a bit longer

def is_good_reply(txt):
    # Successful Mode 22 reply typically contains "62" (response for service 22)
    # Example: "62 11 A6 ..."
    t = txt.replace("\r", "\n")
    if "NO DATA" in t or "?" in t or "UNABLE" in t:
        return False
    return "62" in t

def main():
    ser = None
    for b in BAUDS:
        try:
            ser = serial.Serial(PORT, b, timeout=0.2)
            print(f"[INFO] Opened {PORT} at {b}")
            break
        except Exception as e:
            print(f"[WARN] Failed {b}: {e}")
    if ser is None:
        raise SystemExit("Could not open rfcomm port")

    try:
        init_elm(ser)

        print("\n[INFO] Probing Mode 22 candidates...")
        for pid in CANDIDATES:
            q = "22" + pid
            out = cmd(ser, q, 0.2)
            ok = is_good_reply(out)
            print(f"\n>>> {q}  {'OK' if ok else 'no'}")
            print(out.strip())

        print("\n[INFO] Done. If any showed a '62 ....' reply, tell me which PID and paste the raw reply.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()