"""Paths, limits and the one model every agent uses (GPT-6 Luna through Portkey)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER = ROOT / "MCP_server" / "server.py"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
AUDIT_TRAIL = ROOT / "output" / "audit_trail.json"

# The only model allowed in this project. Not read from the environment on purpose.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# Token guardrails
MAX_OUTPUT_TOKENS = 900          # per model call
BOSS_REQUEST_LIMIT = 12          # model calls in one Boss loop
AGENT_REQUEST_LIMIT = 8          # model calls in one specialist loop
AGENT_TOOL_CALLS_LIMIT = 12      # tool calls in one agent loop
MAX_DELEGATION_DEPTH = 2         # Boss -> A -> B, then B must answer itself
MAX_DELEGATIONS_PER_TICKET = 8   # across all agents working one ticket
MAX_TOKENS_PER_TICKET = 120_000  # input + output, all agents on one ticket
AUDIT_TEXT_LIMIT = 1500          # chars kept per text / tool result in the audit trail


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to .env at the project root.")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIChatModel:
    client = AsyncOpenAI(api_key=require_api_key(), base_url=PORTKEY_BASE_URL)
    # gpt-6-luna rejects function tools on /chat/completions unless reasoning is off.
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
        settings=OpenAIChatModelSettings(
            openai_reasoning_effort="none", max_tokens=MAX_OUTPUT_TOKENS, temperature=0.2
        ),
    )


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
