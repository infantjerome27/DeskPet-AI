import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from tools import (ToolError, create_file, delete_file, list_files, read_file,
                   safe_calculate, search_files, system_info)


class ToolsTests(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(safe_calculate("2 + 3 * 4"), 14)
        self.assertEqual(safe_calculate("(10 - 4) / 2"), 3.0)
        self.assertEqual(safe_calculate("2 ** 3"), 8)

    def test_calculator_rejects_names_and_code(self):
        for bad in ("__import__('os')", "open('x')", "1; import os", "abc + 1"):
            with self.assertRaises(ToolError):
                safe_calculate(bad)

    def test_calculator_division_by_zero(self):
        with self.assertRaises(ToolError):
            safe_calculate("1 / 0")

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hello.txt")
            create_file(path, "Hello Buddy")
            self.assertEqual(read_file(path), "Hello Buddy")
            reply, entries = list_files(tmp)
            self.assertIn("hello.txt", reply)
            delete_file(path)
            self.assertFalse(os.path.exists(path))

    def test_read_missing_file_errors(self):
        with self.assertRaises(ToolError):
            read_file("/definitely/not/a/real/file.txt")

    def test_delete_refuses_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                delete_file(tmp)

    def test_search_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_file(os.path.join(tmp, "a.txt"), "happy birthday to you")
            create_file(os.path.join(tmp, "b.txt"), "nothing here")
            hits = search_files("birthday", tmp)
            self.assertEqual(len(hits), 1)
            self.assertTrue(hits[0].endswith("a.txt"))

    def test_system_info_has_keys(self):
        info = system_info()
        self.assertIn("System", info)
        self.assertIn("CPU cores", info)


if __name__ == "__main__":
    unittest.main()
