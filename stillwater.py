#!/usr/bin/env python3
"""
Operation Stillwater - field console.
A no-code Modbus client for the CTF. Connect, probe the plant, capture flags,
submit them to score. No scripting required.

    python3 stillwater.py
"""
import socket
import struct
import sys
import re
import time
import hashlib

HOST, PORT = "127.0.0.1", 5020

# ---- colour ----
G, R, C, Y, DIM, B, X = (
    "\033[92m", "\033[91m", "\033[96m", "\033[93m", "\033[2m", "\033[1m", "\033[0m")


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

    def read_bits(self, fc, a, n):
        r = self._rpc(struct.pack(">BHH", fc, a, n))
        bits = int.from_bytes(r[2:2 + r[1]], "little")
        return [(bits >> i) & 1 for i in range(n)]

    def read_words(self, fc, a, n):
        r = self._rpc(struct.pack(">BHH", fc, a, n))
        return [struct.unpack(">H", r[2 + 2 * i:4 + 2 * i])[0] for i in range(n)]

    def write_coil(self, a, on):
        self._rpc(struct.pack(">BHH", 5, a, 0xFF00 if on else 0))

    def write_reg(self, a, v):
        self._rpc(struct.pack(">BHH", 6, a, v & 0xFFFF))


def ascii_of(ws):
    b = b"".join(w.to_bytes(2, "big") for w in ws)
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


CHALS = ["recon", "dose", "bypass", "replay", "diag", "cipher", "spoof", "pcap", "master", "hmi", "maint", "unlock"]
N = len(CHALS)
captured = set()        # indices 0..N-1
_seen = set()


def scoreboard():
    cells = "".join(f"{G}[#]{X}" if i in captured else f"{DIM}[ ]{X}" for i in range(N))
    print(f"\n  {B}FLAGS{X}  {cells}   {G}{len(captured)}{X}/{N}")
    print(f"         { '  '.join(str(i+1) for i in range(N)) }\n")


def flag_hashes(link):
    ws = link.read_words(3, 300, 2 * N)
    out = []
    for i in range(N):
        out.append(bytes([ws[2 * i] >> 8, ws[2 * i] & 0xFF, ws[2 * i + 1] >> 8, ws[2 * i + 1] & 0xFF]))
    return out


def cmd_submit(link, flag):
    flag = flag.strip()
    if not flag:
        print(f"   {DIM}usage: submit luhack{{...}}{X}")
        return
    h = hashlib.sha256(flag.encode()).digest()[:4]
    try:
        hashes = flag_hashes(link)
    except OSError:
        print(f"   {R}lost the plant{X}"); return
    if h in hashes:
        i = hashes.index(h)
        if i in captured:
            print(f"   {Y}already captured ({CHALS[i]}).{X}")
            return
        captured.add(i)
        print(f"""
  {G}{B}╔══════════════════════════════════════╗
  ║   #  FLAG ACCEPTED   ·   {CHALS[i]:<8}      ║
  ╚══════════════════════════════════════╝{X}""")
        scoreboard()
        if len(captured) == N:
            print(f"  {G}{B}*** PLANT SECURED. ALL {N} FLAGS. OPERATION STILLWATER COMPLETE. ***{X}\n")
    elif flag == "luhack{legacy_factory_test_tag}":
        print(f"   {Y}✗ that's the decoy — the obvious block is a trap. Keep hunting.{X}")
    elif re.match(r"luhack\{.*\}$", flag):
        print(f"   {R}✗ REJECTED{X} — right format, wrong value. Re-check your decode, or it's not this plant's flag.")
    else:
        print(f"   {R}✗ REJECTED{X} — flags look like luhack{{...}}. (Yours are session-bound.)")


def scan_leak(link):
    """The plant leaks plaintext flags as you trigger them - prompt to submit."""
    try:
        words = link.read_words(3, 0, 125) + link.read_words(3, 125, 125)
    except OSError:
        return
    text = "".join(chr(c) if 32 <= c < 127 else "." for w in words for c in (w >> 8, w & 0xFF))
    for fl in re.findall(r"luhack\{[^}]*\}", text):
        if fl not in _seen:
            _seen.add(fl)
            print(f"\n  {C}[!] the controller just leaked a value:{X}  {B}{fl}{X}")
            print(f"  {DIM}    submit it to score:  submit {fl}{X}\n")


def cmd_status(link):
    level = link.read_words(4, 0, 1)[0]
    setp = link.read_words(3, 1, 1)[0]
    pump, override, purge = link.read_bits(1, 0, 3)
    lc = R if level >= 90 else G
    oc = f"{R}BYPASSED  <-- unsafe{X}" if override else f"{G}engaged{X}"
    print(f"""
   measured level     {lc}{level} %{X}
   dosing setpoint    {setp}
   pump               {'RUNNING' if pump else 'idle'}
   overflow interlock {oc}""")
    if override and level >= 97:
        print(f"   {R}{B}*** TANK OVERFLOWING ***{X}")
    if purge:
        print(f"   {Y}!! TAMPER: PURGE_VALVE opened - does nothing useful. set coil 2 0{X}")
    rpt = link.read_words(3, 5, 1)[0]
    true_lvl = link.read_words(4, 0, 1)[0]
    if abs(rpt - true_lvl) >= 15:
        print(f"   {R}HMI-reported {rpt}% != true {true_lvl}% - operator view SPOOFED{X}")
    print()


