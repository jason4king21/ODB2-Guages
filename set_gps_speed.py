import serial

def set_update_rate(port="/dev/ttyUSB0", rate_ms=100):
    cmd = f"$PMTK220,{rate_ms}*"
    # Compute checksum
    cs = 0
    for c in cmd[1:]:
        cs ^= ord(c)
    full = f"{cmd}{cs:02X}\r\n"
    with serial.Serial(port, 9600, timeout=1) as s:
        s.write(full.encode())

set_update_rate("COM5", 100)
