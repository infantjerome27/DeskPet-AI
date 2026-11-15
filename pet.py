"""Buddy's animated pets: expressions, moods and canvas drawing.

Species: "blob" (the original), "cat" and "puppy". Every species has a
full body — tail that sways, paws that step while it walks, ears that
twitch — and eyes whose pupils track the mouse (the `look` offset).

The expression logic is pure (no tkinter) so it can be unit-tested, and
draw_pet() only needs a canvas-like object with create_*/delete methods,
so the drawings are testable with a stub canvas too.
"""
import math
import time

# Moods Buddy can be in. Each maps to eyes, mouth and extras.
# These are the agent states: thinking while you prompt, working while
# tools run, busy while tests/commands execute, waiting when Buddy needs
# your okay, celebrating when a task finishes, error on a roadblock,
# sleeping when you've stepped away from the keyboard.
EXPRESSIONS = {
    "idle":     {"eyes": "open",   "mouth": "smile",   "extras": []},
    "happy":    {"eyes": "happy",  "mouth": "big_smile", "extras": ["sparkles"]},
    "thinking": {"eyes": "side",   "mouth": "small_o", "extras": ["bubble"]},
    "sad":      {"eyes": "open",   "mouth": "frown",   "extras": []},
    "love":     {"eyes": "hearts", "mouth": "smile",   "extras": ["hearts"]},
    "speaking": {"eyes": "open",   "mouth": "open",    "extras": []},
    "listening": {"eyes": "open",  "mouth": "smile",   "extras": ["ear_wiggle"]},
    "working":  {"eyes": "open",   "mouth": "smile",   "extras": ["typing"]},
    "busy":     {"eyes": "focused", "mouth": "flat",   "extras": []},
    "waiting":  {"eyes": "worried", "mouth": "small_o", "extras": ["sweat"]},
    "error":    {"eyes": "worried", "mouth": "frown",  "extras": ["alarm"]},
    "celebrating": {"eyes": "happy", "mouth": "big_smile",
                    "extras": ["sparkles", "hearts", "dance"]},
    "sleeping": {"eyes": "closed", "mouth": "smile",   "extras": ["zzz"]},
}

SPECIES = ("blob", "cat", "puppy", "robot", "spirit", "muse")

# Photo pets: realistic animals in the pets/ folder, like the
# DeskPet-style companions. The value is (still PNG, animated GIF, drawn
# fallback). GIFs play when available; the PNG shows otherwise; the
# fallback drawing is used when both photo files are missing.
PHOTO_SPECIES = {
    "real_cat": ("real_cat.png", "real_cat.gif", "cat"),
    "real_dog": ("real_dog.png", "real_dog.gif", "puppy"),
    "real_kitty": ("real_kitty.png", "real_kitty.gif", "cat"),
}


def expression_for(mood):
    """Pure function: what Buddy's face looks like for a mood."""
    return dict(EXPRESSIONS.get(mood, EXPRESSIONS["idle"]))


class PetAnimator:
    """Animation state machine: bounce, blink, mood timing, walking."""

    def __init__(self, time_fn=None):
        self.time_fn = time_fn or time.time
        self.body_color = "#FFD66B"
        self.mood = "idle"
        self.mood_until = 0.0
        self.blink_until = 0.0
        self.next_blink = self.time_fn() + 2.5
        self.speaking_open = False
        self.moving = False
        self.tick = 0

    def set_mood(self, mood, seconds=3.0):
        self.mood = mood
        self.mood_until = self.time_fn() + seconds if seconds else 0.0

    def set_moving(self, moving):
        self.moving = moving

    def update(self):
        """Advance one animation frame. Returns a frame dict for drawing."""
        now = self.time_fn()
        self.tick += 1
        if self.mood_until and now >= self.mood_until:
            self.mood = "idle"
            self.mood_until = 0.0
        if now >= self.next_blink:
            self.blink_until = now + 0.15
            self.next_blink = now + 2.0 + (self.tick % 3) * 0.7
        blinking = now < self.blink_until
        if self.mood == "speaking":
            self.speaking_open = not self.speaking_open
        bounce = math.sin(self.tick * 0.08) * 2  # gentle breathing
        if self.mood == "happy":
            bounce = -abs(math.sin(self.tick * 0.5)) * 8
        elif self.mood in ("love", "celebrating"):
            bounce = -abs(math.sin(self.tick * 0.5)) * 12  # jumping for joy
        return {
            "mood": self.mood,
            "expression": expression_for(self.mood),
            "blinking": blinking,
            "bounce": bounce,
            "speaking_open": self.speaking_open,
            # Paws tap while working, and step while walking.
            "moving": self.moving or self.mood == "working",
            "tick": self.tick,
        }


