"""
Shared LLM configuration for all CrewAI agents.
Reads ANTHROPIC_API_KEY from environment (set in .env).
"""

import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

_api_key = os.getenv("ANTHROPIC_API_KEY", "")

if not _api_key or _api_key == "your_key_here":
    raise EnvironmentError(
        "\n\nANTHROPIC_API_KEY is not set.\n"
        "Copy .env.example to .env and add your key:\n"
        "  ANTHROPIC_API_KEY=sk-ant-...\n"
        "Then re-run the CLI.\n"
    )

# crewai 1.x uses litellm internally; Anthropic models use the 'anthropic/' prefix
fap_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    api_key=_api_key,
    temperature=0.0,     # deterministic for compliance decisions
    max_tokens=2048,
)
