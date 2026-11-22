#!/usr/bin/env python3
"""
Operation Stillwater - World View
Little Formby Water Works, live animated plant.

Inspired by VirtuaPlant (jseidl/virtuaplant, GPLv2) — the idea that you should
SEE your attack hit the physical process. Rewritten for Python 3 with no physics
engine, no GTK, no Twisted: only pygame. It is a Modbus CLIENT that reads the
real plant state from waterworks_plc.py and draws it.

Run (after the plant is up):
    pip install pygame
    python3 worldview.py

Attack the plant from a third terminal and watch this window react.
Press ESC or close the window to quit.
"""
import socket
import struct
import sys
import math
import random
import pygame

PLANT_HOST = "127.0.0.1"
PLANT_PORT = 5020
W, H = 920, 580
FPS = 50

# ---- minimal Modbus/TCP client (stdlib only, so this needs only pygame) ----
class Plant:
    def __init__(self):
        self.sock = None
        self.txn = 0

    def connect(self):
        try:
            self.sock = socket.create_connection((PLANT_HOST, PLANT_PORT), timeout=1)
            self.sock.settimeout(1)
            return True
        except OSError:
            self.sock = None
            return False

    def _req(self, pdu):
        self.txn = (self.txn + 1) & 0xFFFF
        frame = struct.pack(">HHHB", self.txn, 0, len(pdu) + 1, 1) + pdu
        self.sock.sendall(frame)
        head = self._recvn(7)
        length = struct.unpack(">HHHB", head)[2]
        return self._recvn(length - 1)

    def _recvn(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise OSError("closed")
            buf += chunk
        return buf

    def read_input_reg(self, addr):
        resp = self._req(struct.pack(">BHH", 4, addr, 1))
        return struct.unpack(">H", resp[2:4])[0]

    def read_holding_reg(self, addr):
        resp = self._req(struct.pack(">BHH", 3, addr, 1))
        return struct.unpack(">H", resp[2:4])[0]

    def read_coils(self, addr, count):
        resp = self._req(struct.pack(">BHH", 1, addr, count))
        bits = resp[2]
        return [(bits >> i) & 1 for i in range(count)]


# ---- palette ----
BG = (14, 27, 36)
PANEL = (19, 37, 47)
INK = (232, 238, 242)
MUTED = (144, 164, 176)
LINE = (42, 63, 74)
AMBER = (242, 166, 59)
CYAN = (77, 182, 196)
WATER = (46, 120, 170)
WATER_HI = (72, 150, 200)
DANGER = (226, 87, 76)
GOOD = (91, 189, 127)

# tank geometry
TANK_X, TANK_Y, TANK_W, TANK_H = 150, 150, 320, 330
RIM_Y = TANK_Y


def draw(screen, fonts, level, setpoint, pump, override, droplets, spills, t):
    big, med, small, mono, monob = fonts
    screen.fill(BG)

    # title
    screen.blit(monob.render("LITTLE FORMBY WATER WORKS", True, INK), (40, 34))
    screen.blit(small.render("World View · Operation Stillwater", True, MUTED), (40, 70))

    # --- the tank ---
    pygame.draw.rect(screen, PANEL, (TANK_X, TANK_Y, TANK_W, TANK_H))
    # water
    wh = int(TANK_H * level / 100.0)
    wy = TANK_Y + TANK_H - wh
    if wh > 0:
        # dosing tint shifts with pump activity
        pygame.draw.rect(screen, WATER, (TANK_X, wy, TANK_W, wh))
        pygame.draw.rect(screen, WATER_HI, (TANK_X, wy, TANK_W, max(4, int(6 + 3 * math.sin(t * 0.2)))))
    # tank walls
    pygame.draw.rect(screen, LINE, (TANK_X, TANK_Y, TANK_W, TANK_H), 3)

    # setpoint marker
    sy = TANK_Y + TANK_H - int(TANK_H * min(setpoint, 100) / 100.0)
    for x in range(TANK_X, TANK_X + TANK_W, 16):
        pygame.draw.line(screen, AMBER, (x, sy), (x + 8, sy), 2)
    screen.blit(small.render(f"setpoint {setpoint}", True, AMBER), (TANK_X + TANK_W + 12, sy - 10))

    # dosing pipe + droplets
    pipe_x = TANK_X + TANK_W // 2
    pygame.draw.rect(screen, LINE, (pipe_x - 12, 96, 24, TANK_Y - 96))
    pygame.draw.rect(screen, CYAN if pump else LINE, (pipe_x - 12, 96, 24, 10))
    for d in droplets:
        pygame.draw.circle(screen, WATER_HI, (int(d[0]), int(d[1])), 4)

    # overflow spill
    for s in spills:
        pygame.draw.circle(screen, WATER_HI, (int(s[0]), int(s[1])), 3)

    # --- pump indicator ---
    px, py = TANK_X - 70, TANK_Y + TANK_H - 40
    pygame.draw.circle(screen, LINE, (px, py), 28, 3)
    col = GOOD if pump else MUTED
    ang = t * 0.4 if pump else 0
    for k in range(3):
        a = ang + k * 2.094
        pygame.draw.line(screen, col, (px, py),
                         (px + 22 * math.cos(a), py + 22 * math.sin(a)), 4)
    screen.blit(small.render("PUMP", True, col), (px - 24, py + 36))

    # --- right status panel ---
    rx = 560
    pygame.draw.rect(screen, PANEL, (rx, 150, 320, 330), border_radius=10)
    pygame.draw.rect(screen, LINE, (rx, 150, 320, 330), 2, border_radius=10)

    def row(y, label, value, vcol):
        screen.blit(small.render(label, True, MUTED), (rx + 24, y))
        screen.blit(med.render(value, True, vcol), (rx + 24, y + 22))

    lvl_col = DANGER if level >= 90 else INK
    row(176, "MEASURED TANK LEVEL", f"{level}%", lvl_col)
    row(246, "DOSING SETPOINT", str(setpoint), AMBER)
    row(316, "PUMP", "RUNNING" if pump else "IDLE", GOOD if pump else MUTED)
    over_col = DANGER if override else GOOD
    row(386, "OVERFLOW INTERLOCK", "BYPASSED" if override else "ENGAGED", over_col)

    # alarm banner — across the top, clear of the readouts
    if override and level >= 97 and (t // 15) % 2 == 0:
        pygame.draw.rect(screen, DANGER, (TANK_X, 96, TANK_W, 40), border_radius=8)
        screen.blit(monob.render("!!  OVERFLOW  !!", True, (20, 20, 20)), (TANK_X + 70, 104))

    # footer
    screen.blit(small.render("127.0.0.1:5020 · read-only view · ESC to quit", True, MUTED), (40, H - 40))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Little Formby Water Works — World View — Operation Stillwater")
    clock = pygame.time.Clock()
    fonts = (
        pygame.font.SysFont("dejavusans", 40, bold=True),
        pygame.font.SysFont("dejavusans", 30, bold=True),
        pygame.font.SysFont("dejavusans", 20),
        pygame.font.SysFont("dejavusansmono", 22),
        pygame.font.SysFont("dejavusansmono", 24, bold=True),
    )

    plant = Plant()
    connected = plant.connect()

    level = setpoint = 0
    pump = override = 0
    disp_level = 0.0
    droplets, spills = [], []
    t = 0
    poll = 0

    running = True
    while running:
        clock.tick(FPS)
        t += 1
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False

        # poll the plant ~5x/sec
        poll += 1
        if poll >= 10:
            poll = 0
            if not connected:
                connected = plant.connect()
            if connected:
                try:
                    level = plant.read_input_reg(0)
                    setpoint = plant.read_holding_reg(1)
                    coils = plant.read_coils(0, 2)
                    pump, override = coils[0], coils[1]
                except OSError:
                    connected = False

        if not connected:
            screen.fill(BG)
            msg = fonts[1].render("Connecting to the plant…", True, MUTED)
            screen.blit(msg, (W // 2 - msg.get_width() // 2, H // 2 - 20))
            hint = fonts[2].render("start waterworks_plc.py first", True, LINE)
            screen.blit(hint, (W // 2 - hint.get_width() // 2, H // 2 + 24))
            pygame.display.flip()
            continue

        # ease displayed level toward target
        disp_level += (level - disp_level) * 0.15

        # spawn droplets from the dosing pipe while the pump runs
        pipe_x = TANK_X + TANK_W // 2
        if pump and t % 3 == 0:
            droplets.append([pipe_x + random.uniform(-6, 6), 110, random.uniform(5, 8)])
        surface_y = TANK_Y + TANK_H - int(TANK_H * disp_level / 100.0)
        for d in droplets:
            d[1] += d[2]
        droplets = [d for d in droplets if d[1] < surface_y]

        # spawn spill particles over the rim when overflowing with the interlock bypassed
        if override and disp_level >= 98:
            for side in (TANK_X + 10, TANK_X + TANK_W - 10):
                spills.append([side, RIM_Y, random.uniform(-2, 2) + (-3 if side == TANK_X + 10 else 3), 0])
        for s in spills:
            s[0] += s[2]
            s[3] += 0.5
            s[1] += s[3]
        spills = [s for s in spills if s[1] < H]

        draw(screen, fonts, int(round(disp_level)), setpoint, pump, override, droplets, spills, t)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
