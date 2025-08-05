from gpiozero import Button
from signal import pause
import os
import time
import threading

# Settings
GPIO_PIN = 17          # BCM pin 17 = physical pin 11
DELAY_SECONDS = 3     # Delay before shutdown

# Setup
shutdown_pin = Button(GPIO_PIN, pull_up=True)
shutdown_thread = None
shutdown_pending = False

def delayed_shutdown():
    global shutdown_pending
    shutdown_pending = True
    print(f"[INFO] Pin grounded. Waiting {DELAY_SECONDS} seconds before shutdown...")

    for i in range(DELAY_SECONDS):
        if not shutdown_pin.is_pressed:  # Pin is no longer grounded
            print("[INFO] Pin ungrounded. Shutdown canceled.")
            shutdown_pending = False
            return
        time.sleep(1)

    print("[INFO] Shutdown triggered.")
    os.system("sudo shutdown -h now")

def on_pin_grounded():
    global shutdown_thread
    if not shutdown_pending:
        shutdown_thread = threading.Thread(target=delayed_shutdown)
        shutdown_thread.start()

# When pin is pulled LOW (grounded)
shutdown_pin.when_pressed = on_pin_grounded

print("[INFO] Shutdown monitor started. Waiting for pin to be grounded...")
pause()
