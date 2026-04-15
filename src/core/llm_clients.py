"""LLM client wrappers for Claude (Anthropic) and Gemini (Google AI)."""

import json
from typing import Any

import anthropic
import structlog
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

logger = structlog.get_logger(__name__)


class AnthropicClient:
    """Wrapper for Anthropic Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        """Initialize Anthropic client.

        Args:
            model: Claude model to use (default: claude-sonnet-4-5)
        """
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model
        self.logger = logger.bind(component="anthropic_client", model=model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate a response from Claude.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling

        Returns:
            Generated text response
        """
        self.logger.info("generating_response", prompt_length=len(prompt))

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system:
                kwargs["system"] = system

            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            # Extract text content
            content = response.content[0]
            if content.type == "text":
                result = content.text
            else:
                result = json.dumps({"type": content.type, "content": str(content)})

            self.logger.info(
                "response_generated",
                output_length=len(result),
                stop_reason=response.stop_reason,
            )
            return result

        except Exception as e:
            self.logger.error("generation_failed", error=str(e))
            raise


class GeminiClient:
    """Wrapper for Google Gemini API."""

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        """Initialize Gemini client.

        Args:
            model: Gemini model to use
        """
        self.client = genai.Client(api_key=settings.google_ai_api_key)
        self.model = model
        self.logger = logger.bind(component="gemini_client", model=model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 8192,
    ) -> str:
        """Generate a response from Gemini.

        Args:
            prompt: User prompt
            system: System instruction (optional)
            temperature: Sampling temperature
            max_tokens: Maximum output tokens

        Returns:
            Generated text response
        """
        self.logger.info("generating_response", prompt_length=len(prompt))

        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system if system else None,
            )

            response = self.client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )

            result = response.text

            self.logger.info("response_generated", output_length=len(result))
            return result

        except Exception as e:
            self.logger.error("generation_failed", error=str(e))
            raise

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: User prompt requesting JSON output
            system: System instruction
            temperature: Sampling temperature
            max_tokens: Maximum output tokens

        Returns:
            Parsed JSON response
        """
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no additional text."

        response_text = await self.generate(
            prompt=json_prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
                return json.loads(response_text)
            raise
