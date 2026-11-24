"""Small dependency-free Gemini model discovery and JSON generation client."""

import functools
import itertools
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
# Probed 2026-11-24 with this project's key: 3-flash-preview and 3.5-flash-lite answer in
# 2-4 s; newer 3.x flash models were returning 503 (demand), 2.5-* 404 (retired).
PREFERRED_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
)
REQUEST_TIMEOUT = 30


class GeminiConfigurationError(RuntimeError):
    """Raised when the Gemini key or a usable model is unavailable."""


def _keys() -> list[str]:
    """GEMINI_API_KEYS=k1,k2,... (rotated) plus GEMINI_API_KEY, de-duplicated, in order."""
    keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    single = os.getenv("GEMINI_API_KEY", "").strip()
    if single:
        keys.append(single)
    return list(dict.fromkeys(keys))


_key_counter = itertools.count()


def _api_key() -> str:
    """Round-robin over the configured keys so parallel batch jobs spread their quota."""
    keys = _keys()
    if not keys:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured in .env")
    return keys[next(_key_counter) % len(keys)]


def list_models() -> list[str]:
    """Return models available to the configured key for text generation."""
    url = f"{API_ROOT}/models?key={quote(_api_key())}"
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise GeminiConfigurationError(f"Could not list Gemini models: {exc}") from exc

    return [
        model["name"].removeprefix("models/")
        for model in payload.get("models", [])
        if "generateContent" in model.get("supportedGenerationMethods", [])
    ]


@functools.lru_cache(maxsize=1)
def _cached_models() -> tuple[str, ...]:
    return tuple(list_models())


def choose_model(available: list[str] | None = None) -> str:
    """Choose the configured model when valid, otherwise the best available Flash model."""
    available = available if available is not None else list(_cached_models())
    configured = os.getenv("GEMINI_MODEL", "").strip()
    if configured in available:
        return configured
    for preferred in PREFERRED_MODELS:
        if preferred in available:
            return preferred
    flash_models = sorted(model for model in available if "flash" in model.lower())
    if flash_models:
        return flash_models[0]
    if available:
        return available[0]
    raise GeminiConfigurationError("No Gemini model supports generateContent for this key")


def generate_json(prompt: str, model: str | None = None) -> dict:
    """Generate a JSON object (JSON mode, temperature 0.1). Rotates API keys on retry."""
    selected_model = model or choose_model()
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    max_retries = max(3, len(_keys()) + 1)
    for attempt in range(max_retries):
        url = f"{API_ROOT}/models/{quote(selected_model, safe='')}:generateContent?key={quote(_api_key())}"
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait_time = 2.0 * (attempt + 1)
                time.sleep(wait_time)
                continue
            raise GeminiConfigurationError(f"Gemini request failed for {selected_model}: {exc}") from exc
        except (URLError, Exception) as exc:
            if attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise GeminiConfigurationError(f"Gemini request failed for {selected_model}: {exc}") from exc

    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)