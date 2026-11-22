#!/usr/bin/env python3
"""
Operation Stillwater - Lab Manager (TUI launcher).

A text UI in the style of a lab VM manager: pick the challenge, read the
warning, launch. After you confirm, it boots the plant, opens the operator
display, and drops you into the console.

    python3 lab.py

Falls back to a plain launch if the terminal can't run the TUI.
"""
import curses
import datetime
import time

import start  # launch_session()

MENU = [
    ("Launch Operation Stillwater",
     "Boot the plant, open the operator display, and take the console.", "launch"),
    ("Little Formby Water Works",
     "The simulated Modbus/TCP PLC — your target machine.", "info"),
    ("Operator Display",
     "Live animated plant view (opens in its own window).", "info"),
    ("Mission Briefing",
     "Read the RICD briefing before you go in.", "brief"),
]

BRIEF = [
    "MISSION BRIEFING  -  RICD, classified",
    "",
    "Deira has seized the Little Formby Water Works. The dosing is rigged,",
    "the overflow safety is off, the tank is spilling. They've locked",
    "maintenance data inside the controller and left a cipher behind.",
    "",
    "Get in. Take back control. Crack what they hid. Recover the master",
    "override. The plant speaks Modbus - no passwords. Whoever reaches it",
    "is the operator. That is your way in.",
    "",
    "Twelve flags, format luhack{...}.  Lab use only.",
]

WARNING = [
    "AUTHORISED TRAINING USE ONLY",
    "",
    "This is a LUHack cyber security exercise. The target is a simulator",
    "on this machine, bound to 127.0.0.1. Do not point these techniques at",
    "any real system - that is illegal under the Computer Misuse Act 1990.",
    "",
    "Press ENTER to launch   ·   ESC to cancel",
]


def setup_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_MAGENTA)   # header bar
    curses.init_pair(2, curses.COLOR_CYAN, -1)                      # accents
    curses.init_pair(3, curses.COLOR_MAGENTA, -1)                   # names
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)      # selected
    curses.init_pair(5, curses.COLOR_WHITE, -1)                     # body


def hbar(stdscr, y, text, w):
    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
    stdscr.addstr(y, 0, " " * w)
    stdscr.addstr(y, 1, text[:w - 2])
    clock = datetime.datetime.utcnow().strftime("%H:%M:%S GMT")
    right = f"Press ? for help  ·  {clock} "
    stdscr.addstr(y, max(1, w - len(right) - 1), right[:w - 2])
    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)


def divider(stdscr, y, label, w):
    stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
    stdscr.addstr(y, 2, "══  " + label + "  " + "═" * max(0, w - len(label) - 12))
    stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)


def draw_menu(stdscr, sel):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    hbar(stdscr, 0, "LUHACK LAB MANAGER", w)
    stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
    stdscr.addstr(1, 2, "STILLWATER")
    stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
    stdscr.addstr(1, 14, "OT Security Assessment", curses.color_pair(5) | curses.A_DIM)
    divider(stdscr, 3, "FIELD DEPLOYMENT", w)

    y = 5
    for i, (name, desc, _) in enumerate(MENU):
        if i == sel:
            stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
            stdscr.addstr(y, 2, "▶ ")
            stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
            stdscr.addstr(y, 4, " " + name + " ")
            stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
        else:
            stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(y, 4, name)
            stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(y + 1, 4, desc[:w - 6], curses.color_pair(5) | curses.A_DIM)
        y += 3

    stdscr.addstr(h - 2, 2,
                  "↑/↓ navigate   enter: select   q: quit",
                  curses.color_pair(5) | curses.A_DIM)
    stdscr.refresh()


def box(stdscr, lines, w, h):
    bw = min(w - 6, max(len(s) for s in lines) + 6)
    bh = len(lines) + 4
    x0 = (w - bw) // 2
    y0 = max(4, (h - bh) // 2)
    for dy in range(bh):
        stdscr.addstr(y0 + dy, x0, " " * bw, curses.color_pair(5))
    stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
    stdscr.addstr(y0, x0, "┌" + "─" * (bw - 2) + "┐")
    stdscr.addstr(y0 + bh - 1, x0, "└" + "─" * (bw - 2) + "┘")
    for dy in range(1, bh - 1):
        stdscr.addstr(y0 + dy, x0, "│")
        stdscr.addstr(y0 + dy, x0 + bw - 1, "│")
    stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
    for i, line in enumerate(lines):
        attr = curses.color_pair(2) | curses.A_BOLD if i == 0 else curses.color_pair(5)
        stdscr.addstr(y0 + 2 + i, x0 + 3, line[:bw - 6], attr)
    stdscr.refresh()


def screen(stdscr, lines):
    """Show a boxed screen; ENTER returns True, ESC/q returns False."""
    stdscr.nodelay(False)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        hbar(stdscr, 0, "LUHACK LAB MANAGER", w)
        box(stdscr, lines, w, h)
        k = stdscr.getch()
        if k in (10, 13, curses.KEY_ENTER):
            return True
        if k in (27, ord("q")):
            return False


def tui(stdscr):
    curses.curs_set(0)
    setup_colors()
    stdscr.nodelay(True)
    stdscr.timeout(500)
    sel = 0
    while True:
        draw_menu(stdscr, sel)
        k = stdscr.getch()
        if k == -1:
            continue
        if k in (curses.KEY_UP, ord("k")):
            sel = (sel - 1) % len(MENU)
        elif k in (curses.KEY_DOWN, ord("j")):
            sel = (sel + 1) % len(MENU)
        elif k in (10, 13, curses.KEY_ENTER):
            action = MENU[sel][2]
            if action == "brief":
                screen(stdscr, BRIEF)
            elif action == "info":
                screen(stdscr, ["COMPONENT", ""] + [MENU[sel][1]])
            elif action == "launch":
                if screen(stdscr, WARNING):
                    return True
            stdscr.nodelay(True)
            stdscr.timeout(500)
        elif k in (ord("q"),):
            return False


def main():
    launch = False
    try:
        launch = curses.wrapper(tui)
    except Exception:
        # No TTY / tiny terminal / no curses: just launch plainly.
        launch = True
    if launch:
        start.launch_session()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
