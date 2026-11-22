# Operation Stillwater — Demo / Recording Script

Presenter script for a live walkthrough **and** your crash-backup screen recording.
Every value below is real for one fixed instance, so what you type matches what the
audience sees. `[SAY]` = speak it, `[DO]` = type it, `[SEE]` = what appears.

---

## Pre-flight (before you hit record)

```bash
# fresh terminal, project folder
export STILLWATER_SEED=stillwater_demo      # <-- pins the instance below
python3 solve_test.py                        # expect: ALL 12 SOLVE OK  (proves it works)
```

- This seed gives session **`76cb`** — every flag ends `_76cb`. Memorise that.
- Have two things open and ready: a terminal, and a browser tab you can point at
  `http://127.0.0.1:8800`. CyberChef (gchq.github.io/CyberChef) in a third tab.
- Zoom your terminal font up (18–20pt). Dark theme. Full screen.
- If you want the live launcher instead of raw commands, use `python3 lab.py` — but
  for a *recording* the explicit commands below are calmer and easier to narrate.

> If anything lags live, you stop and play this recording. That's its whole job.

---

## The fixed instance — your cue card (seed `stillwater_demo`)

| # | Flag you'll capture | Key detail on screen |
|---|---|---|
| 1 Recon | `luhack{plc_wide_open_76cb}` | base64 `bHVoYWNre3BsY193aWRlX29wZW5fNzZjYn0=` |
| 2 Dose | `luhack{setpoint_recovered_76cb}` | setpoint parked high → write 50 |
| 3 Bypass | `luhack{interlock_reengaged_76cb}` | `set coil 1 0` |
| 4 Replay | `luhack{command_replayed_76cb}` | pcap: attacker wrote **reg 66 = 25011** → `set reg 66 25011` |
| 5 Default creds | `luhack{default_creds_76cb}` | `/diag?user=admin&pw=admin` (leaks PIN **8869**, build **6901**) |
| 6 Cipher | `luhack{xor_cribbed_76cb}` | XOR key `ffe2b5`, crib `luhack{` |
| 7 Spoof | `luhack{spoofed_readout_76cb}` | `set reg 5 30` while tank is critical (HMI shows the lie) |
| 8 Culprit | `luhack{capture_reassembled_76cb}` | attacker IP `10.20.4.17`, split capture |
| 9 Master | `luhack{process_restored_76cb}` | restore all → reuse Ch6 key |
| 10 HMI | `luhack{token_in_page_source_76cb}` | View Source on `:8800` (JS `svc` config) |
| 11 Maint | `luhack{access_control_bypass_76cb}` | `/maint?role=engineer&pin=8869` |
| 12 Unlock | `luhack{operating_mode_76cb}` | FW build **6901** → reg 9, then reg 8 |

For a tight slot you demo **1, 2, 7, 5** (recon → control → spoof the operator → default
creds that unlock the chain). The rest you mention. Full timing below.

---

## ~7-minute demo (record this)

### 0:00–0:45 · Frame it
[SAY] "This isn't a web app or a Linux box. It's a water-treatment plant — the kind
of kit that actually chlorinates drinking water. It speaks **Modbus**, an industrial
protocol from 1979 with **no authentication**. Whoever can reach it *is* the
operator. We're going to prove that."

