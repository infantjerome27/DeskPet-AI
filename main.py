"""Buddy - your offline desktop pet AI. Entry point.

Run:  python main.py
No installs needed beyond Python itself (tkinter ships with Python).
Optional smoke test:  python main.py --smoke 3   (auto-quits after 3 seconds)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk  # noqa: E402

from brain import Brain  # noqa: E402
from tools import ReminderService, load_settings  # noqa: E402
from ui import BuddyApp  # noqa: E402


def main():
    smoke = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--smoke":
        try:
            smoke = float(sys.argv[2])
        except ValueError:
            smoke = 3.0

    brain = Brain(reminders=ReminderService())
    try:
        brain.user_name = load_settings().get("user_name")
    except Exception:
        pass

    root = tk.Tk()
    root.withdraw()  # only the pet + chat windows are shown
    app = BuddyApp(root, brain)
    if smoke is not None:
        root.after(int(smoke * 1000), root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
