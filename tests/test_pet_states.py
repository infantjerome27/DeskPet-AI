import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pet import PetAnimator, draw_pet, expression_for


class StubCanvas:
    """Records draw calls instead of painting."""

    def __init__(self):
        self.calls = []

    def delete(self, *args):
        self.calls.append(("delete", args, {}))

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return len(self.calls)
        return record


def make_frame(mood="idle", tick=5, moving=False):
    anim = PetAnimator()
    anim.tick = tick
    anim.mood = mood
    anim.moving = moving
    frame = anim.update()
    frame["tick"] = tick
    frame["blinking"] = False
    return frame


def kinds(canvas, name):
    return [c for c in canvas.calls if c[0] == name]


class PetStateTests(unittest.TestCase):
    def test_cat_has_triangle_ears_and_whiskers(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="cat")
        self.assertGreaterEqual(len(kinds(canvas, "create_polygon")), 4)
        self.assertGreater(len(kinds(canvas, "create_line")), 6)

    def test_puppy_has_floppy_ears(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="puppy")
        ovals = kinds(canvas, "create_oval")
        # Head + ears + snout + nose + blush + paws + body: plenty of ovals.
        self.assertGreater(len(ovals), 10)

    def test_eyes_track_the_mouse(self):
        def pupil_xs(look):
            canvas = StubCanvas()
            draw_pet(canvas, make_frame(), species="blob", look=look)
            xs = []
            for _, args, kwargs in kinds(canvas, "create_oval"):
                if kwargs.get("fill") == "#3A2E1F" and len(args) == 4:
                    xs.append(args[0])
            return xs

        still = pupil_xs((0, 0))
        moved = pupil_xs((5, 0))
        self.assertTrue(any(m - s == 5 for s, m in zip(still, moved)))

    def test_walking_paws_alternate(self):
        def paw_ys(moving, tick):
            canvas = StubCanvas()
            draw_pet(canvas, make_frame(tick=tick, moving=moving), species="cat")
            return [args[1] for _, args, _ in kinds(canvas, "create_oval")]

        still = paw_ys(False, 0)
        left_step = paw_ys(True, 0)
        right_step = paw_ys(True, 15)
        self.assertNotEqual(still, left_step)
        self.assertNotEqual(left_step, right_step)

    def test_agent_state_expressions(self):
        self.assertIn("bubble", expression_for("thinking")["extras"])
        self.assertIn("typing", expression_for("working")["extras"])
        self.assertEqual(expression_for("busy")["eyes"], "focused")
        self.assertIn("sweat", expression_for("waiting")["extras"])
        self.assertIn("alarm", expression_for("error")["extras"])
        self.assertIn("dance", expression_for("celebrating")["extras"])
        self.assertIn("zzz", expression_for("sleeping")["extras"])

    def test_state_extras_draw(self):
        for mood, marker in (("thinking", "create_oval"),
                             ("waiting", "create_text"),
                             ("error", "create_polygon"),
                             ("sleeping", "create_text"),
                             ("celebrating", "create_text")):
            canvas = StubCanvas()
            draw_pet(canvas, make_frame(mood=mood), species="blob")
            self.assertGreater(len(kinds(canvas, marker)), 0, mood)

    def test_unknown_species_falls_back_to_blob(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="dragon")
        self.assertGreater(len(canvas.calls), 10)

    def test_robot_has_rectangles_and_glowing_eyes(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="robot")
        self.assertGreater(len(kinds(canvas, "create_rectangle")), 5)

    def test_spirit_has_wavy_skirt(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="spirit")
        self.assertGreater(len(kinds(canvas, "create_polygon")), 0)

    def test_muse_has_halo_and_sparkle_emblem(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="muse")
        self.assertGreater(len(kinds(canvas, "create_oval")), 10)
        texts = [kw.get("text") for _, _, kw in kinds(canvas, "create_text")]
        self.assertIn("\u2726", texts)

    def test_blob_has_gloss_and_feet(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="blob")
        self.assertGreater(len(kinds(canvas, "create_oval")), 10)

    def test_photo_pet_falls_back_to_drawn_animal(self):
        canvas = StubCanvas()
        draw_pet(canvas, make_frame(), species="real_cat")
        # Same shapes as the drawn cat, so it never breaks headless.
        self.assertGreater(len(kinds(canvas, "create_polygon")), 0)

    def test_draw_photo_pet_places_image_and_leans(self):
        from pet import draw_photo_pet
        canvas = StubCanvas()
        frame = make_frame()
        frame["look"] = (5, 0)
        draw_photo_pet(canvas, frame, photo_image="IMG", size=180)
        images = kinds(canvas, "create_image")
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0][1][0], 95)  # 90 centre + 5 lean

    def test_cat_head_tilts_toward_mouse(self):
        def head_left(look):
            canvas = StubCanvas()
            draw_pet(canvas, make_frame(), species="cat", look=look)
            ovals = [args for _, args, _ in kinds(canvas, "create_oval")]
            return ovals

        straight = head_left((0, 0))
        right = head_left((5, 0))
        # The head oval is the wide oval highest on the canvas; it shifts
        # right when the pet looks right (the body oval stays put).
        def head_oval(ovals):
            wide = [o for o in ovals if o[2] - o[0] > 90]
            return min(wide, key=lambda o: o[1]) if wide else None
        self.assertGreater(head_oval(right)[0], head_oval(straight)[0])


if __name__ == "__main__":
    unittest.main()
