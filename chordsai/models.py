"""Chooses which Groq model to use.

Groq retires models regularly (the original prototype used `qwen-qwq-32b`, which no
longer exists). Instead of hard-coding one model, the app asks Groq which models this
account can use, once, and picks the first one from a preference list.
An explicit GROQ_MODEL wins. Same approach as the car rental chatbot.
"""

import logging

log = logging.getLogger(__name__)

# Models with reliable tool calling on Groq's free tier, best first.
PREFERENCES = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]


def choose(override: str | None, preferences: list[str], available: set[str] | None) -> str:
    """Override if given; otherwise the first preferred model the account has.

    `available` is None when the list could not be fetched: then trust the preferences.
    """
    if override:
        if available is not None and override not in available:
            log.warning("Configured model %s is not in this account's model list", override)
        return override
    if available is not None:
        for model in preferences:
            if model in available:
                return model
        raise RuntimeError(
            f"None of the preferred Groq models is available ({', '.join(preferences)}). "
            "Set GROQ_MODEL to a model listed at https://console.groq.com/docs/models"
        )
    return preferences[0]


def available_models(api_key: str) -> set[str] | None:
    """IDs of the models this API key can use, or None if Groq could not be asked."""
    try:
        from groq import Groq

        return {model.id for model in Groq(api_key=api_key, timeout=15).models.list().data}
    except Exception as error:  # noqa: BLE001 — fall back to the preference list
        log.warning("Could not list Groq models (%s); using defaults", type(error).__name__)
        return None


def resolve_model(api_key: str, override: str | None) -> str:
    model = choose(override, PREFERENCES, available_models(api_key))
    log.info("Using Groq model %s", model)
    return model


def model_options(model: str) -> dict:
    """Extra settings for reasoning models, so answers come quickly and without visible reasoning."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    if model.startswith("qwen/"):
        return {"reasoning_format": "hidden"}
    return {}
