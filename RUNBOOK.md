# Operation Stillwater — Organiser Runbook

Everything a committee member needs to run this session. ~2 hours, 12 flags.

**Each student's instance is randomised** — different flags, cipher key, replayable
command and engineer PIN every launch, so copying doesn't work. To give everyone the *same*
instance (or to reproduce one for marking), set `STILLWATER_SEED=<value>` before
launching. The plant prints its session id (`session abcd`) on startup.

---

## TL;DR

One command starts the whole thing:

```
pip install pygame
python3 lab.py
```

Opens the Lab Manager TUI → **Launch Operation Stillwater** → accept the warning.
The gateway boots in alarm, the operator display opens, you land in the console.
Close it (`quit`) and everything shuts down. Participants capture **twelve**
`luhack{...}` flags using the console + a browser + Wireshark + CyberChef. **No coding.**

---

## A few days before

1. On a clean laptop, run the TL;DR above. Confirm a console appears and the
   World View window shows a flooding tank.
2. Run the self-check: `python3 waterworks_plc.py &` then `python3 solve_test.py`
   → expect `ALL 12 SOLVE OK`.
3. Make sure the room has **Wireshark** installed (for Challenge 8), and point
   people at **CyberChef** (gchq.github.io/CyberChef) for the decode.
4. Share the folder with attendees in advance, or have it on USB sticks. It's
   small and needs only Python 3 (+ pygame for the visual).

## On the day

1. **Intro (15 min).** Read the briefing from `handout.md`. One line to land:
   *Modbus has no password — whoever reaches it is the operator.*
2. **Setup (10 min).** Everyone runs `python3 start.py`. It boots like a real
   plant in alarm. Float and help — most problems are in this window.
3. **Challenges (90 min).** Hand out `handout.md`. The first three are quick
   wins; 4–7 are real attacker moves (a replay attack, default credentials, a
   known-plaintext cipher, spoofing the operator's HMI); 9 is the capstone; 10–12
   add HMI source review, a web access-control exploit, and a write-protect
   bypass. Tiered hints are
   in the handout. CyberChef on hand for decoding.
4. **Wrap (10 min).** Walk the solution, show the real incidents (last slides),
   take questions.

## Timing at a glance

| Time | Phase |
| --- | --- |
| 0:00–0:15 | Intro + briefing |
| 0:15–0:25 | Setup (`python3 start.py`) |
| 0:25–1:55 | The twelve challenges (quick wins → abstract → capstone → exploitation) |
| 1:55–2:05 | Reveal + real incidents |

## Reset

Any plant misbehaving: close the console (`quit`) and run `python3 start.py`
again. State is in memory — a restart is always a clean slate.

## Troubleshooting (the four you'll actually hit)

| Problem | Fix |
| --- | --- |
| `start.py` says the plant didn't come up | Another copy is already running. Close other terminals, or `pkill -f waterworks_plc.py`, and retry. |
| No World View window | `pip install pygame`. The CTF still works without it — it's just the visual. |
| Console won't connect | Start it via `python3 start.py` (it starts the plant first). |
| Wireshark shows raw TCP, not Modbus | Filter on `modbus`, or right-click a packet → Decode As → Modbus/TCP, port 502. |

Full memory map and every flag: `organiser_answers.md`.

## What's in the folder

| File | Role |
| --- | --- |
| `start.py` | One-command launcher — this is all most people run. |
| `waterworks_plc.py` | The plant (simulated PLC). |
| `stillwater.py` | The console participants attack with. |
| `worldview.py` | The animated plant display. |
| `incident.pcap` | Challenge 4 (Wireshark). |
| `handout.md` | Give this to participants. |
| `organiser_answers.md` | Flags + answers (keep to yourself). |
| `solve_test.py` | Pre-session self-check. |
| `make_capture.py` | Regenerates the pcap if ever needed. |
