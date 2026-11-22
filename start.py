#!/usr/bin/env python3
"""
Operation Stillwater - launcher.
Boots the plant, opens the operator display, drops you into the console.

    python3 start.py
"""
import atexit
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
procs = []

C_DIM, C_RED, C_AMB, C_CYN, C_GRN, C_RST = (
    "\033[2m", "\033[91m", "\033[93m", "\033[96m", "\033[92m", "\033[0m")


def boot(line, delay=0.25, colour=""):
    print(f"  {colour}{line}{C_RST}")
    time.sleep(delay)


def spawn(script):
    p = subprocess.Popen([PY, os.path.join(HERE, script)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p


@atexit.register
def _cleanup():
    for p in procs:
        if p.poll() is None:
            p.terminate()
    time.sleep(0.3)
    for p in procs:
        if p.poll() is None:
            p.kill()


def open_monitor():
    """Open the live operations monitor in its own terminal window, if we can."""
    mon = os.path.join(HERE, "monitor.py")
    attempts = [
        ["gnome-terminal", "--title=Operations Monitor", "--", PY, mon],
        ["konsole", "-e", PY, mon],
        ["xfce4-terminal", "--title=Operations Monitor", "-e", f"{PY} {mon}"],
        ["mate-terminal", "-e", f"{PY} {mon}"],
        ["x-terminal-emulator", "-e", PY, mon],
        ["xterm", "-title", "Operations Monitor", "-e", PY, mon],
    ]
    for cmd in attempts:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return False


def wait_for_plant(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", 5020), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


BANNER = f"""{C_CYN}
   ┌────────────────────────────────────────────────────────┐
   │   LITTLE FORMBY WATER WORKS  ·  SCADA FIELD GATEWAY     │
   │   Rheged Infrastructure & Cyber Directorate  ·  RICD    │
   └────────────────────────────────────────────────────────┘{C_RST}"""


def launch_session():
    print(BANNER)
    time.sleep(0.4)
    boot("[boot]  field gateway coming online ...", colour=C_DIM)
    spawn("waterworks_plc.py")
    if not wait_for_plant():
        boot("[boot]  PLC did not respond. Check the errors above.", colour=C_RED)
        return
    boot("[boot]  Modbus/TCP service  127.0.0.1:5020  ... UP", colour=C_GRN)
    boot("[scada] polling PLC tags ... connected", colour=C_GRN)
    boot("[scada] reading process state ...")
    boot("[ALARM] overflow interlock .......... BYPASSED", colour=C_RED)
    boot("[ALARM] dosing setpoint ............. OUT OF RANGE", colour=C_RED)
    boot("[ALARM] tank level .................. CRITICAL", colour=C_RED)
    boot("[scada] the plant is under attacker control.", 0.4, C_AMB)

    boot("[scada] HMI operator screen -> http://127.0.0.1:8800", colour=C_CYN)
    try:
        import webbrowser
        webbrowser.open("http://127.0.0.1:8800")
    except Exception:
        pass
    boot("[scada] opening operations monitor ...", colour=C_DIM)
    if not open_monitor():
        boot("[scada] (no second window - run  python3 monitor.py  alongside)", colour=C_DIM)
    try:
        import pygame  # noqa: F401
        spawn("worldview.py")
        time.sleep(0.6)
    except ImportError:
        pass

    boot("[RICD]  console online. You have the controls.", 0.3, C_CYN)
    print(f"  {C_DIM}type 'help' to see your commands, 'quit' to disconnect.{C_RST}\n")
    subprocess.run([PY, os.path.join(HERE, "stillwater.py")])


if __name__ == "__main__":
    try:
        launch_session()
    except KeyboardInterrupt:
        pass
