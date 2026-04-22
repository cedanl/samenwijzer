"""Gedeelde OpenAI client helper (embeddings)."""

from os import environ

from openai import OpenAI


def _client(api_key: str | None = None) -> OpenAI:
    return OpenAI(api_key=api_key or environ.get("OPENAI_API_KEY"))
