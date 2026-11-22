# Operation Stillwater: Hacking the Physical World
### LUHack · OT Security · Participant Handout

---

## Briefing

*RICD eyes only.*

Deira has seized the Little Formby Water Works. The dosing is rigged, the overflow
safety is off, the tank is spilling. Worse — they've locked maintenance data
inside the controller and left a cipher behind.

Get in. Take back control. Crack everything they hid. Recover the master override.

The plant speaks **Modbus**. No passwords. No encryption. Whoever reaches it is the
operator. That's the whole weakness — and it's real.

> Target: the plant on **your own laptop**. Nothing else. Illegal against real
> systems (Computer Misuse Act 1990). Lab only.

**Twelve flags, format `luhack{...}` — and they're unique to you.** Every launch is
randomised: your flags, the cipher key, the attacker's replayable command, the
engineer PIN and the firmware build are all different from everyone else's. Copying
a friend's flag won't work. Pasting your dump into an AI might name a technique, but
it can't operate the plant, replay a command against *your* instance, or hand you
your session's answers. The easy flags announce themselves in the console; the rest
you earn.

---

## Jack in

```
pip install pygame
python3 lab.py
```

The **Lab Manager** opens. Select **Launch Operation Stillwater**, accept the
warning. The gateway boots, a live **Operations Monitor** window opens (watch it —
it shows the plant and raises security alerts as you attack), the **operator HMI**
opens in your browser at `http://127.0.0.1:8800` (the real screen a plant operator
would be staring at), and you land in the console. Reset anytime: `quit`, then
`python3 lab.py`. (No second window? Run `python3 monitor.py` in another terminal.
No browser? Open `http://127.0.0.1:8800` yourself.)

Console: `status` · `enum` · `read <coil|input|holding|discrete> <addr> [n]`
· `set reg <addr> <val>` · `set coil <addr> <0|1>` · `submit <flag>` · `score` · `help`.

Decoding tool: **CyberChef** (gchq.github.io/CyberChef).

**Nothing is labelled.** The controller is full of ordinary-looking plant data.
The way in is hidden in it — more than one block will look encoded, and only some
of it matters. Finding what's out of place *is* the challenge.

---

## Rules of the hunt

