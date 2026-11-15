import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image


class GifTests(unittest.TestCase):
    def test_gif_files_are_real_animated_gifs(self):
        base = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "pets")
        for name in ("real_cat", "real_dog", "real_kitty"):
            path = os.path.join(base, name + ".gif")
            self.assertTrue(os.path.isfile(path), f"missing {path}")
            gif = Image.open(path)
            self.assertGreaterEqual(getattr(gif, "n_frames", 1), 10)
            self.assertEqual(gif.size[1], 180)

    def test_gif_frames_have_transparency(self):
        base = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "pets")
        gif = Image.open(os.path.join(base, "real_cat.gif"))
        gif.seek(0)
        frame = gif.convert("RGBA")
        alphas = frame.split()[3]
        self.assertLess(min(alphas.getdata()), 255)  # some transparent pixels
        self.assertGreater(max(alphas.getdata()), 0)  # and some opaque ones


if __name__ == "__main__":
    unittest.main()
