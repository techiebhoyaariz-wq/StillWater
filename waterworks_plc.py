#!/usr/bin/env python3
"""
Operation Stillwater - Little Formby Water Works PLC simulator
LUHack OT Security CTF.

A deliberately insecure Modbus/TCP PLC, simulated on your own machine.
Pure standard library. LOCALHOST ONLY - never expose this to a real network.

Every launch is UNIQUE: the flags, the cipher key, the attacker's replayable
command, the engineer PIN and the firmware build are all derived from a per-session
seed, so no two students have the same answers and nothing is copyable. Set
STILLWATER_SEED to reproduce a specific instance (e.g. for marking).

    python3 waterworks_plc.py
"""
import socket
import struct
import threading
import time
import sys
import os
import base64
import random
import hashlib
import json
import http.server

HOST = "127.0.0.1"
PORT = 5020
HMI_PORT = 8800

# ---------------------------------------------------------------------------
# Per-session randomisation
# ---------------------------------------------------------------------------
SEED = os.environ.get("STILLWATER_SEED") or os.urandom(8).hex()
_rng = random.Random(SEED)
SID = hashlib.sha256(SEED.encode()).hexdigest()[:4]   # 4-hex session id


def _b(s):
    return base64.b64decode(s).decode()


def F(name):
    """A session-bound flag: nobody else's instance produces the same string.
    `name` is passed obfuscated so the answers aren't greppable in this source."""
    return f"luhack{{{_b(name)}_{SID}}}".encode()


SAFE_LOW, SAFE_HIGH = 40, 60
CUTOFF = 98
RIGGED_SETPOINT = _rng.randrange(88, 100)

ENG_PIN = _rng.randrange(1000, 10000)                 # 4-digit engineer PIN (leaked in /diag; gates /maint)
XOR_KEY = bytes(_rng.randrange(1, 256) for _ in range(3))
FW_BUILD = _rng.randrange(1000, 9999)                 # firmware build no == maint-mode key
MAINT_KEY = FW_BUILD                                  # write this to CMD reg 9 to unlock writes
REPLAY_REG = 66                                       # the attacker's privileged command register
REPLAY_VAL = _rng.randrange(20000, 60000)            # value seen ONLY in the captured traffic
REPORT_REG = 5                                        # HMI reads its displayed level from here (writable!)

FLAG_RECON = F("cGxjX3dpZGVfb3Blbg==")
FLAG_DOSE = F("c2V0cG9pbnRfcmVjb3ZlcmVk")
FLAG_BYPASS = F("aW50ZXJsb2NrX3JlZW5nYWdlZA==")
FLAG_REPLAY = F("Y29tbWFuZF9yZXBsYXllZA==")         # replay a captured privileged command (T0831)
FLAG_DIAG = F("ZGVmYXVsdF9jcmVkcw==")               # default credentials on /diag (T0812)
FLAG_CIPHER = F("eG9yX2NyaWJiZWQ=")     # this plaintext is the cipher flag
FLAG_SPOOF = F("c3Bvb2ZlZF9yZWFkb3V0")              # spoof the operator's HMI readout (T0856)
FLAG_PCAP = F("Y2FwdHVyZV9yZWFzc2VtYmxlZA==")
FLAG_MASTER = F("cHJvY2Vzc19yZXN0b3JlZA==")
FLAG_HMI = F("dG9rZW5faW5fcGFnZV9zb3VyY2U=")   # hidden in the HMI web layer
FLAG_MAINT = F("YWNjZXNzX2NvbnRyb2xfYnlwYXNz")     # /maint broken access control (chains the /diag PIN)
FLAG_UNLOCK = F("b3BlcmF0aW5nX21vZGU=")    # write-protect / change-operating-mode bypass

