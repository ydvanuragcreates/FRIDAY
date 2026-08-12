from langchain_anthropic import ChatAnthropic

from app.core.config import get_settings


def get_chat_model() -> ChatAnthropic:
    """Factory for the shared Claude chat model, configured from settings.

    Each graph node builds its own `prompt | get_chat_model() | parser`
    chain around this — construction is cheap (no network call), so a
    fresh instance per node call keeps each node self-contained.
    """
    settings = get_settings()
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=1024,
    )
