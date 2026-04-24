"""Abstract base agent class defining the standard pipeline."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.config import settings
from src.models.base import AgentType, EventType
from src.models.recommendation import Recommendation, RecommendationBatch

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base agent following the standard pipeline.

    All agents implement: Gather Data → Analyze → Generate Recommendations →
    Request Approval → Apply Changes

    Each step writes to the agent_audit_log in BigQuery.
    """

    # Subclasses override to specify which actions can propagate to sync groups
    PROPAGATABLE_ACTIONS: set[str] = set()

    def __init__(self, agent_type: AgentType, run_id: UUID | None = None) -> None:
        """Initialize base agent.

        Args:
            agent_type: Type of agent
            run_id: Optional run ID (generated if not provided)
        """
        self.agent_type = agent_type
        self.run_id = run_id or uuid4()
        self.parent_run_id: UUID | None = None
        self.dry_run = settings.is_dry_run
        self.logger = logger.bind(
            component=f"{agent_type.value}_agent",
            run_id=str(self.run_id),
        )

    async def run(self, context: dict[str, Any] | None = None) -> RecommendationBatch:
        """Execute the full agent pipeline.

        Args:
            context: Optional context from orchestrator or parent agent

        Returns:
            Batch of recommendations with approval status
        """
        self.logger.info("agent_run_started", dry_run=self.dry_run)
        await self._log_event(EventType.RUN_START, {"context": context})

        try:
            # Step 1: Gather data
            data = await self.gather_data(context or {})
            await self._log_event(EventType.GATHER_DATA, {"data_summary": self._summarize_data(data)})

            # Step 2: Analyze with LLM
            analysis = await self.analyze(data)
            await self._log_event(EventType.ANALYZE, {"analysis_summary": analysis[:500]})

            # Step 3: Generate recommendations
            recommendations = await self.generate_recommendations(data, analysis)

            # Create batch
            batch = RecommendationBatch(
                run_id=self.run_id,
                agent_type=self.agent_type,
                recommendations=recommendations,
                summary=await self._create_summary(recommendations),
            )

            # Save recommendations to BigQuery
            await self._save_recommendations(recommendations)
            await self._log_event(
                EventType.RECOMMEND,
                {"recommendation_count": len(recommendations), "saved_to_bigquery": True},
            )

            # Step 4: Request approval (if not in dry run)
            if not self.dry_run:
                await self.request_approval(batch)
                await self._log_event(
                    EventType.APPROVAL_REQUESTED,
                    {"batch_id": str(batch.run_id)},
                )

                # Wait for approval (handled by Slack integration)
                # This is asynchronous - approval will trigger apply_changes separately

            await self._log_event(EventType.RUN_COMPLETE, {"status": "success"})
            self.logger.info("agent_run_completed", recommendation_count=len(recommendations))

            return batch

        except Exception as e:
            await self._log_event(EventType.RUN_FAILED, {"error": str(e)})
            self.logger.error("agent_run_failed", error=str(e))
            raise

    @abstractmethod
    async def gather_data(self, context: dict[str, Any]) -> dict[str, Any]:
        """Gather data from BigQuery and other sources.

        Args:
            context: Context from orchestrator

        Returns:
            Dictionary with gathered data
        """
        pass

    @abstractmethod
    async def analyze(self, data: dict[str, Any]) -> str:
        """Analyze data using LLM.

        Args:
            data: Gathered data

        Returns:
            Analysis text from LLM
        """
        pass

    @abstractmethod
    async def generate_recommendations(
        self, data: dict[str, Any], analysis: str
    ) -> list[Recommendation]:
        """Generate structured recommendations from analysis.

        Args:
            data: Gathered data
            analysis: LLM analysis

        Returns:
            List of recommendations
        """
        pass

    async def request_approval(self, batch: RecommendationBatch) -> None:
        """Request approval via Slack.

        This is implemented by the Slack integration and publishes to
        the approval-requests Pub/Sub topic.

        Args:
            batch: Batch of recommendations
        """
        # Import here to avoid circular dependency
        from src.integrations.slack.app import request_approval

        await request_approval(batch)

    async def apply_changes(
        self,
        recommendations: list[Recommendation],
    ) -> dict[str, Any]:
        """Apply approved recommendations to Google Ads.

        This is called after approval is received. Each agent implements
        the specific actions.

        Args:
            recommendations: List of approved recommendations

        Returns:
            Results summary
        """
        self.logger.info("applying_changes", count=len(recommendations))
        await self._log_event(
            EventType.APPLY_CHANGES,
            {"recommendation_count": len(recommendations)},
        )

        # Pre-flight guardrail validation
        from src.core.guardrails import GuardrailService

        guardrails = GuardrailService()
        is_safe, violations = await guardrails.validate_before_apply(
            recommendations=recommendations,
            agent_type=self.agent_type,
        )

        if not is_safe:
            await self._log_event(
                EventType.GUARDRAIL_BLOCKED,
                {"violations": [v.to_dict() for v in violations]},
            )
            return {
                "total": len(recommendations),
                "succeeded": 0,
                "failed": 0,
                "blocked": True,
                "violations": [v.to_dict() for v in violations],
            }

        results = {
            "total": len(recommendations),
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

        for rec in recommendations:
            try:
                await self._apply_single_recommendation(rec)
                results["succeeded"] += 1
                rec.applied_at = datetime.utcnow()
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"recommendation_id": str(rec.id), "error": str(e)})
                rec.error_message = str(e)
                self.logger.error(
                    "recommendation_failed",
                    recommendation_id=str(rec.id),
                    error=str(e),
                )

        self.logger.info(
            "changes_applied",
            succeeded=results["succeeded"],
            failed=results["failed"],
        )

        return results

    @abstractmethod
    async def _apply_single_recommendation(self, recommendation: Recommendation) -> None:
        """Apply a single recommendation.

        Subclasses implement the specific Google Ads API calls.

        Args:
            recommendation: Recommendation to apply
        """
        pass

    async def propagate_to_sync_group(
        self,
        rec: Recommendation,
        sync_group_context: Any,  # SyncGroupContext from taxonomy module
    ) -> list[Recommendation]:
        """Clone a recommendation for all campaigns in a sync group.

        Uses SyncGroupResolver to find equivalent entities by name across geos.
        E.g., pausing ad group "broad_generic_terms" in US → finds and pauses
        the same-named ad group in UK, DE, FR.

        Args:
            rec: Source recommendation to propagate
            sync_group_context: Context with all campaigns in sync group

        Returns:
            List of cloned recommendations for other campaigns
        """
        # Only propagate if action type is in PROPAGATABLE_ACTIONS
        if rec.action_type not in self.PROPAGATABLE_ACTIONS:
            self.logger.info(
                "action_not_propagatable",
                action_type=rec.action_type,
                propagatable_actions=list(self.PROPAGATABLE_ACTIONS),
            )
            return []

        from src.services.sync_group_resolver import SyncGroupResolver
        from src.integrations.bigquery.client import get_client

        resolver = SyncGroupResolver(bq_client=get_client())

        # Resolve entities across all campaigns in sync group
        resolved_params = await resolver.resolve_entities_for_sync_group(
            action_params=rec.action_params,
            source_campaign_id=rec.action_params["campaign_id"],
            sync_group_context=sync_group_context,
        )

        # Create cloned recommendations
        propagated = []
        for target_params in resolved_params:
            if target_params["campaign_id"] == rec.action_params["campaign_id"]:
                continue  # Skip source campaign

            clone = rec.model_copy(update={
                "id": uuid4(),
                "action_params": target_params,
                "metadata": {
                    **rec.metadata,
                    "propagated_from": str(rec.id),
                    "geo": target_params.get("geo"),
                },
            })
            propagated.append(clone)

        self.logger.info(
            "recommendation_propagated",
            source_rec_id=str(rec.id),
            sync_group=sync_group_context.sync_group,
            propagated_count=len(propagated),
        )

        return propagated

    async def _save_recommendations(self, recommendations: list[Recommendation]) -> None:
        """Save recommendations to BigQuery.

        Args:
            recommendations: List of recommendations to save
        """
        if not recommendations:
            self.logger.info("no_recommendations_to_save")
            return

        # Import here to avoid circular dependency
        from src.integrations.bigquery.client import get_client
        import json

        bq_client = get_client()

        # Convert recommendations to BigQuery rows
        rows = []
        for rec in recommendations:
            row = {
                "id": str(rec.id),
                "agent_type": rec.agent_type.value,
                "run_id": str(rec.run_id),
                "created_at": rec.created_at.isoformat(),
                "title": rec.title,
                "description": rec.description,
                "rationale": rec.rationale,
                "impact_estimate": rec.impact_estimate,
                "risk_level": rec.risk_level,
                "action_type": rec.action_type,
                "action_params": json.dumps(rec.action_params),
                "status": rec.status.value,
                "approval_status": rec.approval_status.value if rec.approval_status else None,
                "approved_by": rec.approved_by,
                "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
                "applied_at": rec.applied_at.isoformat() if rec.applied_at else None,
                "applied_result": json.dumps(rec.applied_result) if rec.applied_result else None,
                "error_message": rec.error_message,
                "metadata": json.dumps(rec.metadata),
            }
            rows.append(row)

        try:
            await bq_client.insert_rows("agent_recommendations", rows)
            self.logger.info("recommendations_saved", count=len(rows))
        except Exception as e:
            self.logger.error("save_recommendations_failed", error=str(e))
            # Don't raise - we don't want to fail the agent run if saving fails
            # The recommendations are still returned and can be viewed in logs

    async def _log_event(
        self,
        event_type: EventType,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log event to BigQuery audit log.

        Args:
            event_type: Type of event
            details: Additional event details
        """
        # Import here to avoid circular dependency
        from src.integrations.bigquery.client import log_audit_event

        await log_audit_event(
            run_id=self.run_id,
            agent_type=self.agent_type,
            event_type=event_type,
            details=details or {},
        )

    async def _load_knowledge_context(
        self,
        campaign_type: str | None = None,
        conversion_goal: str | None = None,
    ) -> str:
        """Load knowledge context for this agent.

        Args:
            campaign_type: Optional campaign type (e.g., "brand", "non_brand")
            conversion_goal: Optional conversion goal (e.g., "sqc_org_creates")

        Returns:
            Formatted knowledge context string
        """
        from src.services.knowledge import KnowledgeService

        svc = KnowledgeService()
        return svc.get_context(
            agent_type=self.agent_type.value,
            campaign_type=campaign_type,
            conversion_goal=conversion_goal,
        )

    def _summarize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a summary of gathered data for logging.

        Args:
            data: Full data dictionary

        Returns:
            Summarized data
        """
        summary = {}
        for key, value in data.items():
            if isinstance(value, list):
                summary[key] = f"list[{len(value)}]"
            elif isinstance(value, dict):
                summary[key] = f"dict[{len(value)} keys]"
            else:
                summary[key] = type(value).__name__
        return summary

    @abstractmethod
    async def _create_summary(self, recommendations: list[Recommendation]) -> str:
        """Create human-readable summary for Slack message.

        Args:
            recommendations: List of recommendations

        Returns:
            Summary text
        """
        pass
