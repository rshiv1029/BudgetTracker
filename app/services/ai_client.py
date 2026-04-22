"""
AI client that routes to Ollama (local) or Gemini Flash (fallback).
Both expose the same async interface: complete(prompt) -> str
"""
import os
import httpx

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"
FORCE_GEMINI = os.getenv("FORCE_GEMINI", "false").lower() == "true"


async def _ollama_complete(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]


async def _gemini_complete(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, params={"key": GEMINI_API_KEY})
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _ollama_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def complete(prompt: str) -> tuple[str, str]:
    """Returns (response_text, source) where source is 'ollama' or 'gemini'."""
    if not FORCE_GEMINI and await _ollama_healthy():
        try:
            text = await _ollama_complete(prompt)
            return text, "ollama"
        except Exception:
            pass  # fall through to Gemini

    text = await _gemini_complete(prompt)
    return text, "gemini"