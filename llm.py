"""Optional AI backends for Buddy: Ollama, LM Studio, or any
OpenAI-compatible API. All calls are plain HTTP via urllib (stdlib only).

Nothing here is required: with no backend configured Buddy keeps working
exactly as before with its local command brain. A backend only adds the
`ask ai ...` command — open-ended answers from a model you run or rent.

Backends are chosen from settings:
  llm_backend: "off" | "ollama" | "lmstudio" | "custom"
  llm_model:   model name, e.g. "llama3" (Ollama) or a local model id
  llm_base:    base URL for "custom" (default Ollama/LM Studio defaults)
  llm_key:    API key for "custom" (kept in Buddy's own settings file on
               your PC; prefer Ollama/LM Studio for fully offline use)
"""
import json
import urllib.error
import urllib.request

from tools import ToolError

DEFAULTS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
}


def describe_backend(settings):
    backend = (settings.get("llm_backend") or "off").lower()
    if backend == "off":
        return None
    return {
        "backend": backend,
        "model": settings.get("llm_model") or "",
        "base": settings.get("llm_base") or DEFAULTS.get(backend, ""),
        "key": settings.get("llm_key") or "",
    }


def ask_ai(prompt, settings, opener=None):
    """Ask the configured backend. `opener` is injectable for tests:
    opener(url, payload_dict) -> response_dict."""
    config = describe_backend(settings)
    if config is None:
        raise ToolError(
            "No AI backend is configured. To switch Buddy's open-ended "
            "answers on: install Ollama (https://ollama.com), pull a model "
            "(`ollama pull llama3`), then set AI backend to Ollama in "
            "Buddy's Settings page — or point it at LM Studio / a custom "
            "OpenAI-compatible API. Until then Buddy still handles every "
            "task command offline.")
    if not config["model"]:
        raise ToolError("An AI backend is selected but no model name is set. "
                        "Set the model in Buddy's Settings page.")
    prompt = (prompt or "").strip()
    if not prompt:
        raise ToolError("Ask me something, e.g. 'ask ai what is a black hole'.")
    if config["backend"] == "ollama":
        url = config["base"].rstrip("/") + "/api/generate"
        payload = {"model": config["model"], "prompt": prompt,
                   "stream": False}
        kind = "ollama"
    else:
        url = config["base"].rstrip("/") + "/chat/completions"
        payload = {"model": config["model"],
                   "messages": [{"role": "user", "content": prompt}]}
        kind = "openai"
    try:
        if opener is not None:
            data = opener(url, payload)
        else:
            data = _post_json(url, payload, config["key"])
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"I couldn't reach the AI backend at {config['base']}: "
                        f"{e}. Is it running?")
    try:
        if kind == "ollama":
            text = data["response"]
        else:
            text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ToolError("The AI backend answered in a format I don't "
                        "understand.")
    text = (text or "").strip()
    if not text:
        raise ToolError("The AI backend returned an empty answer.")
    return text


def _post_json(url, payload, api_key):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {api_key}"} if api_key else {})},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ToolError(f"The AI backend answered with an error: {e.code}. "
                        f"Check the model name and that the server is up.")
    except Exception as e:
        raise ToolError(f"I couldn't reach the AI backend: {e}.")