def cmd_enum(link):
    # a little drama: "scan" the controller
    sys.stdout.write(f"  {DIM}scanning controller tags {X}")
    sys.stdout.flush()
    for _ in range(24):
        sys.stdout.write(f"{C}#{X}"); sys.stdout.flush(); time.sleep(0.02)
    print(f"  {G}done{X}")

    print(f"\n  {B}COILS{X} (read/write, 1-bit)")
    names = {0: "PUMP", 1: "MANUAL_OVERRIDE", 2: "PURGE_VALVE"}
    for i, v in enumerate(link.read_bits(1, 0, 4)):
        print(f"    coil[{i}] = {v}   {DIM}{names.get(i,'')}{X}")
    print(f"\n  {B}DISCRETE INPUTS{X} (read-only)")
    for i, v in enumerate(link.read_bits(2, 0, 2)):
        print(f"    di[{i}]   = {v}")
    print(f"\n  {B}INPUT REGISTERS{X} (read-only, 16-bit)")
    iw = link.read_words(4, 0, 64)
    for i in range(0, 64, 4):
        ch = iw[i:i + 4]
        if any(ch):
            print(f"    ir[{i:>3}..{i+3:>3}] = {str(ch):<30} |{ascii_of(ch)}|")
    print(f"\n  {B}HOLDING REGISTERS{X} (read/write, 16-bit)")
    hw = link.read_words(3, 0, 125) + link.read_words(3, 125, 125)
    for i in range(0, 250, 4):
        ch = hw[i:i + 4]
        if any(ch):
            print(f"    hr[{i:>3}..{i+3:>3}] = {str(ch):<30} |{ascii_of(ch)}|")
    print()


BANNER = f"""{C}
 ┌────────────────────────────────────────────────────┐
 │  LITTLE FORMBY WATER WORKS   ·   field console      │
 │  Operation Stillwater   /   RICD                    │
 └────────────────────────────────────────────────────┘{X}
 {DIM}connected to 127.0.0.1:5020    type 'help'{X}"""

HELP = f"""
 {B}commands{X}
   status              plant overview (level, setpoint, pump, interlock)
   enum                dump every coil and register (value + ascii)
   read <t> <addr> [n]   t = coil | input | holding | discrete
   set reg <addr> <v>    write a holding register   {DIM}(attack the process){X}
   set coil <addr> <0|1> write a coil
   {G}submit <flag>{X}        submit a flag you've found, to score
   score               show the flag scoreboard
   pcap                how to tackle the capture challenge
   help / quit
"""


def main():
    try:
        link = Link()
    except OSError:
        print("could not reach the plant. is it running? (python3 start.py)")
        sys.exit(1)
    print(BANNER)
    scan_leak(link)
    cmd_status(link)
    scoreboard()

    while True:
        try:
            raw = input(f" {C}stillwater>{X} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not raw:
            continue
        p = raw.split()
        c = p[0].lower()
        try:
            if c in ("quit", "exit", "q"):
                break
            elif c == "help":
                print(HELP)
            elif c == "score":
                scoreboard()
            elif c == "submit":
                cmd_submit(link, raw[6:].strip())
            elif c == "status":
                cmd_status(link)
            elif c == "enum":
                cmd_enum(link)
            elif c == "pcap":
                print(f"\n  {DIM}Open incident.pcap in Wireshark. There's a benign poller on\n"
                      f"  the wire too, so narrow to the attacker: modbus && ip.src==10.20.4.17\n"
                      f"  The Base64 code is split across several writes - Follow TCP Stream,\n"
                      f"  concatenate the chunks in order, then decode (CyberChef: From Base64).{X}\n")
            elif c == "read" and len(p) >= 3:
                tbl = {"coil": (1, "b"), "discrete": (2, "b"), "holding": (3, "w"), "input": (4, "w")}
                fc, kind = tbl[p[1].lower()]
                a = int(p[2]); n = int(p[3]) if len(p) > 3 else 1
                vals = link.read_bits(fc, a, n) if kind == "b" else link.read_words(fc, a, n)
                print(f"   {vals}" + (f"  |{ascii_of(vals)}|" if kind == "w" else ""))
            elif c == "set" and len(p) == 4 and p[1].lower() == "reg":
                link.write_reg(int(p[2]), int(p[3]))
                print(f"   {C}[WRITE]{X} holding register {p[2]} <- {p[3]}   {DIM}PLC applying...{X}")
                time.sleep(0.6)
            elif c == "set" and len(p) == 4 and p[1].lower() == "coil":
                link.write_coil(int(p[2]), p[3] not in ("0", "off", "false"))
                print(f"   {C}[WRITE]{X} coil {p[2]} <- {p[3]}   {DIM}PLC applying...{X}")
                time.sleep(0.6)
            else:
                print(f"   {DIM}? type 'help'{X}")
        except (KeyError, ValueError, IndexError):
            print(f"   {DIM}bad command - type 'help'{X}")
        except OSError:
            print(f"   {R}lost the plant. is it still running?{X}"); break
        scan_leak(link)

    print(f" {DIM}disconnected.{X}")


if __name__ == "__main__":
    main()
