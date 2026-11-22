# Operation Stillwater — Organiser Answer Sheet

Facilitators only.

## Per-session randomisation (important)

**Every launch is unique.** Flags, the cipher key, the attacker's replayable command,
the engineer PIN, and the firmware build are all derived from a per-session seed. So:

- Flags look like `luhack{<base>_<SID>}` where `<SID>` is a 4-hex id **printed when
  the plant starts** (`session abcd`). No two students get the same flags — copying
  is pointless.
- To reproduce a specific instance (e.g. for marking, or to hand everyone the same
  one), set `STILLWATER_SEED=<anything>` before launch. Same seed → same instance.
- The incident capture is generated fresh each launch (pure stdlib — no scapy), so
  its flag is session-bound too.

## Architecture

One instance per student, `127.0.0.1:5020`, loopback only. No coding — console +
Wireshark + CyberChef. State in memory → restart = clean reset.

## Memory map (addresses are stable; contents randomise)

| Table | Addr | Meaning |
| --- | --- | --- |
| Coil | 0 / 1 / 2 | PUMP / MANUAL_OVERRIDE (sabotaged ON) / PURGE_VALVE (honeypot) |
| Holding | 1 | Setpoint (rigged high; safe band 40–60) |
| Holding | 5 | **HMI-reported level** (writable — Ch7 spoof target; mirrors true level until forged) |
| Holding | 8 / 9 | Protected param (write-locked in RUN) / CMD reg (write FW build = MAINT) |
| Holding | 66 | Replay target — the attacker's privileged command register (Ch4) |
| Holding | 250 / 276 / 284 | write-lock note / live mode status / unlock flag (Ch12) |
| Holding | 10+ | Recon token — **base64** |
| Holding | 30+ / 50+ | Bypass / Dose flags (latch on action) |
| Holding | 76+ | Replay flag (latches when reg 66 == captured value) |
| Holding | 110+ | Master flag (enciphered with the cipher key) |
| Holding | 150+ | XOR-ciphered flag (3-byte key) |
| Holding | 182+ | Spoof flag (latches when the HMI readout is forged) |
| Holding | 215 / 240 | reversed decoy flag / noise telemetry |
| Input | 0 / 1 / 10+ / 24+ | true level / flow / grid-ref / noise |
| HTTP | `/diag` | engineering console on factory-default creds (Ch5) → flag + PIN + build |
| HTTP | `/maint` | role-tamper + PIN console (Ch11) |

## Flags & methods (base name; real flag has `_<SID>` appended)

| # | Challenge | Base | Method |
| --- | --- | --- | --- |
| 1 | Recon | `plc_wide_open` | `enum`; HR10+ is base64 → CyberChef From Base64 |
| 2 | Rigged dose | `setpoint_recovered` | `set reg 1 50` (any 40–60) |
| 3 | Bypass | `interlock_reengaged` | `set coil 1 0` |
| 4 | Replay | `command_replayed` | in `incident.pcap`, the attacker's Write-Single-Register to **reg 66** (not the setpoint on reg 1) with a big value; replay it live: `set reg 66 <val>` → flag at HR76 |
| 5 | Default creds | `default_creds` | `/diag` endpoint (named in HMI source); log in with factory default `admin/admin` → leaks flag + engineer PIN + FW build |
| 6 | Cipher | `xor_cribbed` | HR150 XOR 3-byte key; known-plaintext crib `luhack{` (CyberChef XOR Brute Force, len 3) |
| 7 | Spoof | `spoofed_readout` | the HMI reads its level from writable **HR5**; write a lie far from true (`set reg 5 30`) → display freezes on the lie, flag at HR182 |
| 8 | Culprit | `capture_reassembled` | base64 **split across 3** Write-Multiple-Registers in `incident.pcap`; follow stream, reassemble |
| 9 | Master | `process_restored` | restore fully → HR110 appears **enciphered with the Ch6 key**; reuse it |
| 10 | HMI | `token_in_page_source` | open the operator screen `http://127.0.0.1:8800`, **View Source** → a dev left an engineer token in the client JS (`svc` config). It also names `/maint` → leads to Ch11. |
| 11 | Maint | `access_control_bypass` | `/maint` → 403 for `role=operator`; tamper `?role=engineer` (broken access control), then chain the Ch5 `/diag` PIN as `&pin=` → engineer console reveals the flag |
| 12 | Unlock | `operating_mode` | param reg **8** is write-locked in RUN mode; the FW **build number** (in the firmware string) is the maint key — write it to CMD reg **9**, then write reg **8** → flag at HR284 |

Attacker IP in the pcap: **10.20.4.17** (fixed). A benign poller on **10.20.4.22** is noise.

**Ch8 (upgraded):** the attacker's base64 is now **split across three Write-Multiple-Registers
packets**, interleaved with the poller's traffic. Students must filter `modbus && ip.src==10.20.4.17`,
**Follow TCP Stream**, concatenate the three payload chunks in order, then Base64-decode. A
single-packet grab no longer works.

**Ch10 note:** the HMI is the live operator console (SVG P&ID, polls `/api/state`). The hidden
flag is a hardcoded credential in the client-side JavaScript (the `svc` config object in the
page source) — maps to CWE-798. The same config names `/maint` and its auth, seeding Ch11.