PET_BODY_COLORS = {
    "yellow": "#FFD66B", "pink": "#FFB3C7", "blue": "#A8D8FF",
    "green": "#B5E6A2", "purple": "#D9C2FF", "orange": "#FFC98A",
}

DARK = "#3A2E1F"
PINK = "#FF9DB0"
CREAM = "#FFF3D6"


def _clamp_look(look):
    lx = max(-5, min(5, look[0]))
    ly = max(-5, min(5, look[1]))
    return lx, ly


def _eyes(canvas, cx, ey, look, expr, blinking):
    """Eyes with pupils that follow the mouse (`look` offset)."""
    lx, ly = _clamp_look(look)
    eyes = expr["eyes"]
    if blinking and eyes != "hearts":
        canvas.create_line(cx - 34, ey, cx - 16, ey, fill=DARK, width=3)
        canvas.create_line(cx + 16, ey, cx + 34, ey, fill=DARK, width=3)
    elif eyes == "hearts":
        for ex in (cx - 25, cx + 25):
            canvas.create_text(ex, ey, text="\u2764", font=("Segoe UI", 16),
                               fill="#E5486B")
    elif eyes == "happy":
        canvas.create_arc(cx - 36, ey - 4, cx - 14, ey + 14, start=0, extent=180,
                          style="arc", outline=DARK, width=3)
        canvas.create_arc(cx + 14, ey - 4, cx + 36, ey + 14, start=0, extent=180,
                          style="arc", outline=DARK, width=3)
    elif eyes == "side":
        for ex in (cx - 25, cx + 25):
            canvas.create_oval(ex - 7, ey - 8, ex + 7, ey + 8, fill="white",
                               outline=DARK, width=1)
            canvas.create_oval(ex + 1, ey - 4, ex + 7, ey + 4, fill=DARK, outline="")
    elif eyes == "focused":  # busy: determined, narrowed eyes + angled brows
        for ex in (cx - 25, cx + 25):
            canvas.create_line(ex - 10, ey - 14, ex + 10, ey - 10, fill=DARK, width=2)
            canvas.create_line(ex - 8, ey, ex + 8, ey, fill=DARK, width=3)
    elif eyes == "worried":  # waiting / error: wide eyes, raised brows
        for ex in (cx - 25, cx + 25):
            canvas.create_oval(ex - 9, ey - 10, ex + 9, ey + 10, fill="white",
                               outline=DARK, width=1)
            canvas.create_oval(ex - 3 + lx, ey - 6 + ly, ex + 3 + lx, ey + 2 + ly,
                               fill=DARK, outline="")
            canvas.create_arc(ex - 10, ey - 18, ex + 10, ey - 4, start=20,
                              extent=140, style="arc", outline=DARK, width=2)
    elif eyes == "closed":  # sleeping: softly closed eyes
        for ex in (cx - 25, cx + 25):
            canvas.create_arc(ex - 9, ey - 4, ex + 9, ey + 10, start=180,
                              extent=180, style="arc", outline=DARK, width=2)
    else:  # open: pupils shift with `look`
        for ex in (cx - 25, cx + 25):
            canvas.create_oval(ex - 8, ey - 9, ex + 8, ey + 9, fill="white",
                               outline=DARK, width=1)
            canvas.create_oval(ex - 4 + lx, ey - 5 + ly, ex + 4 + lx, ey + 5 + ly,
                               fill=DARK, outline="")
            canvas.create_oval(ex + 1 + lx, ey - 7 + ly, ex + 4 + lx, ey - 4 + ly,
                               fill="white", outline="")


