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
            await self._log_event(
                EventType.RECOMMEND,
                {"recommendation_count": len(recommendations)},
            )

            # Create batch
            batch = RecommendationBatch(
                run_id=self.run_id,
                agent_type=self.agent_type,
                recommendations=recommendations,
                summary=await self._create_summary(recommendations),
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
