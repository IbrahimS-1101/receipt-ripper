"""Runtime model discovery and fallback support for Gemini-powered Streamlit apps."""

from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any

DEFAULT_MODEL_CANDIDATES = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
)
MODEL_CACHE_TTL_SECONDS = 15 * 60
_STABLE_FLASH_LITE = re.compile(r"^gemini-\d+(?:\.\d+)+-flash-lite(?:-\d+)?$")
_VERSION = re.compile(r"^gemini-(\d+)\.(\d+)-flash-lite")

# Cache per API-key fingerprint so manual-key users do not share a stale catalog.
_model_cache: dict[str, tuple[float, set[str]]] = {}


def _normalize_model_name(name: str) -> str:
    return name.strip().removeprefix("models/")


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_model_name(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _configured_candidates() -> list[str]:
    preferred = os.getenv("GEMINI_MODEL", "").strip()
    fallbacks = os.getenv("GEMINI_MODEL_FALLBACKS", "").split(",")
    configured = [preferred] if preferred and preferred.lower() != "auto" else []
    return _unique(configured + fallbacks)


def _cache_key(api_key: str | None) -> str:
    value = api_key or "default"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _supports_generate_content(model: Any) -> bool:
    actions = getattr(model, "supported_actions", None)
    if actions is None:
        actions = getattr(model, "supported_generation_methods", None)
    if not actions:
        return True

    normalized = {str(action).replace("_", "").lower() for action in actions}
    return "generatecontent" in normalized or "generate" in normalized


def _discover_available_models(client: Any) -> set[str]:
    names: set[str] = set()
    for model in client.models.list():
        name = getattr(model, "name", None)
        if name and _supports_generate_content(model):
            names.add(_normalize_model_name(name))
    return names


def _available_model_names(client: Any, api_key: str | None) -> set[str] | None:
    key = _cache_key(api_key)
    cached = _model_cache.get(key)
    if cached and cached[0] > time.time():
        return cached[1]

    try:
        names = _discover_available_models(client)
    except Exception as error:
        # Discovery is helpful, but generation can still use bounded fallbacks
        # when the catalog endpoint is temporarily unavailable.
        print(f"Gemini model discovery unavailable; using fallbacks: {error}")
        return None

    _model_cache[key] = (time.time() + MODEL_CACHE_TTL_SECONDS, names)
    return names


def _version_parts(name: str) -> tuple[int, int]:
    match = _VERSION.match(name)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def resolve_gemini_model_candidates(client: Any, api_key: str | None = None) -> list[str]:
    configured = _configured_candidates()
    available = _available_model_names(client, api_key)

    if available is None:
        return _unique(configured + list(DEFAULT_MODEL_CANDIDATES))

    discovered = sorted(
        (name for name in available if _STABLE_FLASH_LITE.fullmatch(name)),
        key=_version_parts,
        reverse=True,
    )
    configured_available = [name for name in configured if name in available]
    defaults_available = [name for name in DEFAULT_MODEL_CANDIDATES if name in available]
    candidates = _unique(configured_available + discovered + defaults_available)

    # Keep the app usable if the API catalog changes shape unexpectedly.
    return candidates or _unique(configured + list(DEFAULT_MODEL_CANDIDATES))


def is_gemini_model_availability_error(error: Exception) -> bool:
    message = str(error)
    lowered = message.lower()
    if "404" in message and "model" in lowered:
        return True
    return bool(
        re.search(
            r"(?:model|endpoint).*(?:not found|not exist|unsupported|unavailable|deprecated|shutdown|shut down|invalid)"
            r"|(?:not found|not exist|unsupported|unavailable|deprecated|shutdown|shut down|invalid).*(?:model|endpoint)",
            message,
            re.IGNORECASE,
        )
    )


def reset_gemini_model_cache(api_key: str | None = None) -> None:
    if api_key is None:
        _model_cache.clear()
    else:
        _model_cache.pop(_cache_key(api_key), None)


def create_gemini_client(api_key: str) -> Any:
    from google import genai

    return genai.Client(api_key=api_key)


def get_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned an empty response.")
    return text.strip()


def generate_content_with_fallback(
    client: Any,
    contents: Any,
    api_key: str | None = None,
) -> tuple[Any, str]:
    candidates = resolve_gemini_model_candidates(client, api_key)
    last_model_error: Exception | None = None

    for model_name in candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            return response, model_name
        except Exception as error:
            last_model_error = error
            if not is_gemini_model_availability_error(error):
                raise
            # A cached catalog can outlive a model. Force fresh discovery on
            # the next request after skipping this unavailable candidate.
            reset_gemini_model_cache(api_key)

    raise last_model_error or RuntimeError("No available Gemini model was found.")
