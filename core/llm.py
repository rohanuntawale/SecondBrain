"""The ONLY file that knows about a specific LLM vendor.

Everything else calls `chat(system, user)`. The provider is chosen by the
LLM_PROVIDER env var: "ollama" (local, offline) or "groq" (free hosted API).
"""

from __future__ import annotations

try:
    from . import config
except ImportError:  # allow running directly: python core/llm.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import config


class LLMError(RuntimeError):
    """Raised when no provider is reachable / configured."""


def chat(system: str, user: str) -> str:
    """Send a system + user message to the configured provider, return the text."""
    provider = config.LLM_PROVIDER
    if provider == "ollama":
        return _chat_ollama(system, user)
    if provider == "groq":
        return _chat_groq(system, user)
    raise LLMError(
        f"Unknown LLM_PROVIDER={provider!r}. Set it to 'ollama' or 'groq' in .env."
    )


def _chat_ollama(system: str, user: str) -> str:
    try:
        import ollama
    except ImportError as e:  # pragma: no cover
        raise LLMError("The 'ollama' package is not installed.") from e

    try:
        resp = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        raise LLMError(
            "Could not reach Ollama. Is it installed and running? "
            f"Try `ollama pull {config.OLLAMA_MODEL}`. Original error: {e}"
        ) from e


def _chat_groq(system: str, user: str) -> str:
    if not config.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is empty. Add it to .env or Streamlit secrets.")
    try:
        from groq import Groq
    except ImportError as e:  # pragma: no cover
        raise LLMError("The 'groq' package is not installed.") from e

    try:
        client = Groq(api_key=config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content
        if content is None:
            raise LLMError("Groq returned no text content (message.content is None).")
        return content.strip()
    except Exception as e:
        raise LLMError(f"Groq API call failed: {e}") from e


if __name__ == "__main__":
    print(chat("Be brief.", "Say hi in five words."))