# ---------------------------------------------------------------------------
# Plant state
# ---------------------------------------------------------------------------
coils = [False] * 16            # 0 PUMP, 1 MANUAL_OVERRIDE, 2 PURGE_VALVE (honeypot)
discrete_inputs = [False] * 16
input_registers = [0] * 64      # 0 true level, 1 flow, 10+ grid-ref, 24+ noise
holding_registers = [0] * 400   # 300+ : truncated flag hashes (for the scoreboard)

ALL_FLAGS = None                # set in init_state

lock = threading.Lock()
_warned_overflow = False
_ch2 = _ch3 = _replay = _spoof = _master = False
_unlock = False
_prev_override = True


def pack_ascii(text):
    b = text.encode() if isinstance(text, str) else text
    if len(b) % 2:
        b += b"\x00"
    return [(b[i] << 8) | b[i + 1] for i in range(0, len(b), 2)]


def put(table, addr, text):
    for i, v in enumerate(pack_ascii(text)):
        table[addr + i] = v


def xor_bytes(data, key):
    return bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))


def pack_bytes(table, addr, data):
    for i in range(0, len(data) - 1, 2):
        table[addr + i // 2] = (data[i] << 8) | data[i + 1]
    if len(data) % 2:
        table[addr + len(data) // 2] = data[-1] << 8


def init_state():
    holding_registers[1] = RIGGED_SETPOINT
    input_registers[0] = 96
    input_registers[1] = 12
    holding_registers[REPORT_REG] = 96       # HMI-reported level (mirrors true level until spoofed)
    coils[1] = True

    # Nothing is labelled. The challenges hide in plausible controller data;
    # finding what's out of place is part of the work.
    put(holding_registers, 10, base64.b64encode(FLAG_RECON).decode())   # recon: base64, unlabelled
    pack_bytes(holding_registers, 150, xor_bytes(FLAG_CIPHER, XOR_KEY))  # cipher: unlabelled bytes

    # Camouflage so no block shouts 'flag here'. One of these is a DECOY base64
    # that decodes to junk - recognising the real one is the challenge.
    put(holding_registers, 48, "RTU-3 ONLINE")
    put(holding_registers, 92, "SCADA LINK OK")
    put(holding_registers, 130, "LFWW UNIT3 CONTACT TANK T-301")
    put(holding_registers, 163, f"FW 2.14.3 BUILD {FW_BUILD} OK")
    # Write-protect bypass (T0858 Change Operating Mode): param reg 8 is write-locked
    # in RUN mode; writing the FW build number to CMD reg 9 enters MAINT and unlocks it.
    put(holding_registers, 250, "PARAM REG8 WRITE-LOCKED IN RUN. ENTER MAINT: WR FW BUILD No TO REG9")
    put(holding_registers, 198, base64.b64encode(b"NODE3 LINK NOMINAL").decode())  # DECOY
    put(holding_registers, 216, "CL2 0.42 MG/L PH 7.21")
    put(holding_registers, 240, "TURB 1.1 NTU TEMP 14C")
    put(holding_registers, 215, "luhack{legacy_factory_test_tag}"[::-1])   # reversed decoy flag
    for a, v in [(95, 312), (96, 305), (97, 318), (101, 742), (102, 738), (103, 745), (108, 299)]:
        holding_registers[a] = v                                        # camouflage the bank selector
    for i, v in enumerate([512, 480, 497, 503, 488, 515, 471, 509, 744, 739]):
        input_registers[24 + i] = v
    put(input_registers, 10, "GRID SD4821 6133")

    # Scoreboard support: store a truncated sha256 of each flag (not reversible),
    # in challenge order, so the console can validate submissions without the
    # plaintext ever being readable.
    global ALL_FLAGS
    ALL_FLAGS = [FLAG_RECON, FLAG_DOSE, FLAG_BYPASS, FLAG_REPLAY, FLAG_DIAG,
                 FLAG_CIPHER, FLAG_SPOOF, FLAG_PCAP, FLAG_MASTER, FLAG_HMI,
                 FLAG_MAINT, FLAG_UNLOCK]
    for i, fl in enumerate(ALL_FLAGS):
        h = hashlib.sha256(fl).digest()[:4]
        holding_registers[300 + 2 * i] = (h[0] << 8) | h[1]
        holding_registers[300 + 2 * i + 1] = (h[2] << 8) | h[3]

    write_pcap()


# ---------------------------------------------------------------------------
# Session-bound incident capture (pure stdlib; drops the scapy dependency)
# ---------------------------------------------------------------------------
def _cksum(data):
    if len(data) % 2:
        data += b"\x00"
    s = sum((data[i] << 8) | data[i + 1] for i in range(0, len(data), 2))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def _frame(src, dst, sport, dport, seq, ack, flags, payload):
    mac_a = bytes.fromhex("0242ac110001")
    mac_b = bytes.fromhex("0242ac110002")
    eth = mac_b + mac_a + b"\x08\x00"
    tcp = struct.pack(">HHIIBBHHH", sport, dport, seq, ack,
                      (5 << 4), flags, 8192, 0, 0)
    sip = bytes(int(x) for x in src.split("."))
    dip = bytes(int(x) for x in dst.split("."))
    pseudo = sip + dip + b"\x00\x06" + struct.pack(">H", len(tcp) + len(payload))
    csum = _cksum(pseudo + tcp + payload)
    tcp = tcp[:16] + struct.pack(">H", csum) + tcp[18:]
    total = 20 + len(tcp) + len(payload)
    ip = struct.pack(">BBHHHBBH", 0x45, 0, total, 1, 0x4000, 64, 6, 0) + sip + dip
    ip = ip[:10] + struct.pack(">H", _cksum(ip)) + ip[12:]
    return eth + ip + tcp + payload


def write_pcap(path="incident.pcap"):
    attacker, plant = "10.20.4.17", "10.20.4.10"
    sp, dp = 49722, 502
    cs, ss, txn = [1000], [5000], [0]

    def mbap(pdu):
        txn[0] += 1
        return struct.pack(">HHHB", txn[0], 0, len(pdu) + 1, 1) + pdu

    pkts = []

    def c2s(pdu):
        f = _frame(attacker, plant, sp, dp, cs[0], ss[0], 0x18, mbap(pdu))
        cs[0] += len(f) - 54
        pkts.append(f)

    def s2c(pdu):
        f = _frame(plant, attacker, dp, sp, ss[0], cs[0], 0x18, mbap(pdu))
        ss[0] += len(f) - 54
        pkts.append(f)

    pkts.append(_frame(attacker, plant, sp, dp, cs[0], 0, 0x02, b""))
    pkts.append(_frame(plant, attacker, dp, sp, ss[0], cs[0] + 1, 0x12, b""))
    cs[0] += 1; ss[0] += 1
    c2s(struct.pack(">BHH", 3, 0, 10))                       # recon read
    s2c(bytes([3, 20]) + b"\x00\x00" + struct.pack(">H", RIGGED_SETPOINT) + b"\x00" * 16)
    c2s(struct.pack(">BHH", 6, REPLAY_REG, REPLAY_VAL))      # privileged maintenance-unlock command
    s2c(struct.pack(">BHH", 6, REPLAY_REG, REPLAY_VAL))
    c2s(struct.pack(">BHH", 6, 1, RIGGED_SETPOINT))          # sabotage setpoint
    s2c(struct.pack(">BHH", 6, 1, RIGGED_SETPOINT))
    c2s(struct.pack(">BHH", 5, 1, 0xFF00))                   # bypass interlock
    s2c(struct.pack(">BHH", 5, 1, 0xFF00))
    # the hidden maintenance code, SPLIT across several writes so a single-packet
    # grab fails: you must follow the attacker's TCP stream and reassemble, with a
    # benign HMI poller also on the wire so filtering by the attacker IP matters.
    blob = base64.b64encode(FLAG_PCAP)                       # length is a multiple of 4
    a = (len(blob) // 3) & ~1
    b = (2 * len(blob) // 3) & ~1
    frags = [blob[:a], blob[a:b], blob[b:]]
    noise, nsp = "10.20.4.22", [6000]

    def noise_pkt():
        f = _frame(noise, plant, 51000, dp, nsp[0], 1, 0x18, mbap(struct.pack(">BHH", 3, 0, 4)))
        nsp[0] += len(f) - 54
        pkts.append(f)

    for i, fr in enumerate(frags):
        noise_pkt()
        reg = 100 + i * 10
        c2s(struct.pack(">BHHB", 16, reg, len(fr) // 2, len(fr)) + fr)
        s2c(struct.pack(">BHH", 16, reg, len(fr) // 2))
    noise_pkt()

    with open(path, "wb") as fh:
        fh.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for i, f in enumerate(pkts):
            fh.write(struct.pack("<IIII", 1700000000 + i, i * 1000, len(f), len(f)))
            fh.write(f)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def simulate():
    global _warned_overflow, _ch2, _ch3, _replay, _spoof, _master, _unlock, _prev_override
    while True:
        time.sleep(0.5)
        with lock:
            level = input_registers[0]
            setpoint = holding_registers[1]
            override = coils[1]

            # Governor + physics
            coils[0] = level < setpoint
            level += 3 if coils[0] else -2
            if level >= CUTOFF and not override:
                level = CUTOFF
            if level > 100:
                level = 100
                if override and not _warned_overflow:
                    sys.stderr.write("\n[PLANT] *** OVERFLOW - cutoff BYPASSED. Restore the interlock. ***\n")
                    _warned_overflow = True
            level = max(0, level)
            input_registers[0] = level
            discrete_inputs[1] = level >= 90

            # Ch7 - Spoof Reporting Message (T0856): the HMI shows the level from a
            # WRITABLE register. Forge it (a lie far from the true level) and the
            # operator's screen freezes on the lie - you've blinded them.
            if not _spoof and abs(holding_registers[REPORT_REG] - level) >= 15 \
                    and 25 <= holding_registers[REPORT_REG] <= 75:
                put(holding_registers, 182, FLAG_SPOOF); _spoof = True
                sys.stderr.write("[PLANT] HMI readout SPOOFED - operator blinded; flag in HR182+\n")
            if not _spoof:
                holding_registers[REPORT_REG] = level      # keep the display honest until forged

            if SAFE_LOW <= setpoint <= SAFE_HIGH and not _ch2:
                put(holding_registers, 50, FLAG_DOSE); _ch2 = True
                sys.stderr.write("[PLANT] Setpoint safe - flag in HR50+\n")

            if _prev_override and not override and not _ch3:
                put(holding_registers, 30, FLAG_BYPASS); _ch3 = True; _warned_overflow = False
                sys.stderr.write("[PLANT] Interlock restored - flag in HR30+\n")
            _prev_override = override

            # Ch4 - Replay Attack (T0831): the attacker's privileged command (seen
            # only in the capture) has no replay protection. Resend it and it works.
            if holding_registers[REPLAY_REG] == REPLAY_VAL and not _replay:
                put(holding_registers, 76, FLAG_REPLAY); _replay = True
                sys.stderr.write("[PLANT] privileged command replayed - flag in HR76+\n")

            # Write-protect bypass (T0858): param reg 8 is write-locked in RUN mode.
            # Writing the FW build number to CMD reg 9 enters MAINT and unlocks writes;
            # a successful write to the protected reg 8 then releases the flag.
            maint = (holding_registers[9] == MAINT_KEY)
            put(holding_registers, 276, "MAINT:UNLOCKED" if maint else "RUN:WR-LOCKED")
            if maint and holding_registers[8] and not _unlock:
                put(holding_registers, 284, FLAG_UNLOCK); _unlock = True
                sys.stderr.write("[PLANT] MAINT mode - param write-lock bypassed; flag in HR284+\n")

            # Ch master: synthesis + chaining (enciphered with the Ch6 key)
            restored = (_ch2 and _ch3 and _replay and not override and level <= SAFE_HIGH)
            if restored and not _master:
                pack_bytes(holding_registers, 110, xor_bytes(FLAG_MASTER, XOR_KEY))
                _master = True
                sys.stderr.write("[PLANT] MASTER OVERRIDE released (enciphered) in HR110+\n")


# ---------------------------------------------------------------------------
# Minimal Modbus/TCP server
# ---------------------------------------------------------------------------
def read_bits(table, start, count):
    out = bytearray((count + 7) // 8 + 1)
    out[0] = (count + 7) // 8
    for i in range(count):
        if table[start + i]:
            out[1 + i // 8] |= 1 << (i % 8)
    return bytes(out)


def read_words(table, start, count):
    out = bytearray([count * 2])
    for i in range(count):
        out += struct.pack(">H", table[start + i] & 0xFFFF)
    return bytes(out)


def handle_pdu(pdu):
    fc = pdu[0]
    try:
        with lock:
            if fc in (1, 2):
                start, count = struct.unpack(">HH", pdu[1:5])
                return bytes([fc]) + read_bits(coils if fc == 1 else discrete_inputs, start, count)
            if fc in (3, 4):
                start, count = struct.unpack(">HH", pdu[1:5])
                return bytes([fc]) + read_words(holding_registers if fc == 3 else input_registers, start, count)
            if fc == 5:
                addr, val = struct.unpack(">HH", pdu[1:5])
                coils[addr] = (val == 0xFF00); return pdu
            if fc == 6:
                addr, val = struct.unpack(">HH", pdu[1:5])
                # param reg 8 is write-protected unless controller is in MAINT mode
                if addr == 8 and holding_registers[9] != MAINT_KEY:
                    return bytes([fc | 0x80, 0x04])      # 0x04 slave device failure
                holding_registers[addr] = val; return pdu
            if fc == 15:
                start, count = struct.unpack(">HH", pdu[1:5]); data = pdu[6:6 + pdu[5]]
                for i in range(count):
                    coils[start + i] = bool(data[i // 8] & (1 << (i % 8)))
                return bytes([fc]) + struct.pack(">HH", start, count)
            if fc == 16:
                start, count = struct.unpack(">HH", pdu[1:5]); data = pdu[6:]
                locked = holding_registers[9] != MAINT_KEY
                for i in range(count):
                    if start + i == 8 and locked:
                        continue                          # reg 8 write-protected in RUN
                    holding_registers[start + i] = struct.unpack(">H", data[2 * i:2 * i + 2])[0]
                return bytes([fc]) + struct.pack(">HH", start, count)
    except (IndexError, struct.error):
        pass
    return bytes([fc | 0x80, 0x02])


def serve_client(conn):
    with conn:
        while True:
            head = conn.recv(7)
            if len(head) < 7:
                return
            txn, proto, length, unit = struct.unpack(">HHHB", head)
            pdu = conn.recv(length - 1)
            if not pdu:
                return
            resp = handle_pdu(pdu)
            conn.sendall(struct.pack(">HHHB", txn, 0, len(resp) + 1, unit) + resp)


def hmi_page():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hmi.html")
    try:
        html = open(path, encoding="utf-8").read()
    except OSError:
        html = "<!DOCTYPE html><title>HMI</title><h1>hmi.html missing</h1><!--FLAG-->"
    # A hardcoded secret left in the client's JavaScript - the kind of cyber-hygiene
    # slip real engagements find by reading an HMI's page source. It also names the
    # maintenance endpoint and how it authorises callers (the lead for the /maint flag).
    cfg = ('const svc = {node:"WQ_01", poll:600, proto:"modbus",\n'
           '    // legacy engineer session - TODO strip before go-live\n'
           f'    maint:"/maint", diag:"/diag", auth:"role", engToken:"{FLAG_HMI.decode()}"}};')
    return html.replace("//@STATION_CFG", cfg)


class HMIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        if self.path.startswith("/diag"):
            # Engineering diagnostics, left on FACTORY DEFAULT credentials (T0812) -
            # the single most common real-world OT finding. Logging in leaks the
            # engineer PIN and the firmware build (which feed the /maint and
            # write-protect flags), exactly as a real diag console over-shares.
            q = parse_qs(urlparse(self.path).query)
            user = q.get("user", [""])[0]
            pw = q.get("pw", [""])[0]
            defaults = {("admin", "admin"), ("admin", "password"),
                        ("admin", "1234"), ("operator", "operator")}
            if not user:
                return self._send(200,
                    "<h2>SL-3000 Engineering Diagnostics</h2>"
                    "<p>Authentication required: <code>/diag?user=&amp;pw=</code></p>"
                    "<p>(factory units ship with default engineering credentials)</p>")
            if (user, pw) not in defaults:
                return self._send(401, "<h2>401</h2><p>Invalid engineering credentials.</p>")
            return self._send(200,
                "<h2>SL-3000 Engineering Diagnostics - AUTHENTICATED</h2>"
                f"<pre>engineer line PIN .... {ENG_PIN}\n"
                f"controller build ..... {FW_BUILD}\n"
                f"diag token ........... {FLAG_DIAG.decode()}</pre>")
        if self.path.startswith("/maint"):
            # Engineer maintenance console. Broken access control: the server trusts
            # a client-supplied ?role=, and the engineer gate is the 4-digit PIN that
            # the /diag console (default creds) hands you.
            q = parse_qs(urlparse(self.path).query)
            role = q.get("role", ["operator"])[0]
            pin = q.get("pin", [""])[0]
            if role != "engineer":
                return self._send(403,
                    "<h2>403 - Maintenance console</h2><p>Access denied. role="
                    f"<b>{role}</b> is read-only. Engineer role required.</p>")
            if pin != str(ENG_PIN):
                return self._send(403,
                    "<h2>Engineer role accepted</h2><p>Maintenance PIN required: "
                    "append <code>&pin=</code> with the engineer line PIN (see /diag).</p>")
            return self._send(200,
                "<h2>Maintenance console - ENGINEER</h2>"
                "<pre>override log:\n  ISH-301 interlock .... forced OPEN by 10.20.4.17\n"
                f"  dosing setpoint ...... forced {RIGGED_SETPOINT}\n"
                f"engineer token: {FLAG_MAINT.decode()}</pre>")
        if self.path.startswith("/api/state"):
            with lock:
                st = {"level": holding_registers[REPORT_REG], "setpoint": holding_registers[1],
                      "pump": bool(coils[0]), "override": bool(coils[1]),
                      "purge": bool(coils[2]), "spoofed": _spoof,
                      "flow": input_registers[1],
                      "alarm": bool(coils[1]) and holding_registers[REPORT_REG] >= 97}
            body = json.dumps(st).encode()
            ctype = "application/json"
        else:
            body = hmi_page().encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_hmi():
    try:
        srv = http.server.HTTPServer((HOST, HMI_PORT), HMIHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return True
    except OSError:
        return False


def main():
    init_state()
    threading.Thread(target=simulate, daemon=True).start()
    if start_hmi():
        print(f"[PLANT] HMI operator screen at http://{HOST}:{HMI_PORT}")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    print(f"[PLANT] Little Formby Water Works online at {HOST}:{PORT}")
    print(f"[PLANT] session {SID} - this instance's flags are unique to you")
    print("[PLANT] (Ctrl-C to stop)")
    try:
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=serve_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[PLANT] shutting down")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
