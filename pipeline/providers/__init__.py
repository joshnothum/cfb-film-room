"""Providers used by coach feedback analysis."""

from pipeline.providers.ollama_provider import OllamaProvider
from pipeline.providers.openai_provider import OpenAIProvider

__all__ = ["OpenAIProvider", "OllamaProvider"]
