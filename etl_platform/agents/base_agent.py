"""
Base Agent.

All agents share the same shape: read from metadata/telemetry, optionally
call an LLM for reasoning/summarization, and write a recommendation or
action back to metadata tables (never directly mutating business data).

The `call_model` method is intentionally a thin, swappable seam: in
production it calls the Anthropic API (or Bedrock) using the model
configured in metadata.agent_registry; in tests/CI it can be monkeypatched
or left disabled via AGENTS_ENABLED=false.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

from etl_platform.config import AGENTS

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    agent_name: str = "BaseAgent"

    def __init__(self, engine=None):
        self.engine = engine

    def call_model(self, prompt: str, system: str | None = None) -> str:
        """
        Call the configured LLM provider. Returns a plain-text response.
        No-ops (returns an empty recommendation) when agents are disabled,
        so the deterministic pipeline never blocks on AI availability.
        """
        if not AGENTS.enabled:
            logger.debug("[%s] Agents disabled; skipping model call", self.agent_name)
            return ""

        if AGENTS.provider == "anthropic":
            return self._call_anthropic(prompt, system)

        raise NotImplementedError(f"Unsupported agent provider '{AGENTS.provider}'")

    def _call_anthropic(self, prompt: str, system: str | None) -> str:
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic SDK not installed; agent '%s' returning empty result", self.agent_name)
            return ""

        client = anthropic.Anthropic(api_key=AGENTS.api_key)
        response = client.messages.create(
            model=AGENTS.model,
            max_tokens=1024,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")

    @abstractmethod
    def run(self, *args, **kwargs) -> dict[str, Any]:
        """Execute the agent's advisory/operational task and return a result dict."""
        raise NotImplementedError