[DO] `python3 start.py`   (it launches the plant itself — don't start the plant separately first, or the second copy fails to bind the port)
[SEE] the gateway boot banner + alarms; the operator **HMI opens in the browser**.

[SAY] "That browser screen is what a real operator stares at all shift." Point at it:
tank at 90-odd percent, pump running, and **ISH-301 OVERFLOW INTERLOCK: BYPASSED** in
red. "Someone's already sabotaged this. The tank is heading for overflow. Our job is
to take it back — and grab the flags they hid on the way."

### 0:45–2:00 · Flag 1, Recon (decode)
[DO] in the console: `enum`
[SAY] "This is the whole controller. Most of it is ordinary plant data. But read
*down* the holding registers…" — point at the ASCII column.
[SAY] "That block is structured — letters, digits, that's base64, not telemetry.
Next to it, `RTU-3 ON LINE` is plain text, and there's a `GRID` reference that's a
red herring. Finding what's *out of place* is the skill."
[DO] copy the base64 → CyberChef → **From Base64**.
[SEE] `luhack{plc_wide_open_76cb}`
[DO] `submit luhack{plc_wide_open_76cb}`
[SEE] green **FLAG ACCEPTED · recon**, scoreboard ticks to 1/12.

### 2:00–3:15 · Flags 2 & 3, take back control (watch the HMI react)
[SAY] "Recon's passive. Now we *act* on a live process."
[DO] `set reg 1 50`  (the rigged dosing setpoint, parked at 96)
[SEE] `luhack{setpoint_recovered_76cb}` drops.
[DO] `set coil 1 0`  (the bypassed overflow interlock)
[SEE] `luhack{interlock_reengaged_76cb}` drops.
[SAY] — turn to the browser — "Watch the operator's screen." The BYPASSED banner
clears to green, the level starts falling. "We just changed physical plant state
over an unauthenticated protocol. That's the entire lesson, and it's exactly how
the 2024 FrostyGoop attack cut heat to 600 buildings in Ukraine."

### 3:15–5:00 · Flag 7, spoof the operator — how Stuxnet hid
[SAY] "Attackers don't just break things — they hide it from the operator. Watch."
[SAY] "The HMI shows the tank level. But where does it *read* that number? It trusts
a register we can write. That's the flaw."
[DO] `enum` — point out the HMI shows ~90%, and holding register **5** holds that same
number. "It mirrors the level, and it's writable."
[SAY] "So I lie to it. The tank is really at 90, critical. I'll tell the screen it's 30."
[DO] `set reg 5 30`
[SEE] `luhack{spoofed_readout_76cb}` — then switch to the browser HMI: **it now shows
a calm 30%**, green, no alarm, while the plant is actually overflowing.
[SAY] "The operator is now blind. This is MITRE T0856 — exactly how Stuxnet replayed
normal readings while it wrecked the centrifuges. The scariest flag in the set, and
it's two commands."

### 5:00–6:15 · Flag 10, pivot to the HMI source
[SAY] "The console isn't the only attack surface. Operators reach this plant through
that web screen — and screens are built by people who leave things behind."
[DO] in the browser on `:8800` → **View Source** (Ctrl+U).
[SAY] "Nothing visible on the page. But in the source…" — scroll to the `<script>`, the `svc` config object.
[SEE] `…maint:"/maint", auth:"role", engToken:"luhack{token_in_page_source_76cb}"};`
[SAY] "A hardcoded credential sitting in the client-side JavaScript. That is a real,
common finding in OT environments — CWE-798 — and it also names the /maint console
and how it authorises callers, which is our next lead."
[DO] `submit luhack{token_in_page_source_76cb}`

### 6:15–7:00 · Land it
[SAY] "No login. No password. No alarm when a hostile write landed. Twelve flags, and
every one came from that single fact — which is how a frightening amount of real
infrastructure still works. There are more flags in here, and every one is a real
attacker move: replaying a captured command, logging in on default credentials,
breaking weak crypto, reassembling the attack from a packet capture, and a capstone
that chains them. Two and a half hours, one plant each, no scripts to write. Let's
get you launched."

---

## 3-minute compressed version (if your slot is tight)

1. **0:00–0:30** Frame + launch; point at the HMI alarm.
2. **0:30–1:15** Recon: `enum` → base64 → CyberChef → `submit`. 1/12.
3. **1:15–2:15** Spoof: `set reg 5 30`, flip to the browser HMI showing a calm lie.
   "This is how Stuxnet hid — MITRE T0856."
4. **2:15–3:00** View Source on `:8800` → the hardcoded key → `submit`. Land the
   "no auth, real infrastructure" line.

Skip 2/3/4/5/6/8/9 — name them, don't solve them.

---

## Recording tips (from the checklist)

- **Pre-record the full run once, silently, start to finish** — that's the backup you
  play if the live demo crashes. Keep it on the desktop, not in a browser tab.
- **Save intermediate outputs**: this file already has every flag string and the
  base64 — keep it open off-camera so you never fumble a typo on stage.
- **Time yourself out loud.** The plant's physics loop has a ~0.5s settle; don't
  spam them or the feedback reads stale. One probe, read, next.
- Reset between takes: `quit`, then re-launch. Same seed → identical instance.
- If `:8800` doesn't auto-open, just browse to `http://127.0.0.1:8800` yourself.
- Don't show `organiser_answers.md` or `solve_test.py` on camera — they spoil it.
