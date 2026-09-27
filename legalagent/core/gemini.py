"""Small dependency-free Gemini model discovery and JSON generation client."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
)


class GeminiConfigurationError(RuntimeError):
    """Raised when the Gemini key or a usable model is unavailable."""


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured in .env")
    return key


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


def choose_model(available: list[str] | None = None) -> str:
    """Choose the configured model when valid, otherwise the best available Flash model."""
    available = available if available is not None else list_models()
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
    """Generate a JSON object for the future cross-clause explanation adapter."""
    selected_model = model or choose_model()
    url = f"{API_ROOT}/models/{quote(selected_model, safe='')}:generateContent?key={quote(_api_key())}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise GeminiConfigurationError(f"Gemini request failed for {selected_model}: {exc}") from exc

    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)