"""Wrapper around the language model API.

Model, endpoint and key come from .env, so any OpenAI-compatible provider works.
"""

from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT

# With no key we still build the client, so the error comes back from the API
# instead of crashing at import time.
# Free-tier requests sometimes hang for 30-60 seconds. Giving up after 6 s and
# retrying is much faster, and the retries also cover the rate limit.
_client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY or "missing-key",
    timeout=LLM_TIMEOUT,
    max_retries=3,
)


def chat(messages, tools=None):
    """Send a conversation to the model and return its reply message."""
    # Only send "tools" when the agent has some: some providers reject a null.
    options = {"tools": tools} if tools else {}
    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0,
        **options,
    )
    return response.choices[0].message