def _mouth(canvas, cx, my, expr, speaking_open):
    mouth = expr["mouth"]
    if mouth == "smile":
        canvas.create_arc(cx - 16, my - 4, cx + 16, my + 12, start=200, extent=140,
                          style="arc", outline=DARK, width=3)
    elif mouth == "big_smile":
        canvas.create_arc(cx - 22, my - 6, cx + 22, my + 20, start=200, extent=140,
                          style="arc", outline=DARK, width=3)
        canvas.create_line(cx - 22, my + 2, cx + 22, my + 2, fill=DARK, width=2)
    elif mouth == "frown":
        canvas.create_arc(cx - 16, my, cx + 16, my + 16, start=20, extent=140,
                          style="arc", outline=DARK, width=3)
    elif mouth == "small_o":
        canvas.create_oval(cx - 5, my, cx + 5, my + 8, outline=DARK, width=2)
    elif mouth == "flat":
        canvas.create_line(cx - 9, my + 4, cx + 9, my + 4, fill=DARK, width=2)
    elif mouth == "open":
        if speaking_open:
            canvas.create_oval(cx - 9, my, cx + 9, my + 12, fill="#7A3B2E",
                               outline=DARK)
        else:
            canvas.create_line(cx - 8, my + 4, cx + 8, my + 4, fill=DARK, width=2)


def _extras(canvas, cx, cy, bounce, expr, tick=0):
    if "sparkles" in expr["extras"]:
        for sx, sy in ((cx - 62, cy - 40), (cx + 62, cy - 34), (cx + 48, cy - 58)):
            canvas.create_text(sx, sy + bounce, text="\u2726",
                               font=("Segoe UI", 13), fill="#FFB800")
    if "hearts" in expr["extras"]:
        for hx, hy in ((cx - 58, cy - 52), (cx + 58, cy - 48)):
            canvas.create_text(hx, hy + bounce, text="\u2764",
                               font=("Segoe UI", 13), fill="#E5486B")
    if "bubble" in expr["extras"]:  # thinking bubble
        canvas.create_oval(cx + 44, cy - 78 + bounce, cx + 82, cy - 50 + bounce,
                           fill="white", outline=DARK, width=1)
        canvas.create_text(cx + 63, cy - 64 + bounce, text="...",
                           font=("Segoe UI", 12, "bold"), fill=DARK)
        canvas.create_oval(cx + 36, cy - 48 + bounce, cx + 44, cy - 40 + bounce,
                           fill="white", outline=DARK, width=1)
    if "typing" in expr["extras"]:  # working: a tiny keyboard to tap on
        canvas.create_rectangle(cx - 32, cy + 56 + bounce, cx + 32, cy + 70 + bounce,
                                fill="#EDE6D6", outline=DARK, width=1)
        for kx in range(cx - 24, cx + 25, 12):
            canvas.create_line(kx, cy + 60 + bounce, kx, cy + 66 + bounce,
                               fill="#9A8A75", width=1)
    if "sweat" in expr["extras"]:  # waiting for approval: nervous sweat + ?
        canvas.create_oval(cx + 56, cy - 42 + bounce, cx + 68, cy - 26 + bounce,
                           fill="#7CC4FF", outline="")
        canvas.create_text(cx + 62, cy - 62 + bounce, text="?",
                           font=("Segoe UI", 15, "bold"), fill=DARK)
    if "alarm" in expr["extras"]:  # error: red alert triangle
        canvas.create_polygon(cx + 44, cy - 72 + bounce, cx + 62, cy - 40 + bounce,
                              cx + 26, cy - 40 + bounce,
                              fill="#FFD6D6", outline="#D92B2B", width=2)
        canvas.create_text(cx + 44, cy - 54 + bounce, text="!",
                           font=("Segoe UI", 14, "bold"), fill="#D92B2B")
    if "zzz" in expr["extras"]:  # sleeping: drifting Z's
        bob = math.sin(tick * 0.1) * 2
        for zx, zy, size in ((cx + 48, cy - 48, 10), (cx + 58, cy - 60, 13),
                             (cx + 70, cy - 74, 16)):
            canvas.create_text(zx, zy + bounce + bob, text="Z",
                               font=("Segoe UI", size, "bold"), fill="#8A7ACC")


