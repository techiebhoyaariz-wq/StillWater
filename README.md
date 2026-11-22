# Operation Stillwater

An OT/ICS security capture the flag,

It runs a fake but believable water treatment plant that speaks **Modbus/TCP**, the
industrial protocol from 1979 that ships with no authentication. An attacker has
sabotaged the plant: the chlorine dosing setpoint is forced out of range and the
overflow interlock is switched off, so the contact tank is heading for an overflow.
You play the responder. You get onto the controller, take back control, and piece
together what the attacker did. Everything you recover is a flag in the form
`luhack{...}`.

Twelve flags. Every one is a real OT attack technique, and most map to a MITRE ATT&CK
for ICS ID. There is no scripting. You work with a console, a web browser, Wireshark
and CyberChef.

## Why it is built the way it is

It runs entirely on your own machine on nothing but the Python standard library. No
Docker, no admin rights, no internet. That was a hard constraint. Our lab machines
are locked down, and a shared server that falls over halfway through a session ruins
it for the whole room. So every player gets a private, isolated copy on localhost and
nobody can break anyone else's.

Every launch is randomised from a seed. Your flags, the cipher key, the attacker's
replayable command, the engineer PIN and the firmware build are all different from the
next person's, so copying someone else's answer gets you nothing. If you want two
people on the same instance, or you want to reproduce one for marking, set
`STILLWATER_SEED` to any value before you start.

## Running it

```
python3 start.py
```

That boots the plant, opens the operator screen in your browser at
`http://127.0.0.1:8800`, and drops you into the attack console. Type `help` for the
command list. Type `quit` to stop.

To prove every flag is reachable, run the blind solver in a second terminal:

```
python3 waterworks_plc.py &
python3 solve_test.py
```

It finishes with `ALL 12 SOLVE OK`. The solver has no knowledge of the seed; it cracks
a fresh random instance the way a reasoning player would.

If `pip` is blocked on your machine, ignore the error. The game needs nothing outside
the standard library. The animated pygame view is the only optional extra.

## The twelve challenges

Scaffolded on purpose. The first three are quick confidence wins. Four through eight
are the core. Nine ties everything together. Ten through twelve pivot onto the web/HMI
surface and chain into each other.

| # | Challenge | Technique |
|---|-----------|-----------|
| 1 | Recon: read the unauthenticated controller and decode a token | unauthenticated read |
| 2 | Rigged dose: write the sabotaged setpoint back to safe | T0836 Modify Parameter |
| 3 | Interlock bypass: clear the forced override coil | T0855 Unauthorized Command |
| 4 | Replay attack: resend a captured privileged command | T0831 Manipulation of Control |
| 5 | Default credentials: log in to the `/diag` console on factory defaults | T0812 Default Credentials |
| 6 | The cipher: break a weak XOR with known plaintext | cryptanalysis |
| 7 | Spoof the operator: forge the HMI readout | T0856 Spoof Reporting Message |
| 8 | The culprit: reassemble the attacker's split capture | traffic forensics |
| 9 | Master override: fully restore the plant, then reuse the cipher key | synthesis |
| 10 | HMI source: find the hardcoded token in the page source | CWE-798 |
| 11 | Maintenance console: bypass the `/maint` access control | broken access control |
| 12 | Write protected: change the operating mode to defeat a write lock | T0858 Change Operating Mode |

## Documentation

- `handout.md` is what players get: the brief, the flags, and staged hints.
- `DESIGN.md` is the design brief: scenario, architecture and the reasoning behind each flag.
- `WALKTHROUGH.md` documents where every flag hides and how it is found (full spoilers).
- `organiser_answers.md` is the complete answer key with the MITRE mapping and the trap list.
- `RUNBOOK.md` is how a committee member runs a live session.

## Layout

```
waterworks_plc.py   the vulnerable Modbus PLC (all twelve flags live here)
stillwater.py       the player's attack console
hmi.html            the operator HMI web screen
monitor.py          the live security event monitor
start.py            one command launcher
lab.py              menu style launcher
worldview.py        optional animated plant view
solve_test.py       the blind solver (proof of solvability)
deck/               the workshop slides
```

## Safety

This is a deliberately insecure target. Run it on localhost only. Never expose the
Modbus port or the HMI to a real network.
