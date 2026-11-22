# Operation Stillwater — Hacking the Physical World

An OT / ICS security capture-the-flag for LUHack. You attack a simulated
water-treatment plant over **Modbus/TCP** — a real industrial protocol with no
authentication. Clone it, run one command, and the plant **boots up in alarm and
hands you the controls**, like a live system under attack.

- **12 flags**, each a real OT attack technique (mapped to MITRE ATT&CK for ICS):
  unauthenticated recon, setpoint/interlock manipulation, a **replay attack** (T0831),
  **default credentials** (T0812) on an engineering console, known-plaintext crypto,
  **spoofing the operator's HMI** (T0856), stream-reassembly forensics, a synthesis
  capstone, hardcoded secrets in HMI source, **broken access control** on `/maint`,
  and a **change-operating-mode** write-protect bypass (T0858).
- **Randomised per launch** — flags, cipher key, the replayable command and PIN differ
  every run, so copying is pointless and there's nothing to look up. Set
  `STILLWATER_SEED` to reproduce an instance for marking.
- **No coding.** Players use a console, a browser, Wireshark, and CyberChef.
- **One instance per player**, localhost only. Nothing shared, nothing exposed.
- A live **operator HMI** in the browser (`http://127.0.0.1:8800`) and an animated
  plant view, so you watch the tank flood on the real operator's screen — and calm
  it as you win.

Animated plant view inspired by [VirtuaPlant](https://github.com/jseidl/virtuaplant)
(GPLv2), rewritten for Python 3 with pygame.

---

## Quickstart

```bash
git clone <your-repo-url> operation-stillwater
cd operation-stillwater
pip install pygame
python3 lab.py
```

`lab.py` opens the **Lab Manager** — a TUI like the lab VM manager. Select
**Launch Operation Stillwater**, accept the warning, and the gateway boots, the
operator display opens, and you drop into the console. Type `help`; `quit` shuts
it all down. (Prefer no menu? `python3 start.py` launches straight away.)

> **Lab only.** Binds to `127.0.0.1`. These techniques are illegal against real
> systems (Computer Misuse Act 1990). Attack the simulator, nothing else.

---

## The challenges

| # | Challenge | What it tests |
| --- | --- | --- |
| 1 | Recon — read the unauthenticated controller, decode the access token | encoding recognition |
| 2 | The rigged dose — fix the sabotaged setpoint | control manipulation |
| 3 | The bypass — restore the overflow interlock | control manipulation |
| 4 | Replay a captured privileged command (T0831) | capture analysis / replay |
| 5 | Default credentials on the `/diag` console (T0812) | credential attack |
| 6 | The cipher — known-plaintext XOR | cryptanalysis |
| 7 | Spoof the operator's HMI readout (T0856) | reporting-message spoof |
| 8 | The culprit — reassemble the split capture | forensics |
| 9 | Master override — restore everything | synthesis / chaining |
| 10 | The operator's screen — hardcoded token in the HMI source | source review / surface pivot |
| 11 | Maintenance console — bypass `/maint` access control, chain the PIN | web exploitation / chaining |
| 12 | Write-protected — bypass the RUN-mode write-lock (T0858) | protocol / operating-mode |

Players get `handout.md`. Organisers get `organiser_answers.md` and `RUNBOOK.md`.

---

## What's in here

| File | Role |
| --- | --- |
| `lab.py` | Lab Manager TUI — pick the challenge, launch it. |
| `start.py` | Direct launcher — boot, display, console (no menu). |
| `waterworks_plc.py` | The simulated PLC (standard library only). |
| `stillwater.py` | The field console players attack with. |
| `monitor.py` | Live operations monitor — a SCADA screen that reacts to your attacks (opens in its own window). |
| `hmi.html` | The operator HMI — an SVG P&ID served by the plant at `:8800`, polling live state (Challenge 10 lives in its source). |
| `worldview.py` | Optional animated plant display (needs pygame). |
| `incident.pcap` | The Wireshark challenge (regenerated per session by the plant). |
| `handout.md` | Give to participants. |
| `RUNBOOK.md` | Run-the-session guide for organisers. |
| `organiser_answers.md` | Flags, memory map, cognitive design, AI-resistance. |
| `solve_test.py` | Pre-session self-check — blind-solves a random instance. |
| `requirements.txt` | pygame pin (the plant and console need nothing). |

## Verify it works

```bash
python3 waterworks_plc.py &
python3 solve_test.py        # expect: ALL 12 SOLVE OK
```

## Requirements

Python 3.8+ and `pygame` (for the display only — the CTF runs without it).
