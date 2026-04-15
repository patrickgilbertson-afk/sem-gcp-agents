"""Orchestrator for routing work to specialist agents."""

from typing import Any
from uuid import UUID, uuid4

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient
from src.models.base import AgentType, EventType
from src.models.recommendation import RecommendationBatch
from src.services.taxonomy import TaxonomyService

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Routes work to specialist agents and handles delegation."""

    def __init__(
        self,
        run_id: UUID | None = None,
        taxonomy_service: TaxonomyService | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            run_id: Optional run ID (generated if not provided)
            taxonomy_service: Optional taxonomy service (creates one if not provided)
        """
        self.run_id = run_id or uuid4()
        self.taxonomy_service = taxonomy_service or TaxonomyService()
        self.bq_client = BigQueryClient()
        self.logger = logger.bind(component="orchestrator", run_id=str(self.run_id))

    async def run(self, context: dict[str, Any] | None = None) -> RecommendationBatch:
        """Run orchestrator to decide which agents to execute.

        This is typically called by Cloud Scheduler for scheduled runs.

        Args:
            context: Optional context

        Returns:
            Combined recommendation batch
        """
        self.logger.info("orchestrator_started")

        # TODO: Implement smart routing logic based on:
        # - Time of day
        # - Recent agent runs
        # - Campaign health signals
        # - Manual triggers

        # For now, default to Campaign Health Agent on scheduled runs
        return await self.run_agent(AgentType.CAMPAIGN_HEALTH, context)

    async def run_agent(
        self,
        agent_type: AgentType,
        context: dict[str, Any] | None = None,
        parent_run_id: UUID | None = None,
        campaign_id: str | None = None,
        sync_group: str | None = None,
    ) -> RecommendationBatch | None:
        """Run a specific agent, checking exclusions first.

        Args:
            agent_type: Type of agent to run
            context: Optional context
            parent_run_id: Optional parent run ID for delegation tracking
            campaign_id: Optional campaign ID to check exclusions
            sync_group: Optional sync group to check exclusions

        Returns:
            Recommendation batch from agent, or None if excluded
        """
        # Check exclusions before running agent
        is_excluded = False
        exclusion_reason = None

        if sync_group:
            is_excluded = await self.taxonomy_service.is_agent_excluded_for_sync_group(
                sync_group, agent_type
            )
            if is_excluded:
                sg_context = await self.taxonomy_service.get_sync_group_context(sync_group)
                exclusion_reason = (
                    f"Agent excluded for sync group {sync_group}. "
                    f"External manager: {sg_context.external_manager if sg_context else 'unknown'}"
                )
        elif campaign_id:
            is_excluded = await self.taxonomy_service.is_agent_excluded(campaign_id, agent_type)
            if is_excluded:
                taxonomy = await self.taxonomy_service.get_by_campaign_id(campaign_id)
                exclusion_reason = (
                    f"Agent excluded for campaign {campaign_id}. "
                    f"External manager: {taxonomy.external_manager if taxonomy else 'unknown'}"
                )

        if is_excluded:
            self.logger.info(
                "agent_excluded",
                agent_type=agent_type.value,
                campaign_id=campaign_id,
                sync_group=sync_group,
                reason=exclusion_reason,
            )
            # Log exclusion to audit log
            await self._log_exclusion(agent_type, campaign_id, sync_group, exclusion_reason)
            return None

        self.logger.info("running_agent", agent_type=agent_type.value)

        # Import agents here to avoid circular dependencies
        from src.agents.campaign_health.agent import CampaignHealthAgent

        # Map agent types to implementations
        agent_map = {
            AgentType.CAMPAIGN_HEALTH: CampaignHealthAgent,
            # TODO: Add other agents
            # AgentType.KEYWORD: KeywordAgent,
            # AgentType.AD_COPY: AdCopyAgent,
            # AgentType.BID_MODIFIER: BidModifierAgent,
        }

        agent_class = agent_map.get(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Create and run agent
        agent = agent_class()
        if parent_run_id:
            agent.parent_run_id = parent_run_id

        batch = await agent.run(context)

        self.logger.info(
            "agent_completed",
            agent_type=agent_type.value,
            recommendation_count=batch.total_count,
        )

        return batch

    async def delegate_to_agent(
        self,
        agent_type: AgentType,
        context: dict[str, Any],
    ) -> None:
        """Delegate work to a specialist agent via Pub/Sub.

        Used when Campaign Health Agent identifies issues that need
        specialist handling (keywords, ad copy, bid modifiers).

        Args:
            agent_type: Agent to delegate to
            context: Context for the agent
        """
        self.logger.info("delegating_to_agent", agent_type=agent_type.value)

        from src.integrations.pubsub.client import publish_message

        message = {
            "agent_type": agent_type.value,
            "parent_run_id": str(self.run_id),
            "context": context,
        }

        await publish_message("agent-tasks", message)

        self.logger.info("delegation_published", agent_type=agent_type.value)

    async def _log_exclusion(
        self,
        agent_type: AgentType,
        campaign_id: str | None,
        sync_group: str | None,
        reason: str | None,
    ) -> None:
        """Log agent exclusion to audit log.

        Args:
            agent_type: Type of agent that was excluded
            campaign_id: Campaign ID if applicable
            sync_group: Sync group if applicable
            reason: Exclusion reason
        """
        from datetime import datetime, timezone

        audit_row = {
            "run_id": str(self.run_id),
            "agent_type": agent_type.value,
            "event_type": EventType.ERROR.value,  # Or create new EXCLUDED event type
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "event": "agent_excluded",
                "campaign_id": campaign_id,
                "sync_group": sync_group,
                "reason": reason,
            },
        }

        await self.bq_client.insert_rows("agent_audit_log", [audit_row])
