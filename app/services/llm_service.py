"""
LLM Service — Routes requests to Claude (reasoning) or BharatGen (Telugu).

Handles PII stripping, prompt loading, token tracking, and error fallbacks.
"""
from pathlib import Path

import anthropic
import structlog

from app.config import get_settings
from app.core.security import strip_pii

logger = structlog.get_logger()
settings = get_settings()

# Prompt templates directory
PROMPTS_DIR = Path(__file__).parent.parent / "data" / "telugu_prompts"

# Cache loaded prompts in memory
_prompt_cache: dict[str, str] = {}


def _load_prompt(name: str) -> str:
    """Load a prompt template from file. Cached after first load."""
    if name not in _prompt_cache:
        filepath = PROMPTS_DIR / f"{name}.txt"
        if filepath.exists():
            _prompt_cache[name] = filepath.read_text(encoding="utf-8")
        else:
            logger.warning("Prompt template not found", name=name)
            _prompt_cache[name] = ""
    return _prompt_cache[name]


class LLMRouter:
    """Routes requests to the appropriate LLM based on task complexity."""

    def __init__(self):
        self.claude_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        # Token usage tracking (for cost monitoring)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def route(self, task_type: str, prompt: str, system_prompt: str = "") -> str:
        """Route to the appropriate LLM and prompt template."""
        # Select system prompt based on task type
        if not system_prompt:
            system_prompt = self._get_system_prompt(task_type)

        if task_type in ("eligibility_reasoning", "form_extraction", "complex_query", "scheme_query"):
            return await self.call_claude(prompt, system_prompt)
        elif task_type in ("greeting", "clarification", "simple_faq"):
            # TODO: Integrate BharatGen Telugu LLM for cheaper simple tasks
            return await self.call_claude(prompt, system_prompt, max_tokens=300)
        else:
            return await self.call_claude(prompt, system_prompt)

    async def call_claude(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> str:
        """Call Claude API with PII stripping and error handling."""
        safe_prompt = strip_pii(prompt)
        system = system_prompt or _load_prompt("system_main")

        try:
            message = await self.claude_client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": safe_prompt}],
            )

            response_text = message.content[0].text

            # Track token usage
            self.total_input_tokens += message.usage.input_tokens
            self.total_output_tokens += message.usage.output_tokens

            logger.info(
                "Claude response",
                model=settings.claude_model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                task_type="general",
            )
            return response_text

        except anthropic.RateLimitError:
            logger.warning("Claude rate limited, returning fallback")
            return "సర్వర్ busy గా ఉంది. దయచేసి 1 నిమిషం తర్వాత మళ్ళీ ప్రయత్నించండి."

        except anthropic.APIConnectionError:
            logger.error("Claude API unreachable")
            return "Internet connection సమస్య. దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి."

        except anthropic.APIError as e:
            logger.error("Claude API error", error=str(e), status=getattr(e, 'status_code', None))
            raise

    async def call_claude_structured(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 1500,
    ) -> str:
        """Call Claude for structured JSON extraction (temperature=0)."""
        safe_prompt = strip_pii(prompt)

        try:
            message = await self.claude_client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": safe_prompt}],
            )

            self.total_input_tokens += message.usage.input_tokens
            self.total_output_tokens += message.usage.output_tokens

            return message.content[0].text

        except Exception as e:
            logger.error("Claude structured call failed", error=str(e))
            raise

    async def call_claude_with_history(
        self,
        messages: list[dict],
        system_prompt: str = "",
        max_tokens: int = 1000,
    ) -> str:
        """Call Claude with conversation history for multi-turn context."""
        system = system_prompt or _load_prompt("system_main")

        # Strip PII from all messages
        safe_messages = []
        for msg in messages:
            safe_messages.append({
                "role": msg["role"],
                "content": strip_pii(msg["content"]),
            })

        try:
            message = await self.claude_client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                temperature=0.1,
                system=system,
                messages=safe_messages,
            )

            self.total_input_tokens += message.usage.input_tokens
            self.total_output_tokens += message.usage.output_tokens

            return message.content[0].text

        except Exception as e:
            logger.error("Claude multi-turn call failed", error=str(e))
            raise

    def _get_system_prompt(self, task_type: str) -> str:
        """Get the appropriate system prompt for a task type."""
        prompt_map = {
            "scheme_query": "scheme_advisor",
            "complex_query": "system_main",
            "eligibility_reasoning": "eligibility_checker",
            "form_extraction": "form_extractor",
            "grievance_resolution": "grievance_resolver",
            "task_prioritization": "task_prioritizer",
            "greeting": "system_main",
            "clarification": "system_main",
            "simple_faq": "system_main",
        }
        template_name = prompt_map.get(task_type, "system_main")
        return _load_prompt(template_name)

    def get_usage_stats(self) -> dict:
        """Get cumulative token usage for cost monitoring."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": (
                self.total_input_tokens * 0.003 / 1000
                + self.total_output_tokens * 0.015 / 1000
            ),
        }
