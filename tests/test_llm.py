import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import ask_ai, describe_backend
from tools import ToolError


class LLMTests(unittest.TestCase):
    def test_off_backend_refuses_honestly(self):
        with self.assertRaises(ToolError) as ctx:
            ask_ai("hello", {})
        self.assertIn("No AI backend", str(ctx.exception))

    def test_ollama_shape(self):
        def fake(url, payload):
            self.assertTrue(url.endswith("/api/generate"))
            self.assertEqual(payload["model"], "llama3")
            return {"response": "  The sky is blue. "}
        self.assertEqual(ask_ai("why is the sky blue?",
                                {"llm_backend": "ollama", "llm_model": "llama3"},
                                opener=fake),
                         "The sky is blue.")

    def test_openai_shape_lmstudio(self):
        def fake(url, payload):
            self.assertTrue(url.endswith("/chat/completions"))
            return {"choices": [{"message": {"content": "Hello!"}}]}
        self.assertEqual(ask_ai("hi",
                                {"llm_backend": "lmstudio",
                                 "llm_model": "local-model"},
                                opener=fake),
                         "Hello!")

    def test_missing_model_refuses(self):
        with self.assertRaises(ToolError):
            ask_ai("hi", {"llm_backend": "ollama"})

    def test_backend_error_becomes_tool_error(self):
        def broken(url, payload):
            raise RuntimeError("connection refused")
        with self.assertRaises(ToolError):
            ask_ai("hi", {"llm_backend": "ollama", "llm_model": "m"},
                   opener=broken)

    def test_describe_backend(self):
        self.assertIsNone(describe_backend({}))
        config = describe_backend({"llm_backend": "ollama",
                                   "llm_model": "llama3"})
        self.assertEqual(config["base"], "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