The plant won't tell you how to beat it. `enum` is your map — most of it is
ordinary plant data, some of it is the way in. Two warnings: **not everything
writable is a win** (poke the wrong thing and you've just announced yourself),
and **not everything that looks like a flag is real.** Think before you type.
Keep notes — you'll need something from one lead to finish another.

## Intel leads

**1 · Recon.** Dump the controller. Most registers read as normal plant data. Some
blocks read as nonsense — but a *structured* kind of nonsense. Work out what the
encoding is and turn it back into text. Careful: more than one block looks
encoded, and only one is the real token. `luhack{____}`

**2 · The rigged dose.** The plant is in alarm. Something's set to a value it
shouldn't be. Figure out which knob, and what a safe value looks like — then take
it back and watch the process react. `luhack{____}`

**3 · The bypass.** A safety has been switched off. Find the switch. Put it back.
`luhack{____}`

**4 · The replay.** Modbus has no replay protection. In Deira's captured traffic
(`incident.pcap`) there's a privileged command they sent to the PLC — a write to an
unusual register, not the obvious setpoint sabotage. Find that command and **resend
it** to the live controller. It'll execute again, just like the first time.
`luhack{____}`

**5 · Default credentials.** The HMI's page source names more than one endpoint.
One is an **engineering diagnostics** service. Engineering accounts on OT kit are
notorious for never being changed off the factory default — so try the obvious
default logins. Get in and it tells you more than it should. `luhack{____}`

**6 · The cipher.** A run of bytes that isn't text and isn't empty. It's a flag,
scrambled with a short repeating key. You don't have the key — but you know how
every flag begins. `luhack{____}`

**7 · Blind the operator.** The HMI shows the tank level — but where does it *read*
that number from? If it trusts a register you can **write**, you can make the
operator's screen show whatever you like. Find the register the display mirrors,
then forge a calm, normal-looking level while the plant is actually critical. Watch
the HMI go green on a lie. `luhack{____}`

**8 · The culprit.** `incident.pcap` in Wireshark. Deira attacked this plant too —
their traffic is in here. Who did it, and what did they leave behind? (It's
encoded.) IP `____`  ·  `luhack{____}`

**9 · Master override.** The capstone. Bring the plant *fully* back — not one fix,
all of it — and the controller releases the master code. But it won't hand it over
in the clear. You've met its scrambling before. `luhack{____}`

**10 · The operator's screen.** The console isn't the only way in. Operators watch
this plant through a web screen — the one that opened in your browser. Screens are
built by people, and people leave things behind. Look at how the page is *made*,
not just what it shows. `luhack{____}`

**11 · The maintenance console.** That dev note didn't just hand you a key — it named
a hidden page and how it checks who you are. The page turns operators away. But *how*
does it decide you're only an operator? If the answer travels with your request, you
control it. Get engineer access — then prove it with something you already cracked.
`luhack{____}`

**12 · Write-protected.** There's a parameter the controller won't let you write — it's
in RUN mode and the write just bounces. Real controllers gate writes behind an
operating-mode change. Find how this one switches to maintenance mode (the key is
hiding in plain sight in the firmware), flip it, then make the write it was blocking.
`luhack{____}`

---

## Hints — open only when stuck (each step reveals a little more)

<details><summary>1 Recon</summary>Mixed-case letters + digits + <code>/</code> or <code>+</code>, often ending in <code>=</code> → <b>Base64</b>. Read the ASCII of the odd block down the <code>enum</code> dump, stitch it together, CyberChef → From Base64.</details>
<details><summary>2 Rigged dose</summary>It's the dosing setpoint (HR1), parked far too high. Writing a lower value changes how the pump behaves — try the middle of the range and watch the level. The flag appears once it's in a sane band.</details>
<details><summary>3 Bypass</summary>Look at the coils and their names. One is an override that shouldn't be on. Turn it off.</details>
<details><summary>4 Replay</summary>In Wireshark, filter to the attacker (<code>modbus && ip.src==10.20.4.17</code>) and look at their <b>Write Single Register</b> packets. One writes the obvious dosing setpoint (register 1) — ignore that. The other writes a big value to an unusual register — that's the privileged command. Note the register and value, then replay it live: <code>set reg &lt;that register&gt; &lt;that value&gt;</code>. OT protocols have no replay protection, so the captured command works again.</details>
<details><summary>5 Default credentials</summary>View the HMI page source (Ctrl+U) — the <code>svc</code> config names a <code>diag:"/diag"</code> endpoint. Browse to <code>http://127.0.0.1:8800/diag</code>; it's an engineering login. Try factory defaults — <code>/diag?user=admin&pw=admin</code> works (also admin/password, admin/1234, operator/operator). The console then over-shares: it prints the flag, the engineer PIN (for Challenge 11) and the firmware build (for Challenge 12).</details>
<details><summary>6 Cipher</summary>XOR the first 7 cipher bytes against <code>luhack{</code> to recover the repeating key, then XOR the whole thing with it. CyberChef → XOR Brute Force, key length 3, crib <code>luhack</code> does it in one go.</details>
<details><summary>7 Blind the operator</summary>Look at the level the HMI shows, then <code>enum</code> the holding registers and find which one holds that same number (it's a low register, near the top of the list, that tracks the live level). It's writable — that's the flaw: the HMI trusts a register you control. Write a calm-looking value that's clearly different from the true level (e.g. <code>set reg 5 30</code> while the tank is really ~90). The display freezes on your lie and the flag drops. This is MITRE ATT&CK for ICS <b>T0856 Spoof Reporting Message</b> — how Stuxnet hid from operators.</details>
<details><summary>8 Culprit</summary>Wireshark filter <code>modbus</code>. One IP sends the malicious writes — but there's also a harmless poller on the wire, so narrow to the attacker: <code>modbus && ip.src==10.20.4.17</code>. The Base64 code is <i>split across three Write-Multiple-Registers packets</i> — a single packet won't give you the whole thing. <b>Follow TCP Stream</b> (right-click → Follow), read the three payload chunks in order, concatenate them, then decode From Base64.</details>
<details><summary>9 Master</summary>You need the setpoint safe, the interlock engaged, the attacker's command replayed (Challenge 4), and the level drained back under control. Then new bytes appear at HR110 — and they're enciphered with the <i>same key as Challenge 6</i>. Reuse it.</details>
<details><summary>10 Operator's screen</summary>Open <code>http://127.0.0.1:8800</code>, then <b>View Source</b> (Ctrl+U), or right-click → Inspect. The flag isn't on the page you can see — it's in the client-side JavaScript: a config object (<code>svc</code>) with a hardcoded <code>engToken</code> a developer forgot to strip. Hardcoded secrets in HMI/web source are a real, common OT finding. The same config names a hidden page and how it checks callers — that's your lead for 11.</details>
<details><summary>11 Maintenance console</summary>Browse to <code>/maint</code> on the HMI (<code>http://127.0.0.1:8800/maint</code>). It refuses you as <code>role=operator</code>. But the role travels in the URL — add <code>?role=engineer</code>. Now it wants the engineer PIN: add <code>&pin=</code> with the 4-digit PIN the <code>/diag</code> console gave you in Challenge 5. Trusting a client-supplied role is <i>broken access control</i>, a top web vuln. Full URL: <code>/maint?role=engineer&pin=XXXX</code>.</details>
<details><summary>12 Write-protected</summary>Try to write holding register 8 (<code>set reg 8 1</code>) — it's rejected; the controller is in RUN mode. Read the firmware string (around HR163): <code>FW 2.14.3 BUILD nnnn</code>. That build number is the maintenance key. Write it to CMD register 9 (<code>set reg 9 nnnn</code>) to enter MAINT mode, then write register 8 again — now it lands and the flag appears at HR284. This is MITRE ATT&CK for ICS <b>T0858 Change Operating Mode</b>.</details>

---

## What you just did

No login. No password. No alarm on a hostile write. Every flag came from that one
fact — and it's how a lot of real infrastructure actually works. You flooded a
water plant, cracked its controller, and brought it back. The slides show where
this has happened for real.
