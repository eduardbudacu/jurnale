"""Shared text-embedding helper.

The query embedding (dashboard search / ask) and the stored page embeddings
MUST be produced by the same provider+model, or cosine similarity is
meaningless. Route every embedding call through `embed_text` so they can never
drift apart.
"""
import os
import threading

import requests

EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "openai")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "llama3.2")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

# text-embedding-3 caps input at 8191 tokens; clip defensively (~4 chars/token).
EMBED_MAX_CHARS = int(os.environ.get("EMBED_MAX_CHARS", "24000"))

_client = None
_client_lock = threading.Lock()


def _openai_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                from openai import OpenAI
                _client = OpenAI()
    return _client


def describe() -> str:
    """Human-readable name of the active embedding model (for log lines)."""
    if EMBEDDING_PROVIDER == "ollama":
        return f"ollama:{OLLAMA_EMBEDDING_MODEL}"
    return f"openai:{OPENAI_EMBEDDING_MODEL}"


def embed_text(text: str) -> list[float]:
    """Embed a single string into a vector using the configured provider."""
    text = (text or "")[:EMBED_MAX_CHARS]

    if EMBEDDING_PROVIDER == "ollama":
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": OLLAMA_EMBEDDING_MODEL, "input": text},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    # default: openai
    resp = _openai_client().embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding
