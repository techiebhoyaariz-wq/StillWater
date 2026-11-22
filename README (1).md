# Operation Stillwater

An OT/ICS security capture the flag, built for LUHack (Lancaster University's ethical
hacking society).

It runs a small but believable water treatment plant that speaks **Modbus/TCP**, the
industrial protocol from 1979 that ships with no authentication. An attacker has
sabotaged the plant: the chlorine dosing setpoint is forced out of range and the
overflow interlock is switched off, so the contact tank is heading for an overflow. You
play the responder. You get onto the controller, take back control, and piece together
what the attacker did. Everything you recover is a flag in the form `luhack{...}`.

There are twelve flags. Every one is a real OT attack technique, and most map to a MITRE
ATT&CK for ICS ID. There is no scripting. You work with a console, a web browser,
Wireshark and CyberChef.

## What you need

- **Python 3.8 or newer.** Nothing else is required to run the plant and the console.
  The whole thing is built on the Python standard library on purpose, so it runs on a
  locked down machine with no admin rights and no internet.
- **A web browser**, for the HMI operator screen and the two web based flags.
- **Wireshark**, for the forensics flag (reading the packet capture).
- **CyberChef** (the free web app at gchq.github.io/CyberChef), for decoding and the
  cipher flag. You can also use any tool you like for base64 and XOR.
- **pygame** is optional. It only powers an animated plant view and is not needed for
  any flag. If you cannot install it, ignore it.

## Get the code

On this repository page, click the green **Code** button, then **Download ZIP**, and
unzip it. Or clone it:

```
git clone https://github.com/techiebhoyaariz-wq/operation-stillwater.git
cd operation-stillwater
```

## Run it

One command starts everything:

```
python3 start.py
```

That does three things:

1. Boots the plant (the Modbus server on 127.0.0.1:5020).
2. Opens the operator HMI in your browser at http://127.0.0.1:8800. If it does not open
   on its own, just visit that address yourself.
3. Drops you into the attack console, the `stillwater>` prompt.

At the console, type `help` to see the commands, and `quit` to stop everything. To start
fresh at any time, quit and run `python3 start.py` again. The plant lives in memory, so a
restart is a clean slate.

Do not run `python3 waterworks_plc.py` and `python3 start.py` at the same time. `start.py`
launches the plant itself, so running the plant separately first just collides on the
port. The exception is the verify step below, which runs the plant on its own.

## Verify every flag is solvable

There is a blind solver that cracks a fresh random instance with no knowledge of the
seed, exactly the way a reasoning player would. It is the regression test and the proof
the challenge actually works. In a terminal:

```
python3 waterworks_plc.py &
python3 solve_test.py
```

It prints each flag as it solves it and finishes with `ALL 12 SOLVE OK`. When you are
done, stop the background plant with `kill %1` (or `pkill -f waterworks_plc.py`).

## Playing it

The console is how you interact with the controller. The commands are:

```
status                      a quick plant readout
enum                        dump all coils and registers
read <space> <addr> [n]     read registers (space is coil, input, holding or discrete)
set reg <addr> <value>      write a holding register
set coil <addr> <0 or 1>    write a coil
pcap                        notes on the incident capture file
submit <flag>               score a luhack{...} flag
score                       show what you have captured
help                        the command list
quit                        stop
```

Nothing in the plant is labelled "flag here". Finding what is out of place is part of
the work. Submit a flag with `submit luhack{...}` and the scoreboard updates.

## Reproducing an instance

Every launch is randomised from a seed, so each player's flags, cipher key, replayable
command, engineer PIN and firmware build are different, and copying another person's
answer does nothing. If you want two people on the same instance, or you want to
reproduce one for marking or for a demo, set the seed first:

```
STILLWATER_SEED=anything python3 start.py
```

The same seed always produces the same instance.

## The twelve challenges

Scaffolded on purpose. The first three are fast confidence wins. Four through eight are
the core. Nine ties everything together. Ten through twelve pivot onto the web and HMI
surface and chain into each other.

| # | Challenge | Technique |
|---|-----------|-----------|
| 1 | Recon: read the unauthenticated controller and decode a token | unauthenticated read |
| 2 | Rigged dose: write the sabotaged setpoint back to safe | T0836 Modify Parameter |
| 3 | Interlock bypass: clear the forced override coil | T0855 Unauthorized Command |
| 4 | Replay attack: resend a captured privileged command | T0831 Manipulation of Control |
| 5 | Default credentials: log in to the /diag console on factory defaults | T0812 Default Credentials |
| 6 | The cipher: break a weak XOR with known plaintext | cryptanalysis |
| 7 | Spoof the operator: forge the HMI readout | T0856 Spoof Reporting Message |
| 8 | The culprit: reassemble the attacker's split capture | traffic forensics |
| 9 | Master override: fully restore the plant, then reuse the cipher key | synthesis |
| 10 | HMI source: find the hardcoded token in the page source | CWE-798 |
| 11 | Maintenance console: bypass the /maint access control | broken access control |
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
```

## Troubleshooting

- A `pip` error that mentions "externally managed environment" is harmless. The game
  needs nothing beyond the standard library, so skip the install.
- If a launch complains that the address is already in use, an old plant is still
  running. Stop it with `pkill -f waterworks_plc.py` and start again.
- If the HMI does not open on its own, visit http://127.0.0.1:8800 in your browser.

## Safety

This is a deliberately insecure target. Run it on localhost only. Never expose the
Modbus port or the HMI to a real network.
