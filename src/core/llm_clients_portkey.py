"""LLM client wrappers using Portkey gateway for Claude and Gemini."""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog
from portkey_ai import Portkey
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

logger = structlog.get_logger(__name__)


class PortkeyLLMClient:
    """Base client for LLM calls routed through Portkey."""

    def __init__(self, provider: str, virtual_key: str) -> None:
        """Initialize Portkey client.

        Args:
            provider: Provider name ('anthropic' or 'google')
            virtual_key: Portkey virtual key for this provider
        """
        self.provider = provider
        self.client = Portkey(
            api_key=settings.portkey_api_key,
            virtual_key=virtual_key,
        )
        self.logger = logger.bind(component=f"{provider}_portkey_client")

    async def _log_llm_call(
        self,
        call_id: str,
        run_id: str,
        agent_type: str,
        model: str,
        prompt: str,
        system_prompt: str | None,
        response_tokens: int,
        prompt_tokens: int,
        total_tokens: int,
        response_time_ms: int,
        cost_usd: float,
        portkey_request_id: str | None,
        cache_hit: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log LLM call to BigQuery.

        Args:
            call_id: Unique call identifier
            run_id: Agent run ID
            agent_type: Type of agent making the call
            model: Model name
            prompt: User prompt
            system_prompt: System prompt
            response_tokens: Completion tokens
            prompt_tokens: Prompt tokens
            total_tokens: Total tokens
            response_time_ms: Response time in milliseconds
            cost_usd: Cost in USD
            portkey_request_id: Portkey request ID
            cache_hit: Whether response was cached
            error_code: Error code if failed
            error_message: Error message if failed
        """
        try:
            from src.integrations.bigquery.client import get_client

            client = get_client()

            # Hash prompts for deduplication analysis
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            system_hash = (
                hashlib.sha256(system_prompt.encode()).hexdigest() if system_prompt else None
            )

            row = {
                "call_id": call_id,
                "run_id": run_id,
                "agent_type": agent_type,
                "provider": self.provider,
                "model": model,
                "timestamp": datetime.utcnow().isoformat(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": response_tokens,
                "total_tokens": total_tokens,
                "response_time_ms": response_time_ms,
                "cost_usd": cost_usd,
                "error_code": error_code,
                "error_message": error_message,
                "portkey_request_id": portkey_request_id,
                "cache_hit": cache_hit,
            }

            await client.insert_rows("llm_calls", [row])

            self.logger.info(
                "llm_call_logged",
                call_id=call_id,
                tokens=total_tokens,
                cost=cost_usd,
                cache_hit=cache_hit,
            )

        except Exception as e:
            self.logger.error("failed_to_log_llm_call", error=str(e))
            # Don't raise - logging failure shouldn't break the agent


class AnthropicClient(PortkeyLLMClient):
    """Claude client via Portkey."""

    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        """Initialize Anthropic client.

        Args:
            model: Claude model to use
        """
        super().__init__(
            provider="anthropic",
            virtual_key=settings.portkey_virtual_key_anthropic,
        )
        self.model = model
        self.logger = logger.bind(component="anthropic_portkey_client", model=model)

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
        run_id: str | None = None,
        agent_type: str | None = None,
    ) -> str:
        """Generate a response from Claude via Portkey.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions
            run_id: Agent run ID for logging
            agent_type: Agent type for logging

        Returns:
            Generated text response
        """
        call_id = str(uuid4())
        start_time = datetime.utcnow()

        self.logger.info(
            "generating_response",
            call_id=call_id,
            prompt_length=len(prompt),
            model=self.model,
        )

        try:
            # Build request
            messages = [{"role": "user", "content": prompt}]

            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system:
                kwargs["system"] = system

            if tools:
                kwargs["tools"] = tools

            # Enable caching if configured
            if settings.portkey_enable_cache:
                kwargs["cache"] = {
                    "mode": "semantic",
                    "max_age": settings.portkey_cache_ttl,
                }

            # Call via Portkey
            response = self.client.chat.completions.create(**kwargs)

            # Extract response
            result = response.choices[0].message.content
            if not isinstance(result, str):
                result = str(result)

            # Calculate metrics
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
            completion_tokens = getattr(response.usage, "completion_tokens", 0)
            total_tokens = getattr(response.usage, "total_tokens", 0)

            # Estimate cost (approximate - Portkey provides more accurate)
            cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)

            # Check if cached
            cache_hit = getattr(response, "_cache_hit", False)

            # Get Portkey request ID
            portkey_request_id = getattr(response, "_request_id", None)

            self.logger.info(
                "response_generated",
                call_id=call_id,
                output_length=len(result),
                tokens=total_tokens,
                cost=cost_usd,
                cache_hit=cache_hit,
                response_time_ms=response_time_ms,
            )

            # Log to BigQuery
            if run_id and agent_type:
                await self._log_llm_call(
                    call_id=call_id,
                    run_id=run_id,
                    agent_type=agent_type,
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system,
                    response_tokens=completion_tokens,
                    prompt_tokens=prompt_tokens,
                    total_tokens=total_tokens,
                    response_time_ms=response_time_ms,
                    cost_usd=cost_usd,
                    portkey_request_id=portkey_request_id,
                    cache_hit=cache_hit,
                )

            return result

        except Exception as e:
            self.logger.error("generation_failed", call_id=call_id, error=str(e))

            # Log error to BigQuery
            if run_id and agent_type:
                end_time = datetime.utcnow()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                await self._log_llm_call(
                    call_id=call_id,
                    run_id=run_id,
                    agent_type=agent_type,
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system,
                    response_tokens=0,
                    prompt_tokens=0,
                    total_tokens=0,
                    response_time_ms=response_time_ms,
                    cost_usd=0.0,
                    portkey_request_id=None,
                    cache_hit=False,
                    error_code=type(e).__name__,
                    error_message=str(e),
                )

            raise

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on token usage.

        Args:
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Estimated cost in USD
        """
        # Approximate pricing for Claude Sonnet 4.5 (update as needed)
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015

        input_cost = (prompt_tokens / 1000) * input_cost_per_1k
        output_cost = (completion_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost


class GeminiClient(PortkeyLLMClient):
    """Gemini client via Portkey."""

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        """Initialize Gemini client.

        Args:
            model: Gemini model to use
        """
        super().__init__(
            provider="google",
            virtual_key=settings.portkey_virtual_key_google,
        )
        self.model = model
        self.logger = logger.bind(component="gemini_portkey_client", model=model)

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
        run_id: str | None = None,
        agent_type: str | None = None,
    ) -> str:
        """Generate a response from Gemini via Portkey.

        Args:
            prompt: User prompt
            system: System instruction (optional)
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            run_id: Agent run ID for logging
            agent_type: Agent type for logging

        Returns:
            Generated text response
        """
        call_id = str(uuid4())
        start_time = datetime.utcnow()

        self.logger.info(
            "generating_response",
            call_id=call_id,
            prompt_length=len(prompt),
            model=self.model,
        )

        try:
            # Build messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Call via Portkey (OpenAI-compatible format)
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Enable caching
            if settings.portkey_enable_cache:
                kwargs["cache"] = {
                    "mode": "semantic",
                    "max_age": settings.portkey_cache_ttl,
                }

            response = self.client.chat.completions.create(**kwargs)

            # Extract response
            result = response.choices[0].message.content
            if not isinstance(result, str):
                result = str(result)

            # Calculate metrics
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
            completion_tokens = getattr(response.usage, "completion_tokens", 0)
            total_tokens = getattr(response.usage, "total_tokens", 0)

            cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)
            cache_hit = getattr(response, "_cache_hit", False)
            portkey_request_id = getattr(response, "_request_id", None)

            self.logger.info(
                "response_generated",
                call_id=call_id,
                output_length=len(result),
                tokens=total_tokens,
                cost=cost_usd,
                cache_hit=cache_hit,
                response_time_ms=response_time_ms,
            )

            # Log to BigQuery
            if run_id and agent_type:
                await self._log_llm_call(
                    call_id=call_id,
                    run_id=run_id,
                    agent_type=agent_type,
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system,
                    response_tokens=completion_tokens,
                    prompt_tokens=prompt_tokens,
                    total_tokens=total_tokens,
                    response_time_ms=response_time_ms,
                    cost_usd=cost_usd,
                    portkey_request_id=portkey_request_id,
                    cache_hit=cache_hit,
                )

            return result

        except Exception as e:
            self.logger.error("generation_failed", call_id=call_id, error=str(e))

            # Log error
            if run_id and agent_type:
                end_time = datetime.utcnow()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                await self._log_llm_call(
                    call_id=call_id,
                    run_id=run_id,
                    agent_type=agent_type,
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system,
                    response_tokens=0,
                    prompt_tokens=0,
                    total_tokens=0,
                    response_time_ms=response_time_ms,
                    cost_usd=0.0,
                    portkey_request_id=None,
                    cache_hit=False,
                    error_code=type(e).__name__,
                    error_message=str(e),
                )

            raise

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 8192,
        run_id: str | None = None,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: User prompt requesting JSON output
            system: System instruction
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            run_id: Agent run ID
            agent_type: Agent type

        Returns:
            Parsed JSON response
        """
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no additional text."

        response_text = await self.generate(
            prompt=json_prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            run_id=run_id,
            agent_type=agent_type,
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
                return json.loads(response_text)
            raise

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on token usage.

        Args:
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Estimated cost in USD
        """
        # Approximate pricing for Gemini 2.0 Flash
        input_cost_per_1k = 0.000075
        output_cost_per_1k = 0.0003

        input_cost = (prompt_tokens / 1000) * input_cost_per_1k
        output_cost = (completion_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost
