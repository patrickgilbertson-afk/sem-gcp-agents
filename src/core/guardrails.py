"""Guardrail service for enforcing safety limits before applying recommendations."""

from typing import Any

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient
from src.models.base import AgentType

logger = structlog.get_logger(__name__)


class GuardrailViolation:
    """Represents a guardrail violation."""

    def __init__(self, rule: str, message: str, context: dict[str, Any] | None = None):
        """Initialize violation.

        Args:
            rule: Name of the violated rule
            message: Human-readable description
            context: Additional context about the violation
        """
        self.rule = rule
        self.message = message
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule": self.rule,
            "message": self.message,
            "context": self.context,
        }


class GuardrailService:
    """Service for validating recommendations against safety limits."""

    def __init__(self, bq_client: BigQueryClient | None = None):
        """Initialize guardrail service.

        Args:
            bq_client: BigQuery client for loading config overrides
        """
        self.bq_client = bq_client or BigQueryClient()
        self.logger = logger.bind(component="guardrail_service")
        self._config_cache: dict[str, dict[str, Any]] = {}

    async def validate_before_apply(
        self,
        recommendations: list[Any],
        agent_type: AgentType,
        daily_spend: float | None = None,
    ) -> tuple[bool, list[GuardrailViolation]]:
        """Validate recommendations against safety guardrails.

        Args:
            recommendations: List of recommendations to validate
            agent_type: Type of agent making the recommendations
            daily_spend: Current daily spend (for spend impact validation)

        Returns:
            Tuple of (is_safe, violations). is_safe is True if all checks pass.
        """
        violations: list[GuardrailViolation] = []
        agent_type_str = agent_type.value if isinstance(agent_type, AgentType) else agent_type

        self.logger.info(
            "validating_recommendations",
            agent_type=agent_type_str,
            recommendation_count=len(recommendations),
        )

        # Load agent-specific config overrides
        config = await self._load_config(agent_type_str)

        # 1. Check kill switch
        if settings.kill_switch_enabled:
            violations.append(
                GuardrailViolation(
                    rule="kill_switch",
                    message="Kill switch is enabled. All apply operations are blocked.",
                    context={"kill_switch_enabled": True},
                )
            )

        # 2. Check dry run mode
        if settings.is_dry_run:
            violations.append(
                GuardrailViolation(
                    rule="dry_run_mode",
                    message="Dry run mode is enabled. Cannot apply changes.",
                    context={"dry_run": settings.dry_run},
                )
            )

        # 3. Check operation count
        max_operations = config.get("max_operations_per_run", settings.max_operations_per_run)
        if len(recommendations) > max_operations:
            violations.append(
                GuardrailViolation(
                    rule="max_operations",
                    message=f"Recommendation count ({len(recommendations)}) exceeds maximum allowed ({max_operations})",
                    context={
                        "recommendation_count": len(recommendations),
                        "max_allowed": max_operations,
                    },
                )
            )

        # 4. Check daily spend impact (if daily_spend provided)
        if daily_spend is not None and daily_spend > 0:
            total_spend_impact = sum(
                rec.action_params.get("spend_impact_estimate", 0)
                for rec in recommendations
            )
            max_spend_increase_pct = config.get(
                "max_daily_spend_increase_pct", settings.max_daily_spend_increase_pct
            )
            spend_impact_pct = (total_spend_impact / daily_spend) * 100

            if abs(spend_impact_pct) > max_spend_increase_pct:
                violations.append(
                    GuardrailViolation(
                        rule="max_daily_spend_increase",
                        message=f"Total spend impact ({spend_impact_pct:.1f}%) exceeds maximum allowed ({max_spend_increase_pct}%)",
                        context={
                            "spend_impact_pct": spend_impact_pct,
                            "max_allowed_pct": max_spend_increase_pct,
                            "total_spend_impact": total_spend_impact,
                            "daily_spend": daily_spend,
                        },
                    )
                )

        is_safe = len(violations) == 0

        if not is_safe:
            self.logger.warning(
                "guardrail_violations_detected",
                violation_count=len(violations),
                violations=[v.to_dict() for v in violations],
            )
        else:
            self.logger.info("guardrail_validation_passed")

        return is_safe, violations

    async def _load_config(self, agent_type: str) -> dict[str, Any]:
        """Load agent-specific config overrides from BigQuery.

        Falls back to settings.* values when no override exists.

        Args:
            agent_type: Type of agent (e.g., "campaign_health")

        Returns:
            Dictionary of config key-value pairs
        """
        # Check cache first
        if agent_type in self._config_cache:
            return self._config_cache[agent_type]

        config: dict[str, Any] = {}

        try:
            # Query agent_config table for this agent type
            sql = f"""
                SELECT config_key, config_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.agent_config`
                WHERE agent_type = @agent_type
            """

            rows = await self.bq_client.query(sql, {"agent_type": agent_type})

            for row in rows:
                key = row["config_key"]
                value = row["config_value"]

                # Parse value based on key type
                if "pct" in key or "percent" in key:
                    config[key] = float(value)
                elif "max_" in key or "limit" in key:
                    config[key] = int(value)
                elif value.lower() in ("true", "false"):
                    config[key] = value.lower() == "true"
                else:
                    config[key] = value

            self.logger.info(
                "loaded_agent_config",
                agent_type=agent_type,
                override_count=len(config),
            )

        except Exception as e:
            self.logger.warning(
                "failed_to_load_agent_config",
                agent_type=agent_type,
                error=str(e),
                fallback="using_settings_defaults",
            )

        # Cache the config
        self._config_cache[agent_type] = config
        return config
