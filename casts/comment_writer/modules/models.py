"""LLM provider bridge using the same config as the API."""
from src.llm.provider import get_llm_client, llm_readiness


def get_comment_generation_client(provider: str | None = None):
    if provider is not None:
        raise ValueError("Set LLM_PROVIDER in the environment; per-call overrides are not supported")
    return get_llm_client()


def comment_generation_readiness(provider: str | None = None) -> dict:
    if provider is not None:
        raise ValueError("Set LLM_PROVIDER in the environment; per-call overrides are not supported")
    return llm_readiness()
