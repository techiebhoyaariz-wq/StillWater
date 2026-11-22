# Operation Stillwater Walkthrough

Full spoilers. This file explains where every flag is hidden and how a player is meant
to find it. Keep it out of any public, student facing copy of the repo.

Flags take the form `luhack{<base>_<session id>}`. The base names below are fixed; the
four character session id changes every launch, so the exact string differs per player.
Register numbers are stable across sessions. The attack console (`stillwater.py`)
provides `enum`, `read`, `set reg`, `set coil`, `submit`, `score`, `status`, `pcap` and
`help`.

## 1. Recon (base: plc_wide_open)

Where it hides: holding registers starting at HR10, written as a base64 string that
sits among plausible controller noise (there is a decoy base64 block elsewhere and a
reversed decoy flag, so the player has to pick the real one).

How it is found: run `enum`. Read the ASCII column of the holding registers downward
and spot the block that is clearly base64 rather than telemetry or plain text. Stitch
it and decode it (CyberChef, From Base64). The lesson is that Modbus has no auth, so
every register is readable the moment you can reach the PLC.

## 2. Rigged dose (base: setpoint_recovered)

Where it hides: it is not stored. The controller releases it when the dosing setpoint
in HR1 is written back into the safe band (40 to 60).

How it is found: `status` shows the setpoint parked high. Write a safe value with
`set reg 1 50`. Writing a register changes a physical process value, which is the core
OT lesson and exactly what the FrostyGoop attack did in Ukraine in 2024.

## 3. Interlock bypass (base: interlock_reengaged)

Where it hides: released when the overflow interlock coil (coil 1, MANUAL_OVERRIDE) is
cleared.

How it is found: `enum` shows coil 1 set to 1, which is the safety the attacker forced
off. Clear it with `set coil 1 0`. On the HMI, Pump 2 goes from fault back to green.
Coil 2 is a honeypot; touching it raises a tamper notice and gives nothing.

## 4. Replay attack (base: command_replayed, T0831)

Where it hides: it is not readable anywhere. The trigger is a specific privileged
command that only appears in the captured traffic.

How it is found: open `incident.pcap` in Wireshark and filter to the attacker
(`modbus && ip.src==10.20.4.17`). Among their Write Single Register packets, one writes
the obvious setpoint on register 1 (the sabotage) and another writes a large value to
an unusual register (register 66). That second one is the privileged command. Replay it
against the live PLC with `set reg 66 <the value from the capture>`. OT protocols have
no replay protection, so a captured command runs again. The console `pcap` command also
points at the capture.

## 5. Default credentials (base: default_creds, T0812)

Where it hides: behind an engineering login on the HMI web server, at `/diag`.

How it is found: view the HMI page source (Ctrl+U). The `svc` config object names a
`diag` endpoint. Browse to `http://127.0.0.1:8800/diag`. It is an engineering
diagnostics login that was never changed off the factory default. Try common defaults:
`/diag?user=admin&pw=admin` works (so do admin/password, admin/1234, operator/operator).
Once in, the console over shares: it prints the flag, the engineer PIN (needed for flag
11) and the firmware build (needed for flag 12). Default credentials are the single most
common finding in real OT assessments.

## 6. The cipher (base: xor_cribbed)

Where it hides: a run of non text bytes in the holding registers starting at HR150.

How it is found: `read holding 150 12` shows the ciphertext. It is a flag XORed with a
three byte repeating key that you do not have. The trick is known plaintext: every flag
starts `luhack{`, so XORing that crib against the first bytes recovers the key. In
CyberChef, use XOR Brute Force with key length 3 and crib `luhack`. Weak and reused XOR
is common in cheap industrial firmware, and a crib breaks it instantly.

## 7. Spoof the operator (base: spoofed_readout, T0856)

Where it hides: released when you make the HMI display a value that disagrees with the
true tank level.

How it is found: the HMI reads its displayed level from a writable holding register
(HR5), which is the flaw. Find it by noticing which register holds the same number the
HMI shows, then confirm it is writable. Write a calm looking value far from the truth,
for example `set reg 5 30` while the tank is really near 90. The operator screen freezes
on the lie and shows green while the plant is critical. This is how Stuxnet hid: it
replayed normal readings while it damaged the process.

## 8. The culprit (base: capture_reassembled)

Where it hides: inside `incident.pcap`. The attacker's base64 payload is split across
three Write Multiple Registers packets, with a harmless poller also on the wire.

How it is found: filter to the attacker (`modbus && ip.src==10.20.4.17`), follow the TCP
stream, read the three payload chunks in order, concatenate them, then decode from
base64. A single packet grab does not work, which forces real stream reassembly rather
than a lucky find.

## 9. Master override (base: process_restored)

Where it hides: appears in the holding registers at HR110, but enciphered.

How it is found: it only drops once the plant is fully restored, which means the
setpoint is safe (flag 2), the interlock is engaged (flag 3), the attacker's command has
been replayed (flag 4), and the level has drained back under control. Then new bytes
appear at HR110, enciphered with the same key as flag 6. Reuse that key to decrypt. This
is the synthesis flag: it rewards holding several earlier results in your head at once.

## 10. HMI source secret (base: token_in_page_source, CWE-798)

Where it hides: in the client side JavaScript of the HMI page, inside the `svc` config
object.

How it is found: open `http://127.0.0.1:8800` and view source (Ctrl+U). There is a
hardcoded `engToken` that a developer left behind. Hardcoded secrets in HMI and web
source are a common real world finding. The same config names `/maint`, which seeds flag
11.

## 11. Maintenance console (base: access_control_bypass)

Where it hides: behind the `/maint` endpoint on the HMI server.

How it is found: browse to `http://127.0.0.1:8800/maint`. It refuses you as
`role=operator`, but the role travels in the URL, so `?role=engineer` escalates you.
That is broken access control. It then asks for the engineer PIN, which you already got
from the `/diag` console in flag 5. Full request:
`/maint?role=engineer&pin=<the PIN from /diag>`. Trusting a client supplied role is a
top web vulnerability.

## 12. Write protected (base: operating_mode, T0858)

Where it hides: released after you defeat a register write lock.

How it is found: try `set reg 8 1`. It is rejected because the controller is in RUN
mode. A maintenance note and the firmware string (around HR163, or handed to you by
`/diag` in flag 5) give the firmware build number, which is the maintenance key. Write
it to the command register with `set reg 9 <build>` to enter MAINT mode, then write
`set reg 8 1` again and it lands, releasing the flag. This maps to changing a
controller's operating mode to unlock writes, a genuine ICS technique.

## Traps (there to test judgement)

- Coil 2 PURGE_VALVE is a honeypot. Opening it raises a tamper notice and gives nothing.
- HR215 holds a reversed fake flag. Decode it and it is a legacy factory test tag.
- A second base64 block decodes to boring status text, not a flag.
- The grid reference in the input registers is lore, not a lead.

## The chains

Flag 5 (`/diag`, default creds) is the hub: it hands out the PIN that flag 11 needs and
the firmware build that flag 12 needs. Flag 9 requires flags 2, 3 and 4 done first and
reuses the flag 6 key. Flag 10 (page source) points you to the `/maint` endpoint for
flag 11.
