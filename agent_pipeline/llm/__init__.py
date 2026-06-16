"""LLM provider layer. Anthropic Claude in production; deterministic mock offline."""
from .client import LLMResponse, get_llm

__all__ = ["get_llm", "LLMResponse"]
