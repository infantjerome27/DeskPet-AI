"""Buddy's desktop interface: the pet window and the chat window (tkinter).

Only the standard library is used, so this runs on any Windows PC with
Python installed. The pet window is small, always on top, transparent
(only the pet itself is visible) and draggable anywhere on the desktop;
click Buddy to open the chat, double-click for a trick, right-click
for a menu. On its own it wanders, hides and plays; after a minute
with no keyboard activity it falls asleep.
"""
import os
import queue
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from pet import PET_BODY_COLORS, PHOTO_SPECIES, PetAnimator, draw_pet, draw_photo_pet
from tools import celebrate_sound, listen, speak

# On Windows the pet window is truly transparent: this colour becomes
# see-through, so only the drawn pet and its labels float on the desktop.
# Everywhere else the window keeps a warm cream background instead.
BG = "#FF00FF" if os.name == "nt" else "#FFF8E7"


class BuddyApp:
    def __init__(self, root, brain, listener=None):
        self.root = root
        self.brain = brain
        self.listener = listener  # injected mic for tests; None = real mic
        self.animator = PetAnimator()
        self.reminder_queue = queue.Queue()
        self.reply_queue = queue.Queue()
        self.listen_queue = queue.Queue()
        self.brain.on_reminder = self.reminder_queue.put
        self.chat_visible = False
        self._drag = None
        self._press_pos = None
        self._click_job = None
        self._suppress_click = False
        self._tasks_running = 0
        self._glide_token = 0
        self._chat_placed = False
        self._last_activity = time.time()
        self._listening = False
        self.settings_win = None
        self.approval_win = None
        self.species = "real_cat"
        self.photo_images = {}
        self.gif_frames = {}
        self.voice_enabled = True
        self.autonomy = True
        self.pet_size = 180
        self.move_speed = "normal"
        self.voice_volume = 100

        # ---------------- pet window ----------------
        self.pet_win = tk.Toplevel(root)
        self.pet_win.overrideredirect(True)
        self.pet_win.attributes("-topmost", True)
        if os.name == "nt":
            try:
                self.pet_win.attributes("-transparentcolor", BG)
            except Exception:
                pass
        self.pet_win.configure(bg=BG)
        self.pet_win.geometry("200x240+100+100")

        self.canvas = tk.Canvas(self.pet_win, width=180, height=180, bg=BG,
                                highlightthickness=0)
        self.canvas.pack(pady=(4, 0))
        self.name_label = tk.Label(self.pet_win, text="Buddy",
                                   font=("Segoe UI", 11, "bold"), bg=BG,
                                   fg="#3A2E1F")
        self.name_label.pack()
        self.mood_label = tk.Label(self.pet_win, text="",
                                   font=("Segoe UI", 9), bg=BG, fg="#7A6A55")
        self.mood_label.pack()
        self.hint_label = tk.Label(self.pet_win, text="Click me to chat!",
                                   font=("Segoe UI", 8), bg=BG, fg="#9A8A75")
        self.hint_label.pack()

        for widget in (self.pet_win, self.canvas, self.name_label,
                       self.mood_label, self.hint_label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_release)
            widget.bind("<Double-Button-1>", self._double_click)
        self.pet_win.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Button-3>", self._show_menu)

        # ---------------- chat window ----------------
        self.chat_win = tk.Toplevel(root)
        self.chat_win.title("Buddy - your desktop pet")
        self.chat_win.geometry("420x540+320+100")
        self.chat_win.protocol("WM_DELETE_WINDOW", self._hide_chat)

        self.history = tk.Text(self.chat_win, wrap="word", state="disabled",
                               font=("Segoe UI", 11), bg="white")
        self.history.pack(fill="both", expand=True, padx=8, pady=8)
        self.history.tag_config("buddy_name", font=("Segoe UI", 11, "bold"),
                                foreground="#B85C00")
        self.history.tag_config("you_name", font=("Segoe UI", 11, "bold"),
                                foreground="#1A5276")
        self.history.tag_config("time", font=("Segoe UI", 9),
                                foreground="#9A8A75")
        entry_frame = tk.Frame(self.chat_win)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.entry = tk.Entry(entry_frame, font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.send_message())
        self.entry.bind("<Key>", lambda e: self._mark_activity())
        self.mic_btn = tk.Button(entry_frame, text="\U0001F3A4",
                                 command=self._on_mic, font=("Segoe UI", 11))
        self.mic_btn.pack(side="right", padx=(6, 0))
        self.voice_btn = tk.Button(entry_frame, text="\U0001F50A",
                                   command=self._toggle_voice,
                                   font=("Segoe UI", 11))
        self.voice_btn.pack(side="right", padx=(6, 0))
        send_btn = tk.Button(entry_frame, text="Send", command=self.send_message,
                             font=("Segoe UI", 11, "bold"))
        send_btn.pack(side="right", padx=(6, 0))
        quick = tk.Frame(self.chat_win)
        quick.pack(fill="x", padx=8, pady=(0, 8))
        for label, command in (("Help", lambda: self._quick("help")),
                               ("Open Word", lambda: self._quick("open word")),
                               ("My Files", lambda: self._quick("list files in Documents")),
                               ("Settings", self._open_settings)):
            tk.Button(quick, text=label, command=command,
                      font=("Segoe UI", 10)).pack(side="left", padx=3)
        self.chat_win.withdraw()

        # Apply saved settings (pet name, species, size, colour, greeting,
        # chat font, voice, autonomy, and where you last left the pet).
        from tools import load_settings, set_voice_volume
        settings = load_settings()
        self.pet_name = settings.get("pet_name", "Buddy")
        self.name_label.configure(text=self.pet_name)
        self.chat_win.title(f"{self.pet_name} - your desktop pet")
        if settings.get("pet_species") in ("blob", "cat", "puppy", "robot",
                                           "spirit", "muse", "real_cat",
                                           "real_dog", "real_kitty"):
            self.species = settings["pet_species"]
        if settings.get("pet_size"):
            self.pet_size = int(settings["pet_size"])
        if settings.get("move_speed") in ("slow", "normal", "fast"):
            self.move_speed = settings["move_speed"]
        if settings.get("pet_color"):
            self.animator.body_color = settings["pet_color"]
        if settings.get("chat_font"):
            self._set_chat_font(settings["chat_font"])
        if "voice" in settings:
            self.voice_enabled = bool(settings["voice"])
            self._refresh_voice_button()
        if "voice_volume" in settings:
            self.voice_volume = int(settings["voice_volume"])
            set_voice_volume(self.voice_volume)
        if "autonomy" in settings:
            self.autonomy = bool(settings["autonomy"])
        if self.pet_size != 180:
            self._apply_pet_size(self.pet_size)
        px, py = settings.get("pet_x"), settings.get("pet_y")
        if isinstance(px, int) and isinstance(py, int):
            sw = self.pet_win.winfo_screenwidth()
            sh = self.pet_win.winfo_screenheight()
            px = max(0, min(px, sw - 100))
            py = max(0, min(py, sh - 100))
            self.pet_win.geometry(f"200x240+{px}+{py}")
        greeting = settings.get("greeting") or (
            f"Hi! I'm {self.pet_name}, your desktop pet. "
            "Click me anytime to chat. Type 'help' to see what I can do!")
        self._say(self.pet_name, greeting)
        self._animate()
        self._poll_reminders()
        self._poll_replies()
        self._idle_check()
        self.root.after(20000, self._autonomy_tick)

    def _set_chat_font(self, size):
        self.history.configure(font=("Segoe UI", size))
        self.entry.configure(font=("Segoe UI", size))

    # -- pet window behaviour -----------------------------------------
    def _drag_start(self, event):
        self._mark_activity()
        self._glide_token += 1  # stop any autonomous glide in progress
        self._drag = (event.x_root, event.y_root,
                      self.pet_win.winfo_x(), self.pet_win.winfo_y())
        self._press_pos = (event.x_root, event.y_root)

    def _drag_move(self, event):
        if not self._drag:
            return
        x0, y0, wx, wy = self._drag
        self.pet_win.geometry(f"+{wx + event.x_root - x0}+{wy + event.y_root - y0}")

    def _drag_release(self, event):
        if self._drag is None or self._press_pos is None:
            return
        self._drag = None
        self._save_position()
        if self._suppress_click:
            # This release belongs to a double-click; the trick already ran.
            self._suppress_click = False
            return
        dx = event.x_root - self._press_pos[0]
        dy = event.y_root - self._press_pos[1]
        if dx * dx + dy * dy < 36:  # moved less than 6px: a click, not a drag
            # Slight delay so a double-click can cancel this and play
            # a trick instead of opening and instantly closing the chat.
            if self._click_job is not None:
                self.root.after_cancel(self._click_job)
            self._click_job = self.root.after(250, self._toggle_chat_delayed)

    def _double_click(self, event):
        if self._click_job is not None:
            self.root.after_cancel(self._click_job)
            self._click_job = None
        self._suppress_click = True
        self._play_trick()

    def _toggle_chat_delayed(self):
        self._click_job = None
        if self.chat_visible:
            self._hide_chat()
        else:
            self._show_chat()

    def _show_chat(self):
        self._mark_activity()
        if not self._chat_placed:
            # Open the chat right beside the pet, wherever it currently is.
            px, py = self._pet_pos()
            sw = self.chat_win.winfo_screenwidth()
            sh = self.chat_win.winfo_screenheight()
            cx = max(0, min(px + self.pet_size + 30, sw - 430))
            cy = max(0, min(py, sh - 550))
            self.chat_win.geometry(f"420x540+{cx}+{cy}")
            self._chat_placed = True
        self.chat_win.deiconify()
        self.chat_win.lift()
        # The typing fix: clicking the borderless pet window does not give
        # the app keyboard focus on Windows, so the chat must grab it
        # explicitly — briefly on top, then forced focus on the text box.
        try:
            self.chat_win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.chat_win.focus_force()
            self.entry.focus_force()
        except Exception:
            self.entry.focus_set()
        self.chat_visible = True
        self.root.after(500, self._release_chat_topmost)

    def _release_chat_topmost(self):
        try:
            self.chat_win.attributes("-topmost", False)
        except Exception:
            pass

    def _hide_chat(self):
        self.chat_win.withdraw()
        self.chat_visible = False

    def _pet_pos(self):
        """Current pet position, from the geometry string (synchronous,
        unlike winfo_x/y which lag behind a just-requested move)."""
        import re
        m = re.match(r"\d+x\d+\+(-?\d+)\+(-?\d+)",
                     self.pet_win.geometry())
        if m:
            return int(m.group(1)), int(m.group(2))
        return self.pet_win.winfo_x(), self.pet_win.winfo_y()

    def _save_position(self):
        try:
            from tools import load_settings, save_settings
            settings = load_settings()
            settings["pet_x"], settings["pet_y"] = self._pet_pos()
            save_settings(settings)
        except Exception:
            pass

    def _play_trick(self):
        """A little jump for joy, right where the pet sits."""
        self.animator.set_mood("love", seconds=3.0)
        base_x, base_y = self._pet_pos()

        def step(i, offsets=(-18, -30, -18, 0, -12, 0)):
            if i >= len(offsets):
                self.pet_win.geometry(f"+{base_x}+{base_y}")
                return
            self.pet_win.geometry(f"+{base_x}+{base_y + offsets[i]}")
            self.root.after(80, step, i + 1)

        step(0)

    def _show_menu(self, event):
        menu = tk.Menu(self.pet_win, tearoff=0)
        menu.add_command(label="Open chat", command=self._show_chat)
        menu.add_command(label="Play a trick", command=self._play_trick)
        menu.add_command(label="Settings...", command=self._open_settings)
        menu.add_command(label="Help", command=lambda: self._quick("help"))
        menu.add_command(label="Take a screenshot",
                         command=lambda: self._quick("take screenshot"))
        menu.add_command(label="About Buddy",
                         command=lambda: messagebox.showinfo(
                             "About Buddy",
                             "Buddy is your offline desktop pet.\n"
                             "It runs entirely on your computer, needs no "
                             "account, and sends no data anywhere.\n"
                             "Web searches open your browser and need internet."))
        menu.add_separator()
        menu.add_command(label="Quit Buddy", command=self.root.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    # -- chat ----------------------------------------------------------
    def _say(self, who, text):
        self.history.configure(state="normal")
        stamp = datetime.now().strftime("%H:%M")
        self.history.insert("end", f"[{stamp}] ", ("time",))
        tag = "you_name" if who == "You" else "buddy_name"
        self.history.insert("end", f"{who}: ", (tag,))
        self.history.insert("end", f"{text}\n\n")
        self.history.configure(state="disabled")
        self.history.see("end")

    def _quick(self, text):
        if not self.chat_visible:
            self._show_chat()
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.send_message()

    def send_message(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._mark_activity()
        self._say("You", text)
        # Agent state while the task runs: busy for tests/commands,
        # working (typing paws) for everything else. The reply arrives
        # through the queue so the pet keeps animating meanwhile.
        busy = text.lower().startswith(("run python", "check python"))
        self.animator.set_mood("busy" if busy else "working", seconds=0)
        self._tasks_running += 1
        threading.Thread(target=self._run_task, args=(text,),
                         daemon=True).start()

    def _run_task(self, text):
        try:
            reply, mood = self.brain.handle(text)
            changed = dict(self.brain.settings_changed)
        except Exception as e:  # never let a task crash the pet
            reply, mood, changed = f"Something went wrong on my side: {e}", "error", {}
        self.reply_queue.put((reply, mood, changed))

    def _poll_replies(self):
        try:
            while True:
                reply, mood, changed = self.reply_queue.get_nowait()
                self._tasks_running = max(0, self._tasks_running - 1)
                self._apply_settings(changed)
                self.animator.set_mood(mood, seconds=4.0)
                self._say(self.pet_name, reply)
                if mood == "waiting":
                    self._show_approval(reply)
                if mood == "celebrating":
                    try:
                        celebrate_sound()
                    except Exception:
                        pass
                if self.voice_enabled:
                    try:
                        speak(reply)
                    except Exception:
                        pass
                # Persist the user's name once Buddy learns it.
                try:
                    from tools import load_settings, save_settings
                    settings = load_settings()
                    if self.brain.user_name and settings.get("user_name") != self.brain.user_name:
                        settings["user_name"] = self.brain.user_name
                        save_settings(settings)
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            while True:
                text, error = self.listen_queue.get_nowait()
                self._listening = False
                self.mic_btn.configure(state="normal")
                self.entry.configure(fg="black")
                self.entry.delete(0, "end")
                if error:
                    self.animator.set_mood("sad", seconds=3.0)
                    self._say(self.pet_name, error)
                elif text:
                    self.animator.set_mood("idle", seconds=0)
                    self.entry.insert(0, text)
                    self.send_message()
                else:
                    self.animator.set_mood("sad", seconds=3.0)
                    self._say(self.pet_name, "I couldn't hear anything — "
                                            "try again, a bit louder.")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_replies)

    def _apply_settings(self, changed):
        if "pet_name" in changed:
            self.pet_name = changed["pet_name"]
            self.name_label.configure(text=self.pet_name)
            self.chat_win.title(f"{self.pet_name} - your desktop pet")
        if "pet_color" in changed:
            self.animator.body_color = changed["pet_color"]
        if "chat_font" in changed:
            self._set_chat_font(changed["chat_font"])
        if "pet_species" in changed:
            self.species = changed["pet_species"]
        if "pet_size" in changed:
            self._apply_pet_size(int(changed["pet_size"]))
        if "move_speed" in changed:
            self.move_speed = changed["move_speed"]
        if "voice" in changed:
            self.voice_enabled = bool(changed["voice"])
            self._refresh_voice_button()
        if "voice_volume" in changed:
            self.voice_volume = int(changed["voice_volume"])
            try:
                from tools import set_voice_volume
                set_voice_volume(self.voice_volume)
            except Exception:
                pass
        if "autonomy" in changed:
            self.autonomy = bool(changed["autonomy"])
        if changed.get("open_settings"):
            self._open_settings()

    def _get_photo(self, species):
        """Load a photo pet's transparent PNG (cached, resized to the
        pet size when Pillow is available). None if the file is missing,
        in which case the drawn fallback is shown instead."""
        if species not in PHOTO_SPECIES:
            return None
        if species in self.photo_images:
            return self.photo_images[species]
        filename = PHOTO_SPECIES[species][0]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pets", filename)
        photo = None
        try:
            if self.pet_size != 180:
                from PIL import Image, ImageTk
                img = Image.open(path)
                w, h = img.size
                nw = max(1, round(w * self.pet_size / h))
                photo = ImageTk.PhotoImage(img.resize((nw, self.pet_size),
                                                       Image.LANCZOS))
            else:
                photo = tk.PhotoImage(file=path)
        except Exception:
            try:
                photo = tk.PhotoImage(file=path)
            except Exception:
                photo = None
        if photo is not None:
            self.photo_images[species] = photo
        return photo

    def _get_gif_frames(self, species):
        """Load a photo pet's animated GIF frames (tkinter plays GIFs
        natively, frame by frame). Empty list when there is no GIF."""
        if species not in PHOTO_SPECIES:
            return []
        if species in self.gif_frames:
            return self.gif_frames[species]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pets", PHOTO_SPECIES[species][1])
        frames = []
        try:
            if self.pet_size != 180:
                from PIL import Image, ImageTk
                gif = Image.open(path)
                for i in range(getattr(gif, "n_frames", 1)):
                    gif.seek(i)
                    frame = gif.convert("RGBA")
                    w, h = frame.size
                    nw = max(1, round(w * self.pet_size / h))
                    frames.append(ImageTk.PhotoImage(
                        frame.resize((nw, self.pet_size), Image.LANCZOS)))
            else:
                i = 0
                while True:
                    try:
                        frames.append(tk.PhotoImage(
                            file=path, format=f"gif -index {i}"))
                    except Exception:
                        break
                    i += 1
        except Exception:
            frames = []
        if frames:
            self.gif_frames[species] = frames
        return frames

    def _apply_pet_size(self, size):
        self.pet_size = max(120, min(280, int(size)))
        self.photo_images = {}  # reload photos at the new size
        self.gif_frames = {}
        self.canvas.configure(width=self.pet_size, height=self.pet_size)
        px, py = self._pet_pos()
        self.pet_win.geometry(
            f"{self.pet_size + 20}x{self.pet_size + 60}+{px}+{py}")

    # -- activity, sleep, autonomy --------------------------------------
    def _mark_activity(self):
        self._last_activity = time.time()
        if self.animator.mood == "sleeping":
            self.animator.set_mood("happy", seconds=2.0)  # waking stretch

    def _idle_check(self):
        # A minute with no keyboard activity: fall asleep (any keypress,
        # click or message wakes Buddy up again).
        if (time.time() - self._last_activity > 60
                and self.animator.mood == "idle"):
            self.animator.set_mood("sleeping", seconds=0)
        self.root.after(5000, self._idle_check)

    def _autonomy_tick(self, choice=None):
        self.root.after(random.randint(15000, 30000), self._autonomy_tick)
        if not self.autonomy:
            return
        if (self.chat_visible or self._drag is not None
                or self.animator.mood == "sleeping" or self._tasks_running > 0):
            return
        if choice is None:
            choice = random.choice(["glide", "glide", "hide", "trick"])
        if choice == "trick":
            self._play_trick()
        elif choice == "hide":
            self._hide_and_seek()
        else:
            self._glide_somewhere()

    def _glide_to(self, tx, ty, on_done=None):
        """Glide the pet to (tx, ty) with stepping paws; abort on grab."""
        self._glide_token += 1
        token = self._glide_token
        sx, sy = self._pet_pos()
        steps = 24
        dx, dy = (tx - sx) / steps, (ty - sy) / steps
        self.animator.set_moving(True)

        def step(i):
            if token != self._glide_token:
                self.animator.set_moving(False)
                return
            if i >= steps:
                self.pet_win.geometry(f"+{tx}+{ty}")
                self.animator.set_moving(False)
                self._save_position()
                if on_done:
                    on_done()
                return
            self.pet_win.geometry(f"+{int(sx + dx * i)}+{int(sy + dy * i)}")
            delay = {"slow": 50, "normal": 30, "fast": 15}[self.move_speed]
            self.root.after(delay, step, i + 1)

        step(0)

    def _glide_somewhere(self):
        sw = self.pet_win.winfo_screenwidth()
        sh = self.pet_win.winfo_screenheight()
        if random.random() < 0.3:
            # Hang out near the cursor.
            mx = self.pet_win.winfo_pointerx()
            my = self.pet_win.winfo_pointery()
            tx = max(0, min(mx - 230, sw - 200))
            ty = max(0, min(my - 100, sh - 240))
        else:
            tx = random.randint(0, max(0, sw - 200))
            ty = random.randint(0, max(0, sh - 240))
        self._glide_to(tx, ty)

    def _hide_and_seek(self):
        ox, oy = self._pet_pos()
        sw = self.pet_win.winfo_screenwidth()
        if random.random() < 0.5:
            # Peekaboo: vanish for a few seconds, then pop back with a jump.
            self.pet_win.withdraw()
            self.root.after(4000, lambda: (
                self.pet_win.deiconify(), self._play_trick()))
        else:
            # Slide to the nearest screen edge, peek, then come back.
            tx = -160 if ox < sw // 2 else sw - 40
            self._glide_to(tx, oy, on_done=lambda: self.root.after(
                4000, lambda: self._glide_to(ox, oy)))

    # -- voice -----------------------------------------------------------
    def _refresh_voice_button(self):
        self.voice_btn.configure(text="\U0001F50A" if self.voice_enabled
                                 else "\U0001F507")

    def _toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        self._refresh_voice_button()
        try:
            from tools import load_settings, save_settings
            settings = load_settings()
            settings["voice"] = self.voice_enabled
            save_settings(settings)
        except Exception:
            pass

    def _on_mic(self):
        if self._listening:
            return
        self._listening = True
        self._mark_activity()
        self.mic_btn.configure(state="disabled")
        self.animator.set_mood("listening", seconds=0)
        self.entry.delete(0, "end")
        self.entry.insert(0, "Listening... speak now!")
        self.entry.configure(fg="gray")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        try:
            text = listen(runner=self.listener)
            self.listen_queue.put((text, None))
        except Exception as e:
            self.listen_queue.put(("", str(e)))

    # -- approval popup -----------------------------------------------------
    def _show_approval(self, text):
        """Interactive permission bubble anchored near the pet."""
        if self.approval_win is not None:
            try:
                self._approval_label.configure(text=text)
                return
            except Exception:
                self.approval_win = None
        win = tk.Toplevel(self.root)
        self.approval_win = win
        win.title("Buddy needs your okay")
        px, py = self._pet_pos()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"320x170+{max(0, min(px + self.pet_size + 30, sw - 330))}"
                     f"+{max(0, min(py, sh - 180))}")
        win.protocol("WM_DELETE_WINDOW", self._close_approval)
        tk.Label(win, text="Buddy is asking permission:",
                 font=("Segoe UI", 10, "bold")).pack(padx=12, pady=(10, 2))
        self._approval_label = tk.Label(win, text=text, wraplength=290,
                                        font=("Segoe UI", 10), justify="left")
        self._approval_label.pack(padx=12, pady=4)
        btns = tk.Frame(win)
        btns.pack(pady=10)
        tk.Button(btns, text="Approve", command=lambda: self._answer_approval(True),
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        tk.Button(btns, text="Deny", command=lambda: self._answer_approval(False),
                  font=("Segoe UI", 10)).pack(side="left", padx=8)

    def _close_approval(self):
        if self.approval_win is not None:
            self.approval_win.destroy()
            self.approval_win = None

    def _answer_approval(self, approved):
        self._close_approval()
        self._quick("yes" if approved else "no")

    # -- settings page ----------------------------------------------------
    def _open_settings(self):
        if self.settings_win is not None:
            try:
                self.settings_win.lift()
                self.settings_win.focus_set()
                return
            except Exception:
                self.settings_win = None
        from tools import load_settings
        settings = load_settings()
        win = tk.Toplevel(self.root)
        self.settings_win = win
        win.title(f"{self.pet_name} settings")
        win.geometry("380x580")
        win.protocol("WM_DELETE_WINDOW", self._close_settings)
        vars_ = {}

        def row(label_text, widget, r):
            tk.Label(win, text=label_text, font=("Segoe UI", 10)).grid(
                row=r, column=0, sticky="w", padx=12, pady=4)
            widget.grid(row=r, column=1, sticky="ew", padx=12, pady=4)

        name_var = tk.StringVar(value=settings.get("pet_name", self.pet_name))
        row("Pet name:", tk.Entry(win, textvariable=name_var,
                                  font=("Segoe UI", 10)), 0)
        species_var = tk.StringVar(
            value={"blob": "Blob", "cat": "Cat", "puppy": "Puppy",
                   "robot": "Robot", "spirit": "Spirit", "muse": "Muse",
                   "real_cat": "Real Cat", "real_dog": "Real Dog",
                   "real_kitty": "Real Kitty"}[self.species])
        row("Pet:", tk.OptionMenu(win, species_var, "Blob", "Cat", "Puppy",
                                  "Robot", "Spirit", "Muse", "Real Cat",
                                  "Real Dog", "Real Kitty"), 1)
        color_name = settings.get("pet_color_name", "yellow")
        color_var = tk.StringVar(value=color_name)
        row("Colour:", tk.OptionMenu(win, color_var,
                                     *sorted(PET_BODY_COLORS)), 2)
        size_var = tk.IntVar(value=self.pet_size)
        row("Pet size:", tk.Spinbox(win, from_=120, to=280,
                                    textvariable=size_var, width=5,
                                    font=("Segoe UI", 10)), 3)
        speed_var = tk.StringVar(value=self.move_speed.capitalize())
        row("Move speed:", tk.OptionMenu(win, speed_var, "Slow", "Normal",
                                         "Fast"), 4)
        greet_var = tk.StringVar(value=settings.get("greeting", ""))
        row("Greeting:", tk.Entry(win, textvariable=greet_var,
                                  font=("Segoe UI", 10)), 5)
        font_var = tk.IntVar(value=settings.get("chat_font", 11))
        row("Chat text size:", tk.Spinbox(win, from_=10, to=20,
                                          textvariable=font_var, width=5,
                                          font=("Segoe UI", 10)), 6)
        voice_var = tk.BooleanVar(value=self.voice_enabled)
        row("Speak replies aloud:", tk.Checkbutton(win, variable=voice_var), 7)
        volume_var = tk.IntVar(value=self.voice_volume)
        row("Voice volume:", tk.Spinbox(win, from_=0, to=100,
                                        textvariable=volume_var, width=5,
                                        font=("Segoe UI", 10)), 8)
        autonomy_var = tk.BooleanVar(value=self.autonomy)
        row("Wander & play on its own:", tk.Checkbutton(win, variable=autonomy_var), 9)
        confirm_var = tk.StringVar(
            value=settings.get("confirm_mode", "standard").capitalize())
        row("Confirmation mode:", tk.OptionMenu(win, confirm_var, "Standard",
                                                "Strict"), 10)
        backend_var = tk.StringVar(
            value={"off": "Off", "ollama": "Ollama", "lmstudio": "LM Studio",
                   "custom": "Custom API"}.get(
                       settings.get("llm_backend", "off"), "Off"))
        row("AI backend:", tk.OptionMenu(win, backend_var, "Off", "Ollama",
                                         "LM Studio", "Custom API"), 11)
        model_var = tk.StringVar(value=settings.get("llm_model", ""))
        row("AI model:", tk.Entry(win, textvariable=model_var,
                                  font=("Segoe UI", 10)), 12)
        base_var = tk.StringVar(value=settings.get("llm_base", ""))
        row("AI server URL:", tk.Entry(win, textvariable=base_var,
                                       font=("Segoe UI", 10)), 13)
        key_var = tk.StringVar(value=settings.get("llm_key", ""))
        row("AI API key:", tk.Entry(win, textvariable=key_var, show="•",
                                    font=("Segoe UI", 10)), 14)
        vars_.update(name=name_var, species=species_var, color=color_var,
                     size=size_var, speed=speed_var, greet=greet_var,
                     font=font_var, voice=voice_var, volume=volume_var,
                     autonomy=autonomy_var, confirm=confirm_var,
                     backend=backend_var, model=model_var, base=base_var,
                     key=key_var)
        self._settings_vars = vars_
        win.columnconfigure(1, weight=1)
        btns = tk.Frame(win)
        btns.grid(row=15, column=0, columnspan=2, pady=14)
        tk.Button(btns, text="Save", command=self._save_settings_window,
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=self._close_settings,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)
        tk.Button(btns, text="Reset to defaults",
                  command=self._reset_settings_window,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)

    def _close_settings(self):
        if self.settings_win is not None:
            self.settings_win.destroy()
            self.settings_win = None

    def _save_settings_window(self):
        v = self._settings_vars
        from tools import load_settings, save_settings
        settings = load_settings()
        name = v["name"].get().strip() or "Buddy"
        species = v["species"].get().lower().replace(" ", "_")
        color_name = v["color"].get()
        backend = {"Off": "off", "Ollama": "ollama", "LM Studio": "lmstudio",
                   "Custom API": "custom"}[v["backend"].get()]
        settings.update(
            pet_name=name,
            pet_species=species if species in ("blob", "cat", "puppy", "robot",
                                               "spirit", "muse", "real_cat",
                                               "real_dog", "real_kitty") else "real_cat",
            pet_color=PET_BODY_COLORS.get(color_name, "#FFD66B"),
            pet_color_name=color_name,
            pet_size=max(120, min(280, v["size"].get())),
            move_speed=v["speed"].get().lower(),
            greeting=v["greet"].get().strip(),
            chat_font=max(10, min(20, v["font"].get())),
            voice=bool(v["voice"].get()),
            voice_volume=max(0, min(100, v["volume"].get())),
            autonomy=bool(v["autonomy"].get()),
            confirm_mode=v["confirm"].get().lower(),
            llm_backend=backend,
            llm_model=v["model"].get().strip(),
            llm_base=v["base"].get().strip(),
            llm_key=v["key"].get())
        save_settings(settings)
        self._apply_settings({"pet_name": name, "pet_species": settings["pet_species"],
                              "pet_color": settings["pet_color"],
                              "pet_size": settings["pet_size"],
                              "move_speed": settings["move_speed"],
                              "chat_font": settings["chat_font"],
                              "voice": settings["voice"],
                              "voice_volume": settings["voice_volume"],
                              "autonomy": settings["autonomy"]})
        self._close_settings()

    def _reset_settings_window(self):
        v = self._settings_vars
        v["name"].set("Buddy")
        v["species"].set("Blob")
        v["color"].set("yellow")
        v["size"].set(180)
        v["speed"].set("Normal")
        v["greet"].set("")
        v["font"].set(11)
        v["voice"].set(True)
        v["volume"].set(100)
        v["autonomy"].set(True)
        v["confirm"].set("Standard")
        v["backend"].set("Off")
        v["model"].set("")
        v["base"].set("")
        v["key"].set("")

    # -- animation + reminders -----------------------------------------
    def _animate(self):
        frame = self.animator.update()
        try:
            mx = self.pet_win.winfo_pointerx()
            my = self.pet_win.winfo_pointery()
            px, py = self._pet_pos()
            half = self.pet_size // 2
            look = (max(-5, min(5, (mx - (px + half)) // 30)),
                    max(-5, min(5, (my - (py + half)) // 30)))
        except Exception:
            look = (0, 0)
        frame["look"] = look
        if self.species in PHOTO_SPECIES:
            frames = self._get_gif_frames(self.species)
            if frames:
                gif_frame = frames[(frame["tick"] // 2) % len(frames)]
                draw_photo_pet(self.canvas, frame, gif_frame,
                               size=self.pet_size)
            else:
                photo = self._get_photo(self.species)
                if photo is not None:
                    draw_photo_pet(self.canvas, frame, photo,
                                   size=self.pet_size)
                else:
                    draw_pet(self.canvas, frame,
                             body_color=self.animator.body_color,
                             species=self.species, look=look)
        else:
            draw_pet(self.canvas, frame, body_color=self.animator.body_color,
                     species=self.species, look=look)
        mood = frame["mood"]
        self.mood_label.configure(text="" if mood == "idle" else mood)
        self.root.after(70, self._animate)

    def _poll_reminders(self):
        try:
            while True:
                message = self.reminder_queue.get_nowait()
                self.animator.set_mood("happy", seconds=4.0)
                messagebox.showinfo("Buddy reminds you", message)
        except queue.Empty:
            pass
        self.root.after(500, self._poll_reminders)
