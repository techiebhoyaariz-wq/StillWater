#!/usr/bin/env python3
"""
Operation Stillwater - Operations Monitor.
A live SCADA screen for the Little Formby Water Works. Leave it running in a
second window while you attack the plant from the console - it shows the process
in real time and raises security events as you touch the controller.

    python3 monitor.py
"""
import socket
import struct
import time
import sys
import random

HOST, PORT = "127.0.0.1", 5020
G, R, C, Y, B, DIM, X = (
    "\033[92m", "\033[91m", "\033[96m", "\033[93m", "\033[1m", "\033[2m", "\033[0m")
BLU = "\033[38;5;39m"


class Link:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=2)
        self.txn = 0

    def _rpc(self, pdu):
        self.txn = (self.txn + 1) & 0xFFFF
        self.s.sendall(struct.pack(">HHHB", self.txn, 0, len(pdu) + 1, 1) + pdu)
        h = self._recv(7)
        return self._recv(struct.unpack(">HHHB", h)[2] - 1)

    def _recv(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise OSError("closed")
            b += c
        return b

    def words(self, fc, a, n):
        r = self._rpc(struct.pack(">BHH", fc, a, n))
        return [struct.unpack(">H", r[2 + 2 * i:4 + 2 * i])[0] for i in range(n)]

    def bits(self, fc, a, n):
        r = self._rpc(struct.pack(">BHH", fc, a, n))
        v = int.from_bytes(r[2:2 + r[1]], "little")
        return [(v >> i) & 1 for i in range(n)]


LOG = []
AMBIENT = ["LT-301 transmitter nominal", "FIC-102 dosing loop steady",
           "comms heartbeat OK", "historian sync complete", "P-101 bearing temp normal",
           "chlorine residual in range", "RTU-3 keepalive", "turbidity nominal"]


def ev(msg, col=DIM, tag="INFO"):
    t = time.strftime("%H:%M:%S")
    LOG.append(f"{DIM}{t}{X}  {col}{tag:<4}{X} {msg}")
    del LOG[:-9]


def tank(level, setp):
    rows = []
    fill = round(level / 100 * 8)
    spf = round(setp / 100 * 8)
    for i in range(8):
        r = 8 - i
        cell = f"{BLU}████{X}" if r <= fill else f"{DIM}····{X}"
        mark = f"{Y}sp{X}" if r == spf else "  "
        cap = "100" if i == 0 else ("  0" if i == 7 else "   ")
        rows.append(f"   {mark} ║{cell}║ {DIM}{cap}{X}")
    return rows


def frame(st):
    level, setp, pump, override, purge, report, spoofed = st
    w = 70
    out = ["\033[H"]
    bar = "█" * round(level / 20) + "░" * (5 - round(level / 20))
    lc = R if level >= 90 else (Y if level >= 75 else G)
    out.append(f" {C}┌{'─'*w}┐{X}")
    title = f"{B}LITTLE FORMBY WATER WORKS{X}   OPERATIONS MONITOR   UNIT 3"
    out.append(f" {C}│{X} {title}{' '*(w-57)}{DIM}{time.strftime('%H:%M:%S')}{X} {C}│{X}")
    out.append(f" {C}├{'─'*w}┤{X}")
    rows = tank(level, setp)
    tele = [
        f"{DIM}TELEMETRY{X}",
        f"LEVEL      {lc}{level:>3}%{X}  [{lc}{bar}{X}]",
        f"SETPOINT   {setp:>3}   {DIM}(safe 40-60){X}",
        f"PUMP       {(G+'● RUNNING') if pump else (DIM+'○ idle')}{X}",
        f"INTERLOCK  {(R+'✖ BYPASSED') if override else (G+'● engaged')}{X}",
        f"DOSING     {DIM}CL2 injection{X}",
        f"HMI RPT    {(R+'✖ SPOOFED '+str(report)+'%') if spoofed else (G+'● '+str(report)+'%')}{X}",
        "",
    ]
    out.append(f" {C}│{X}   {DIM}CONTACT TANK T-301{X}{' '*20}{tele[0]}{' '*18}{C}│{X}")
    for i in range(8):
        left = rows[i]
        right = tele[i + 1] if i + 1 < len(tele) else ""
        # pad accounting for ANSI is awkward; keep it loose
        out.append(f" {C}│{X} {left}      {right}")
    out.append(f" {C}├{'─'*w}┤{X}")
    out.append(f" {C}│{X} {DIM}SECURITY / EVENT LOG{X}")
    for ln in LOG[-9:]:
        out.append(f" {C}│{X}   {ln}\033[K")
    for _ in range(9 - len(LOG[-9:])):
        out.append(f" {C}│{X}\033[K")
    out.append(f" {C}└{'─'*w}┘{X}\033[K")
    if override and level >= 97:
        out.append(f"   {R}{B}  ▀▄▀▄  OVERFLOW · WEIR OVERTOPPING · CUTOFF BYPASSED  ▄▀▄▀{X}\033[K")
    else:
        out.append("\033[K")
    return "\n".join(out)


def main():
    sys.stdout.write("\033[2J\033[?25l")
    try:
        link = None
        prev = None
        amb = 0
        ev("operations monitor started", C, "SYS")
        while True:
            if link is None:
                try:
                    link = Link(); ev("connected to PLC-01 (Modbus/TCP :5020)", G, "SYS")
                except OSError:
                    sys.stdout.write("\033[H  connecting to the plant...\033[K\n"); time.sleep(1); continue
            try:
                level = link.words(4, 0, 1)[0]
                setp = link.words(3, 1, 1)[0]
                pump, override, purge = link.bits(1, 0, 3)
                report = link.words(3, 5, 1)[0]
                spoofed = 1 if abs(report - level) >= 15 else 0
            except OSError:
                link = None; ev("PLC link lost", R, "COMM"); continue

            st = (level, setp, pump, override, purge, report, spoofed)
            if prev:
                if setp != prev[1]:
                    ev(f"unauthorised write  HR1 setpoint {prev[1]}->{setp}", R, "SEC")
                if override != prev[3]:
                    ev(f"coil 1 MANUAL_OVERRIDE {'set' if override else 'cleared'}",
                       R if override else G, "SEC")
                if purge and not prev[4]:
                    ev("coil 2 PURGE_VALVE actuated (no effect)", Y, "SEC")
                if spoofed and not prev[6]:
                    ev(f"HMI readout SPOOFED: screen shows {report}%, true level {level}%", R, "SEC")
                if level >= 97 and prev[0] < 97:
                    ev("HIGH-HIGH level alarm  LAH-301", R, "ALRM")
            else:
                ev("process scan baseline captured", DIM, "INFO")
            amb += 1
            if amb % 6 == 0:
                ev(random.choice(AMBIENT))
            prev = st
            sys.stdout.write(frame(st))
            sys.stdout.flush()
            time.sleep(0.8)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\033[0m\n")


if __name__ == "__main__":
    main()
