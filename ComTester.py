import obd
ports = obd.scan_serial()
print("Available OBD ports:", ports)
connection = obd.OBD(ports[3], check_voltage=False) if ports else None