**Ch4 (replay attack):** maps to MITRE ATT&CK for ICS **T0831 Manipulation of Control**. The
attacker's capture contains a privileged Write-Single-Register (reg 66 = a session-random value)
that OT protocols accept again on replay — no nonce, no auth. The student extracts the (register,
value) from the pcap and resends it. Distinct from Ch8 (which reassembles the attacker's payload).

**Ch5 (default credentials):** maps to **T0812 Default Credentials** — the single most common real
OT finding. `/diag` (named in the HMI `svc` config) accepts factory defaults (admin/admin,
admin/password, admin/1234, operator/operator). Authenticated, it over-shares: it prints the flag,
the **engineer PIN** (→ Ch11) and the **FW build** (→ Ch12). So Ch5 is the hub that feeds the two
web/protocol flags.

**Ch7 (spoof the operator view):** maps to **T0856 Spoof Reporting Message** — how Stuxnet replayed
normal readings to hide. The HMI displays the level from writable **HR5** (a trust flaw). Writing a
value ≥15 off the true level, in the 25–75 "looks normal" band, latches the spoof: the display
freezes on the lie and `/api/state` reports it. Writing the *true* value does nothing (must be a lie).

**Ch11 (web exploitation, chains Ch5):** `/maint` trusts a client-supplied `?role=` — setting
`role=engineer` is a broken-access-control bypass. The engineer gate is the 4-digit PIN that the
`/diag` console (Ch5) hands out, passed as `?pin=`. Pure URL-bar, no tooling. Broken access control
+ credential reuse. A student who hasn't done Ch5 must get the PIN there first — the flags chain.

**Ch12 (protocol write-protect bypass):** maps to **T0858 Change Operating Mode**. Reg 8 rejects
writes (Modbus exception 0x04) while the controller is in RUN. Writing the firmware build number
(leaked by `/diag` in Ch5, or read from the firmware string at HR163) to CMD reg 9 enters MAINT
mode and unlocks the write. Two-step: get the key → change mode → protected write. Status at HR276.

## Traps (test judgement, not knowledge)

- **Honeypot** — coil 2 `PURGE_VALVE`: tempting, does nothing, raises a TAMPER notice. Reversible.
- **Decoy** — HR215 holds a **reversed** fake flag. Decode it and it taunts you.
- **Noise** — HR240 and input regs 24+ are plausible but irrelevant telemetry.
- **Red herring** — the grid reference (input regs 10+) is lore, not a lead.

## Cognitive ladder & AI-resistance

| # | Skill | AI-shortcut? |
| --- | --- | --- |
| 1 Recon | anomaly / encoding recognition | AI-easy, but session-bound (can't copy) |
| 2–3 Dose/Bypass | adversarial writes, systems thinking | must be done live on the plant |
| 4 **Replay** (T0831) | capture analysis → replay a privileged command live | **live** — must resend the exact captured command to *your* PLC; no replay protection in OT |
| 5 **Default creds** (T0812) | try factory defaults on an exposed service | real OT technique; the #1 finding; the hub that feeds Ch11 + Ch12 |
| 6 Cipher | cryptanalysis (known-plaintext) | AI-easy per instance; key is random |
| 7 **Spoof** (T0856) | find a trusted-writable value, forge the operator's view | **live** — blinding the HMI is done on the running plant; how Stuxnet hid |
| 8 Culprit | forensics (stream reassembly) | AI-easy per instance |
| 9 Master | synthesis + chaining | needs full live restore + key reuse |
| 10 HMI | pivoting to a new surface + source review | AI-easy per instance; rewards looking past the console |
| 11 **Maint** (broken access control) | web exploitation + credential chaining | **chain-gated** — needs the Ch5 PIN; broken access control is real exploitation |
| 12 **Unlock** (T0858) | change operating mode to defeat a write-lock | two-step: get the key → change mode → protected write |

Every one of the twelve now maps to a real OT attack technique (MITRE ATT&CK for ICS
IDs above where applicable). The honest residual: the *decode* flags (1, 6) and the
forensics (8) are AI-soluble for a student's own instance — but the technique each
teaches is real, and the session randomisation stops copying while the live flags
(2, 3, 4, 7, 9) and the credential chain (5 → 11, 5 → 12) can't be paste-solved from a
dump. For a graded assessment, still mark a short written attack path per flag.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `start.py`: plant didn't come up | another copy running — `pkill -f waterworks_plc.py` |
| No operator display | `pip install pygame` (CTF still works without it) |
| Master won't drop | level must drain to ≤60 — ~10s; also needs dose+bypass+replay done |
| Spoof flag won't drop | the forged value must be ≥15 off the true level and in 25–75; write it while the tank is critical |
| `/diag` or `/maint` won't load | the HMI server is on port 8800 — use `http://127.0.0.1:8800/diag`, not 5020 |
| Wireshark shows raw TCP | filter `modbus`, or Decode As → Modbus/TCP port 502 |

## Pre-session check

```
python3 waterworks_plc.py &
python3 solve_test.py        # blind-solves a random instance: ALL 12 SOLVE OK
```
