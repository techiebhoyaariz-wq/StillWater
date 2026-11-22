# Operation Stillwater: Design Brief

*A pre-read for reviewers. About a ten minute read. The full answer key is in
`organiser_answers.md`, the per flag walkthrough is in `WALKTHROUGH.md`, and the blind
solver that proves solvability is `solve_test.py`.*

## TL;DR

An intermediate OT/ICS security CTF. It is a deliberately insecure Modbus/TCP water
treatment plant, simulated on localhost in pure Python (standard library only, because
it had to run on a locked down university VDI with no Docker and no admin rights).
Twelve flags, each mapped to a real OT attack technique, most with a MITRE ATT&CK for
ICS ID. Every launch is randomised per student, and a blind solver proves all twelve
are solvable from observation alone. Target length is about 2.5 hours, and no scripting
is required. Players use a console, a browser, Wireshark and CyberChef.

## Scenario

The framing comes from our society's house universe (two factions, Rheged versus
Deira). The attacker, Deira, has compromised the Little Formby Water Works contact tank
controller. They forced the chlorine dosing setpoint out of range and bypassed the
overflow interlock, so the tank is heading for an overflow. The player is the incident
responder who has to get onto the PLC, take back control, and reconstruct what the
attacker did. The flags are the artefacts you collect along the way.

An operator HMI, served over HTTP, shows the plant live (tanks, pumps, alarms, a P&ID)
and reacts in real time as the player attacks and restores the process. A separate ops
monitor streams a security event log. The point is that the player sees and feels the
cyber physical consequences rather than reading a CLI in isolation.

## Architecture and constraints

- Pure Python standard library. The PLC is a hand rolled Modbus/TCP server, the HMI is
  an `http.server`, and the only optional dependency is pygame for an animated view.
- One isolated instance per player, localhost only. There is no shared server to fall
  over mid session, which is a problem our society has hit before. Nothing is exposed
  to the network.
- Per session randomisation. A seed (random, or `STILLWATER_SEED` for reproducible
  marking) derives every flag, the cipher key, the attacker's replayable command, the
  engineer PIN and the firmware build. Flags look like `luhack{<base>_<session id>}`,
  so no two players share answers.
- No code. Everything is solvable with the provided console, a browser, Wireshark and
  CyberChef. No exploit scripting, which suits a mixed ability society session.

## The twelve challenges

Scaffolded on purpose. Flags 1 to 3 are fast confidence wins, 4 to 8 are the core, 9 is
a synthesis capstone, and 10 to 12 pivot onto the web and HMI surface and chain into
each other.

| # | Name | Technique (MITRE ICS or class) | Intended solve path |
|---|------|--------------------------------|---------------------|
| 1 | Recon | unauthenticated read | `enum` the controller, spot a base64 token among plausible register noise, decode it |
| 2 | Rigged dose | T0836 Modify Parameter | write the dosing setpoint register back into the safe band |
| 3 | Interlock bypass | T0855 Unauthorized Command | clear the overflow interlock coil the attacker forced on |
| 4 | Replay attack | T0831 Manipulation of Control | find the attacker's privileged command in the pcap and resend it to the live PLC |
| 5 | Default credentials | T0812 Default Credentials | the HMI source names a `/diag` console, it is on factory defaults, log in and it over shares the PIN and build |
| 6 | The cipher | cryptanalysis (known plaintext) | a flag XORed with a 3 byte key, the crib `luhack{` recovers the key |
| 7 | Spoof the operator | T0856 Spoof Reporting Message | the HMI reads its level from a writable register, forge a calm value while the plant is critical |
| 8 | The culprit | forensics (traffic analysis) | the attacker's base64 is split across writes with a benign poller on the wire, filter, follow the stream, reassemble, decode |
| 9 | Master override | synthesis and chaining | drops only when the plant is fully restored, returned enciphered with the flag 6 key, reuse it |
| 10 | HMI source secret | CWE-798 hardcoded credential | a hardcoded engineer token in the client side JS, found by reading page source, also names `/maint` |
| 11 | Maintenance console | broken access control | `/maint` trusts a client supplied `?role=`, escalate, then supply the PIN from flag 5 |
| 12 | Write protect bypass | T0858 Change Operating Mode | a register is write locked in RUN mode, write the firmware build to the command register to enter MAINT, then the protected write lands |

Chains: flag 5 (`/diag`) hands out the PIN that flag 11 needs and the build that flag 12
needs, so it is a deliberate hub. Flag 9 requires flags 2, 3 and 4 done and reuses the
flag 6 key.

## Design principles, and where I tried to be honest

- Anti copy and AI resistance. Per session randomisation means a pasted flag or an AI
  answer from another student's dump does not transfer. The live flags (2, 3, 4, 7, 9)
  must be performed against the running plant, and the credential chain (5 into 11, 5
  into 12) cannot be shortcut from a static dump.
- Honest limitation. Flags 1, 6 and 8 are decode or analyse by nature, so an AI can help
  a student solve their own instance. I accepted that. Each still teaches a real
  technique, and for grading I ask for a one line written attack path per flag, where
  understanding rather than paste shows.
- Unintended solution audit. The main hole in any local CTF is that players have the
  source. I mitigated it. Flag bases are base64 obfuscated in the source so they are not
  greppable as `luhack{...}`, and everything is per session. There is a decoy flag and a
  honeypot coil to test judgement.
- Validation. `solve_test.py` is a blind solver. It cracks a fresh random instance with
  no seed knowledge, the way a reasoning player would, and asserts all twelve. It is my
  regression test and my proof the challenge is actually solvable.

## Run and verify (two commands)

```
python3 start.py
python3 waterworks_plc.py & python3 solve_test.py
```

The first boots the plant, opens the HMI, and drops you in the console. The second runs
the blind solver and should print `ALL 12 SOLVE OK`. Set `STILLWATER_SEED` first to pin
a reproducible instance, handy if we want to look at the same one in the meeting.

## What I would most value your view on

1. Difficulty curve. Is the scaffolding right for a 2.5 hour intermediate session, or is
   the back third too steep?
2. Realism. Do any flags still read as contrived rather than a real attacker move? I
   replaced three earlier puzzle flags with the replay, default creds and spoof
   techniques for exactly this reason.
3. Unintended solutions. Anything you would expect players to shortcut that I have not
   closed.
4. What you would cut. I would rather have nine tight flags than twelve with filler.
