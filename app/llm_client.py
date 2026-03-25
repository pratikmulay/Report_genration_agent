"""
Unified async LLM client supporting multiple providers via LangChain:
Ollama, Claude (Anthropic), OpenAI, Groq, and MCP (Model Context Protocol).
"""

import json
import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Multi-provider LLM client for narrative generation using LangChain."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a professional report writer.",
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        provider = self.provider.lower()

        # Auto-select Groq when key is available and provider isn't forced to ollama
        if getattr(settings, "XAI_API_KEY", "") and provider not in ("ollama", "claude", "openai"):
            provider = "grok"
        elif getattr(settings, "GROQ_API_KEY", "") and provider not in ("ollama", "claude", "openai"):
            provider = "groq"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        try:
            if provider == "grok":
                llm = ChatOpenAI(api_key=settings.XAI_API_KEY, base_url="https://api.x.ai/v1", model="grok-2-latest", max_tokens=max_tokens, temperature=temperature)
            elif provider == "ollama":
                llm = ChatOllama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL, temperature=temperature)
            elif provider == "groq":
                llm = ChatGroq(api_key=settings.GROQ_API_KEY, model_name=settings.GROQ_MODEL, max_tokens=max_tokens, temperature=temperature)
            elif provider == "claude":
                llm = ChatAnthropic(api_key=settings.ANTHROPIC_API_KEY, model_name=settings.CLAUDE_MODEL, max_tokens=max_tokens, temperature=temperature)
            elif provider == "openai":
                llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY, model_name=settings.OPENAI_MODEL, max_tokens=max_tokens, temperature=temperature)
            elif provider == "mcp":
                llm = ChatOpenAI(api_key=getattr(settings, "OPENAI_API_KEY", ""), model_name="gpt-4o", max_tokens=max_tokens, temperature=temperature)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")

            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM generation failed ({provider}): {e}")
            raise

# Singleton instance
llm_client = LLMClient()
