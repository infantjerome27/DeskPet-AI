import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from tools import ReminderService, load_settings
from ui import BuddyApp


class UITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(tools, "get_data_dir",
                                    return_value=self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.brain = Brain(launcher=lambda *a: None, opener=lambda u: None,
                           reminders=ReminderService())
        self.app = BuddyApp(self.root, self.brain)
        self.root.update()

    def tearDown(self):
        self.app.pet_win.destroy()
        self.app.chat_win.destroy()
        self.root.destroy()

    def _pump(self, seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            time.sleep(0.02)

    def _ev(self, x, y):
        return SimpleNamespace(x_root=x, y_root=y)

    def test_click_opens_chat_even_with_tiny_jitter(self):
        x, y = self.app.pet_win.winfo_x(), self.app.pet_win.winfo_y()
        self.app._drag_start(self._ev(x + 50, y + 50))
        self.app._drag_release(self._ev(x + 52, y + 51))
        self._pump()
        self.assertTrue(self.app.chat_visible)

    def test_drag_moves_pet_without_opening_chat(self):
        x, y = self.app.pet_win.winfo_x(), self.app.pet_win.winfo_y()
        self.app._drag_start(self._ev(x + 50, y + 50))
        self.app._drag_move(self._ev(x + 200, y + 180))
        self.app._drag_release(self._ev(x + 200, y + 180))
        self._pump()
        self.assertFalse(self.app.chat_visible)
        self.assertEqual((self.app.pet_win.winfo_x(),
                          self.app.pet_win.winfo_y()), (x + 150, y + 130))
        # The new spot is remembered.
        self.assertEqual(load_settings().get("pet_x"), x + 150)
        self.assertEqual(load_settings().get("pet_y"), y + 130)

    def test_double_click_plays_trick_instead_of_chat(self):
        x, y = self.app.pet_win.winfo_x(), self.app.pet_win.winfo_y()
        self.app._drag_start(self._ev(x + 50, y + 50))
        self.app._drag_release(self._ev(x + 50, y + 50))
        self.app._double_click(self._ev(x + 50, y + 50))
        self._pump()
        self.assertFalse(self.app.chat_visible)
        self.assertEqual(self.app.animator.mood, "love")

    def test_quick_help_reaches_brain_and_shows_reply(self):
        self.app._quick("help")
        # Replies arrive asynchronously through the reply queue.
        deadline = time.time() + 5
        while time.time() < deadline:
            self.root.update()
            if "what I can do" in self.app.history.get("1.0", "end"):
                break
            time.sleep(0.05)
        self.assertIn("what I can do", self.app.history.get("1.0", "end"))

    def test_settings_window_changes_species(self):
        self.app._open_settings()
        self.assertIsNotNone(self.app.settings_win)
        self.app._settings_vars["species"].set("Cat")
        self.app._settings_vars["name"].set("Mittens")
        self.app._save_settings_window()
        self.assertEqual(self.app.species, "cat")
        self.assertEqual(self.app.pet_name, "Mittens")
        self.assertIsNone(self.app.settings_win)

    def test_mic_button_sends_recognised_text(self):
        app2 = None
        try:
            import tkinter as tk
            from ui import BuddyApp
            app2 = BuddyApp(self.root, self.brain,
                            listener=lambda: "hello buddy")
            self.root.update()
            app2._on_mic()
            deadline = time.time() + 5
            while time.time() < deadline:
                self.root.update()
                if "hello buddy" in app2.history.get("1.0", "end"):
                    break
                time.sleep(0.05)
            self.assertIn("hello buddy", app2.history.get("1.0", "end"))
        finally:
            if app2 is not None:
                app2.pet_win.destroy()
                app2.chat_win.destroy()

    def test_sleep_after_idle_and_wake_on_activity(self):
        self.app._last_activity = time.time() - 61
        self.app.animator.set_mood("idle", seconds=0)
        self.app._idle_check()
        self.assertEqual(self.app.animator.mood, "sleeping")
        self.app._mark_activity()
        self.assertEqual(self.app.animator.mood, "happy")

    def test_approval_popup_appears_for_waiting_reply(self):
        self.app.reply_queue.put(
            ("Are you sure you want to delete x.txt? Reply 'yes' or 'no'.",
             "waiting", {}))
        self.root.update()
        deadline = time.time() + 3
        while time.time() < deadline and self.app.approval_win is None:
            self.root.update()
            time.sleep(0.05)
        self.assertIsNotNone(self.app.approval_win)
        self.app._close_approval()

    def test_pet_size_applies(self):
        self.app._apply_pet_size(240)
        self.assertEqual(self.app.pet_size, 240)
        self.assertEqual(int(self.app.canvas.cget("width")), 240)

    def test_photo_pet_loads_and_unknown_species_returns_none(self):
        self.assertIsNone(self.app._get_photo("cat"))
        photo = self.app._get_photo("real_cat")
        self.assertIsNotNone(photo)
        # Cached on the second call.
        self.assertIs(photo, self.app._get_photo("real_cat"))

    def test_gif_frames_load_and_animate(self):
        self.assertEqual(self.app._get_gif_frames("cat"), [])
        frames = self.app._get_gif_frames("real_cat")
        self.assertGreater(len(frames), 1)
        # Cached, and the animation advances with the tick.
        self.assertIs(frames, self.app._get_gif_frames("real_cat"))

    def test_autonomy_glide_moves_pet(self):
        x, y = self.app.pet_win.winfo_x(), self.app.pet_win.winfo_y()
        target_x, target_y = x + 60, y + 40
        self.app._glide_to(target_x, target_y)
        deadline = time.time() + 5
        while time.time() < deadline:
            self.root.update()
            if (self.app.pet_win.winfo_x(),
                    self.app.pet_win.winfo_y()) == (target_x, target_y):
                break
            time.sleep(0.02)
        self.assertEqual((self.app.pet_win.winfo_x(),
                          self.app.pet_win.winfo_y()), (target_x, target_y))

    def test_startup_command_reports_platform_limit(self):
        reply, _ = self.brain.handle("start with windows")
        self.assertIn("only works on Windows", reply)


if __name__ == "__main__":
    unittest.main()
