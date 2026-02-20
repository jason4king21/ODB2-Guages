import time
import serial

PORT = "/dev/rfcomm0"
BAUD = 115200

# Try these ranges first (common GM enhanced blocks on P59-era)
RANGES = [
    (0x1100, 0x11FF),
    (0x1900, 0x19FF),
    (0x1A00, 0x1AFF),
]

def cmd(ser, s, d=0.15, w=2.0):
    ser.reset_input_buffer()
    ser.write((s + "\r").encode())
    time.sleep(d)
    end = time.time() + w
    out = ""
    while time.time() < end:
        chunk = ser.read(ser.in_waiting or 1).decode(errors="ignore")
        if chunk:
            out += chunk
            if ">" in out:
                break
        else:
            time.sleep(0.01)
    return out.replace("\r", "\n")

def init(ser):
    print(cmd(ser, "ATZ", 0.8, 3.0))
    print(cmd(ser, "ATE0"))
    print(cmd(ser, "ATL0"))
    print(cmd(ser, "ATS0"))
    print(cmd(ser, "ATH1"))
    print(cmd(ser, "ATSP0"))
    print(cmd(ser, "ATDP"))
    # A little more patience on VPW
    print(cmd(ser, "ATST96"))   # timeout ~150ms*? (ELM units), slightly longer
    print(cmd(ser, "ATAT2"))    # adaptive timing

def looks_like_hit(txt):
    t = txt.upper()
    if "NO DATA" in t or "STOPPED" in t or "UNABLE" in t or "?" in t:
        return False
    # Mode 22 positive response is 0x62
    return "62" in t

def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    init(ser)

    hits = []
    try:
        for start, end in RANGES:
            print(f"\n[SCAN] 22{start:04X}..22{end:04X}")
            for pid in range(start, end + 1):
                q = f"22{pid:04X}"
                out = cmd(ser, q, d=0.12, w=1.2)
                if looks_like_hit(out):
                    print(f"\nHIT {q}")
                    print(out.strip())
                    hits.append((q, out.strip()))
                # tiny delay to be kind to VPW bus
                time.sleep(0.01)

        print(f"\nDone. Hits: {len(hits)}")
        for q, _ in hits:
            print(" ", q)

    finally:
        ser.close()

if __name__ == "__main__":
    main()