def _paw_steps(moving, tick):
    """Front-paw lift offsets: alternate while walking, still otherwise."""
    if not moving:
        return 0, 0
    return (-6, 0) if (tick % 20) < 10 else (0, -6)


def _draw_blob(canvas, cx, cy, bounce, frame, body, look):
    """The classic blob, restyled: soft halo, gloss shine, neat ears
    and feet, and a little gold sparkle — a proper little AI pet."""
    expr = frame["expression"]
    tick = frame["tick"]
    moving = frame["moving"]
    canvas.create_oval(cx - 42, cy + 66 + bounce * 0.2, cx + 42, cy + 74,
                       fill="#E8DCC3", outline="")
    canvas.create_oval(cx - 62, cy - 62 + bounce, cx + 62, cy + 70 + bounce,
                       fill="#FDF6D8", outline="")
    wiggle = 6 if "ear_wiggle" in expr["extras"] else 0
    canvas.create_oval(cx - 50, cy - 64 + bounce, cx - 20, cy - 28 + bounce,
                       fill=body, outline=DARK, width=2)
    canvas.create_oval(cx + 20, cy - 64 + bounce + wiggle, cx + 50, cy - 28 + bounce,
                       fill=body, outline=DARK, width=2)
    canvas.create_oval(cx - 42, cy - 54 + bounce, cx - 28, cy - 34 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(cx + 28, cy - 54 + bounce + wiggle, cx + 42, cy - 34 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(cx - 56, cy - 46 + bounce, cx + 56, cy + 64 + bounce,
                       fill=body, outline=DARK, width=2)
    canvas.create_oval(cx - 32, cy + 10 + bounce, cx + 32, cy + 54 + bounce,
                       fill=CREAM, outline="")
    # Gloss shine, top-left of the body.
    canvas.create_oval(cx - 40, cy - 36 + bounce, cx - 20, cy - 14 + bounce,
                       fill="white", outline="")
    canvas.create_oval(cx - 48, cy + 2 + bounce, cx - 32, cy + 14 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(cx + 32, cy + 2 + bounce, cx + 48, cy + 14 + bounce,
                       fill=PINK, outline="")
    left_up, right_up = _paw_steps(moving, tick)
    canvas.create_oval(cx - 34, cy + 54 + bounce + left_up,
                       cx - 8, cy + 70 + bounce + left_up,
                       fill=CREAM, outline=DARK, width=1)
    canvas.create_oval(cx + 8, cy + 54 + bounce + right_up,
                       cx + 34, cy + 70 + bounce + right_up,
                       fill=CREAM, outline=DARK, width=1)
    canvas.create_text(cx + 46, cy - 40 + bounce, text="\u2726",
                       font=("Segoe UI", 13), fill="#FFB800")
    _eyes(canvas, cx, cy - 12 + bounce, look, expr, frame["blinking"])
    _mouth(canvas, cx, cy + 14 + bounce, expr, frame["speaking_open"])
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def _draw_muse(canvas, cx, cy, bounce, frame, body, look):
    """The Muse-style AI pet: a floating violet orb-bot with a glowing
    halo, a gold-tipped antenna, big glossy eyes and a white sparkle
    emblem on its belly. Drawn from scratch in this style, no assets."""
    expr = frame["expression"]
    tick = frame["tick"]
    moving = frame["moving"]
    violet = "#8B7CF6"
    deep = "#5B4BD4"
    pale = "#C9C2FF"
    canvas.create_oval(cx - 34, cy + 72 + bounce * 0.2, cx + 34, cy + 78,
                       fill="#D9D2FF", outline="")
    canvas.create_oval(cx - 60, cy - 66 + bounce, cx + 60, cy + 70 + bounce,
                       fill="#E9E4FF", outline="")
    # Antenna with a glowing tip (tinted by the chosen pet colour).
    canvas.create_line(cx, cy - 52 + bounce, cx, cy - 72 + bounce, fill=DARK, width=3)
    canvas.create_oval(cx - 7, cy - 80 + bounce, cx + 7, cy - 66 + bounce,
                       fill=body, outline=DARK, width=1)
    # Body + belly panel + gloss shine.
    canvas.create_oval(cx - 46, cy - 52 + bounce, cx + 46, cy + 64 + bounce,
                       fill=violet, outline=deep, width=2)
    canvas.create_oval(cx - 28, cy + 12 + bounce, cx + 28, cy + 52 + bounce,
                       fill=pale, outline="")
    canvas.create_oval(cx - 34, cy - 42 + bounce, cx - 14, cy - 20 + bounce,
                       fill="white", outline="")
    # Sparkle emblem on the belly.
    canvas.create_text(cx, cy + 32 + bounce, text="\u2726",
                       font=("Segoe UI", 20), fill="white")
    # Arms wave when happy; feet step while walking.
    wave = math.sin(tick * 0.4) * 4 if frame["mood"] == "happy" else 0
    canvas.create_oval(cx - 58, cy + 2 + bounce + wave, cx - 44, cy + 18 + bounce + wave,
                       fill=violet, outline=deep, width=1)
    canvas.create_oval(cx + 44, cy + 2 + bounce - wave, cx + 58, cy + 18 + bounce - wave,
                       fill=violet, outline=deep, width=1)
    left_up, right_up = _paw_steps(moving, tick)
    canvas.create_oval(cx - 30, cy + 56 + bounce + left_up,
                       cx - 10, cy + 70 + bounce + left_up,
                       fill=deep, outline="")
    canvas.create_oval(cx + 10, cy + 56 + bounce + right_up,
                       cx + 30, cy + 70 + bounce + right_up,
                       fill=deep, outline="")
    canvas.create_oval(cx - 44, cy + 2 + bounce, cx - 30, cy + 12 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(cx + 30, cy + 2 + bounce, cx + 44, cy + 12 + bounce,
                       fill=PINK, outline="")
    _eyes(canvas, cx, cy - 14 + bounce, look, expr, frame["blinking"])
    _mouth(canvas, cx, cy + 2 + bounce, expr, frame["speaking_open"])
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def _draw_cat(canvas, cx, cy, bounce, frame, body, look):
    expr = frame["expression"]
    tick = frame["tick"]
    moving = frame["moving"]
    lx, ly = _clamp_look(look)
    hx, hy = cx + lx * 2, cy + ly  # head tilts toward the mouse
    sway = math.sin(tick * 0.15) * 8
    # Tail (sways gently, faster when happy)
    if frame["mood"] == "happy":
        sway = math.sin(tick * 0.4) * 10
    canvas.create_line(cx + 48, cy + 48 + bounce, cx + 68, cy + 34 + bounce,
                       cx + 78, cy + 12 + bounce + sway,
                       fill=body, width=7, smooth=True)
    # Body + paws (they step while walking)
    canvas.create_oval(cx - 50, cy + 6 + bounce, cx + 50, cy + 68 + bounce,
                       fill=body, outline=DARK, width=2)
    left_up, right_up = _paw_steps(moving, tick)
    canvas.create_oval(cx - 34, cy + 56 + bounce + left_up,
                       cx - 8, cy + 72 + bounce + left_up,
                       fill=CREAM, outline=DARK, width=1)
    canvas.create_oval(cx + 8, cy + 56 + bounce + right_up,
                       cx + 34, cy + 72 + bounce + right_up,
                       fill=CREAM, outline=DARK, width=1)
    # Head (tilts toward the mouse)
    canvas.create_oval(hx - 48, hy - 58 + bounce, hx + 48, hy + 24 + bounce,
                       fill=body, outline=DARK, width=2)
    # Triangle ears (one twitches now and then, or when listening)
    twitch = 5 if ("ear_wiggle" in expr["extras"] or tick % 60 < 3) else 0
    canvas.create_polygon(hx - 44, hy - 50 + bounce, hx - 30, hy - 86 + bounce,
                          hx - 12, hy - 54 + bounce, fill=body, outline=DARK, width=2)
    canvas.create_polygon(hx - 36, hy - 52 + bounce, hx - 30, hy - 74 + bounce,
                          hx - 20, hy - 54 + bounce, fill=PINK, outline="")
    canvas.create_polygon(hx + 44, hy - 50 + bounce, hx + 30, hy - 86 + bounce - twitch,
                          hx + 12, hy - 54 + bounce, fill=body, outline=DARK, width=2)
    canvas.create_polygon(hx + 36, hy - 52 + bounce, hx + 30, hy - 74 + bounce - twitch,
                          hx + 20, hy - 54 + bounce, fill=PINK, outline="")
    # Whiskers
    for side in (-1, 1):
        for wy in (-2, 4, 10):
            canvas.create_line(hx + side * 14, hy + 2 + bounce + wy,
                               hx + side * 48, hy - 2 + bounce + wy,
                               fill=DARK, width=1)
    # Nose + mouth, blush, eyes
    canvas.create_polygon(hx - 6, hy - 2 + bounce, hx + 6, hy - 2 + bounce,
                          hx, hy + 5 + bounce, fill=PINK, outline="")
    _eyes(canvas, hx, hy - 22 + bounce, look, expr, frame["blinking"])
    _mouth(canvas, hx, hy + 8 + bounce, expr, frame["speaking_open"])
    canvas.create_oval(hx - 44, hy - 2 + bounce, hx - 28, hy + 10 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(hx + 28, hy - 2 + bounce, hx + 44, hy + 10 + bounce,
                       fill=PINK, outline="")
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def _draw_puppy(canvas, cx, cy, bounce, frame, body, look):
    expr = frame["expression"]
    tick = frame["tick"]
    moving = frame["moving"]
    lx, ly = _clamp_look(look)
    hx, hy = cx + lx * 2, cy + ly  # head tilts toward the mouse
    wag = math.sin(tick * 0.4) * 12
    # Tail (wags hard when happy)
    if frame["mood"] == "happy":
        wag = math.sin(tick * 0.7) * 16
    canvas.create_line(cx - 48, cy + 48 + bounce, cx - 68, cy + 30 + bounce,
                       cx - 74, cy + 8 + bounce + wag,
                       fill=body, width=7, smooth=True)
    # Body + paws (they step while walking)
    canvas.create_oval(cx - 50, cy + 6 + bounce, cx + 50, cy + 68 + bounce,
                       fill=body, outline=DARK, width=2)
    left_up, right_up = _paw_steps(moving, tick)
    canvas.create_oval(cx - 34, cy + 56 + bounce + left_up,
                       cx - 8, cy + 72 + bounce + left_up,
                       fill=CREAM, outline=DARK, width=1)
    canvas.create_oval(cx + 8, cy + 56 + bounce + right_up,
                       cx + 34, cy + 72 + bounce + right_up,
                       fill=CREAM, outline=DARK, width=1)
    # Head (tilts toward the mouse)
    canvas.create_oval(hx - 46, hy - 56 + bounce, hx + 46, hy + 22 + bounce,
                       fill=body, outline=DARK, width=2)
    # Floppy ears
    canvas.create_oval(hx - 62, hy - 52 + bounce, hx - 30, hy + 2 + bounce,
                       fill=body, outline=DARK, width=2)
    canvas.create_oval(hx + 30, hy - 52 + bounce, hx + 62, hy + 2 + bounce,
                       fill=body, outline=DARK, width=2)
    # Snout + nose + tongue when happy
    canvas.create_oval(hx - 24, hy - 6 + bounce, hx + 24, hy + 18 + bounce,
                       fill=CREAM, outline="")
    canvas.create_oval(hx - 8, hy - 4 + bounce, hx + 8, hy + 4 + bounce,
                       fill=DARK, outline="")
    if frame["mood"] == "happy":
        canvas.create_oval(hx - 7, hy + 14 + bounce, hx + 7, hy + 28 + bounce,
                           fill=PINK, outline="")
    _eyes(canvas, hx, hy - 24 + bounce, look, expr, frame["blinking"])
    _mouth(canvas, hx, hy + 10 + bounce, expr, frame["speaking_open"])
    canvas.create_oval(hx - 42, hy - 2 + bounce, hx - 26, hy + 10 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(hx + 26, hy - 2 + bounce, hx + 42, hy + 10 + bounce,
                       fill=PINK, outline="")
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def _draw_robot(canvas, cx, cy, bounce, frame, body, look):
    expr = frame["expression"]
    tick = frame["tick"]
    moving = frame["moving"]
    lx, ly = _clamp_look(look)
    hx, hy = cx + lx * 2, cy + ly  # head tilts toward the mouse
    metal = "#C0C8D0"
    glow = "#00C8E8"
    # Antenna (blinks)
    canvas.create_line(hx, hy - 58 + bounce, hx, hy - 76 + bounce, fill=DARK, width=3)
    canvas.create_oval(hx - 6, hy - 84 + bounce, hx + 6, hy - 72 + bounce,
                       fill=glow if tick % 20 < 10 else "#FFB800", outline="")
    # Head
    canvas.create_rectangle(hx - 42, hy - 58 + bounce, hx + 42, hy + 6 + bounce,
                            fill=metal, outline=DARK, width=2)
    canvas.create_rectangle(hx - 52, hy - 40 + bounce, hx - 42, hy - 16 + bounce,
                            fill=body, outline=DARK, width=1)
    canvas.create_rectangle(hx + 42, hy - 40 + bounce, hx + 52, hy - 16 + bounce,
                            fill=body, outline=DARK, width=1)
    # Glowing eyes that track the mouse
    for ex in (hx - 20, hx + 20):
        canvas.create_oval(ex - 9, hy - 36 + bounce, ex + 9, hy - 18 + bounce,
                           fill="#0B2B33", outline="")
        canvas.create_oval(ex - 4 + lx, hy - 31 + ly, ex + 4 + lx, hy - 23 + ly,
                           fill=glow, outline="")
    # Mouth: a light bar that opens while speaking
    mh = 12 if frame["speaking_open"] else 4
    canvas.create_rectangle(hx - 14, hy - 8 + bounce, hx + 14, hy - 8 + bounce + mh,
                            fill=glow if frame["speaking_open"] else DARK, outline="")
    # Body + core
    canvas.create_rectangle(cx - 38, cy + 12 + bounce, cx + 38, cy + 58 + bounce,
                            fill=metal, outline=DARK, width=2)
    canvas.create_oval(cx - 10, cy + 26 + bounce, cx + 10, cy + 46 + bounce,
                       fill=glow, outline=DARK, width=1)
    # Arms (swing while walking) and legs (step while walking)
    swing = 6 if moving and (tick % 20) < 10 else 0
    canvas.create_rectangle(cx - 52, cy + 14 + bounce - swing, cx - 38,
                            cy + 48 + bounce, fill=body, outline=DARK, width=1)
    canvas.create_rectangle(cx + 38, cy + 14 + bounce + swing, cx + 52,
                            cy + 48 + bounce, fill=body, outline=DARK, width=1)
    left_up, right_up = _paw_steps(moving, tick)
    canvas.create_rectangle(cx - 26, cy + 58 + bounce + left_up, cx - 6,
                            cy + 72 + bounce + left_up, fill=DARK, outline="")
    canvas.create_rectangle(cx + 6, cy + 58 + bounce + right_up, cx + 26,
                            cy + 72 + bounce + right_up, fill=DARK, outline="")
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def _draw_spirit(canvas, cx, cy, bounce, frame, body, look):
    expr = frame["expression"]
    tick = frame["tick"]
    float_bob = math.sin(tick * 0.1) * 6
    ghost = "#E8F4FF"
    # Wavy ghost skirt
    wave = math.sin(tick * 0.2) * 4
    canvas.create_polygon(cx - 44, cy - 30 + bounce + float_bob,
                          cx - 44, cy + 44 + bounce,
                          cx - 33, cy + 34 + bounce + wave,
                          cx - 22, cy + 44 + bounce,
                          cx - 11, cy + 34 + bounce - wave,
                          cx, cy + 44 + bounce,
                          cx + 11, cy + 34 + bounce + wave,
                          cx + 22, cy + 44 + bounce,
                          cx + 33, cy + 34 + bounce - wave,
                          cx + 44, cy + 44 + bounce,
                          cx + 44, cy - 30 + bounce + float_bob,
                          fill=ghost, outline=DARK, width=2, smooth=True)
    # Head dome
    canvas.create_oval(cx - 44, cy - 66 + bounce + float_bob,
                       cx + 44, cy + 6 + bounce + float_bob,
                       fill=ghost, outline=DARK, width=2)
    # Little arms
    canvas.create_oval(cx - 56, cy - 10 + bounce, cx - 38, cy + 6 + bounce,
                       fill=ghost, outline=DARK, width=1)
    canvas.create_oval(cx + 38, cy - 10 + bounce, cx + 56, cy + 6 + bounce,
                       fill=ghost, outline=DARK, width=1)
    _eyes(canvas, cx, cy - 30 + bounce + float_bob, look, expr, frame["blinking"])
    _mouth(canvas, cx, cy - 2 + bounce + float_bob, expr, frame["speaking_open"])
    canvas.create_oval(cx - 40, cy - 12 + bounce, cx - 26, cy - 2 + bounce,
                       fill=PINK, outline="")
    canvas.create_oval(cx + 26, cy - 12 + bounce, cx + 40, cy - 2 + bounce,
                       fill=PINK, outline="")
    _extras(canvas, cx, cy, bounce, expr, frame["tick"])


def draw_photo_pet(canvas, frame, photo_image, size=180):
    """Show a photo pet: the image bobs/jumps with the mood and leans a
    few pixels toward the mouse (the photo's own eyes do the rest)."""
    lx, ly = _clamp_look(frame.get("look", (0, 0)))
    bounce = frame["bounce"]
    canvas.delete("all")
    canvas.create_image(size // 2 + lx, size // 2 + bounce + ly,
                        image=photo_image)


def draw_pet(canvas, frame, size=180, body_color="#FFD66B",
             species="blob", look=(0, 0)):
    """Draw Buddy on a canvas. `frame` comes from PetAnimator.update().

    species: "blob", "cat" or "puppy". look: (dx, dy) pupil offset in
    pixels, e.g. towards the mouse, clamped to +/-5.
    """
    canvas.delete("all")
    cx, cy = size // 2, size // 2 + 8
    bounce = frame["bounce"]
    if "dance" in frame["expression"]["extras"]:
        cx += int(math.sin(frame["tick"] * 0.3) * 6)  # celebration dance
    if species in PHOTO_SPECIES:
        # Drawn fallback for photo pets (the UI shows the photo itself).
        species = PHOTO_SPECIES[species][2]
    if species not in SPECIES:
        species = "blob"
    if species == "cat":
        _draw_cat(canvas, cx, cy, bounce, frame, body_color, look)
    elif species == "puppy":
        _draw_puppy(canvas, cx, cy, bounce, frame, body_color, look)
    elif species == "robot":
        _draw_robot(canvas, cx, cy, bounce, frame, body_color, look)
    elif species == "spirit":
        _draw_spirit(canvas, cx, cy, bounce, frame, body_color, look)
    elif species == "muse":
        _draw_muse(canvas, cx, cy, bounce, frame, body_color, look)
    else:
        _draw_blob(canvas, cx, cy, bounce, frame, body_color, look)
