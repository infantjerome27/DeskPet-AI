import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pet import PetAnimator, expression_for


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PetTests(unittest.TestCase):
    def test_expressions_exist_for_all_moods(self):
        for mood in ("idle", "happy", "thinking", "sad", "love",
                     "speaking", "listening"):
            expr = expression_for(mood)
            self.assertIn("eyes", expr)
            self.assertIn("mouth", expr)

    def test_unknown_mood_falls_back_to_idle(self):
        self.assertEqual(expression_for("confused")["mouth"], "smile")

    def test_mood_reverts_to_idle_after_timeout(self):
        clock = FakeClock()
        pet = PetAnimator(time_fn=clock)
        pet.set_mood("happy", seconds=3.0)
        frame = pet.update()
        self.assertEqual(frame["mood"], "happy")
        clock.now += 5.0
        frame = pet.update()
        self.assertEqual(frame["mood"], "idle")

    def test_happy_bounces(self):
        clock = FakeClock()
        pet = PetAnimator(time_fn=clock)
        pet.set_mood("happy", seconds=60)
        bounces = {pet.update()["bounce"] for _ in range(20)}
        self.assertTrue(any(b < 0 for b in bounces))


if __name__ == "__main__":
    unittest.main()
