"""Campaign Health Agent implementation."""

from datetime import date, timedelta
from typing import Any

from src.config import settings
from src.core import AnthropicClient  # Uses Portkey routing by default
from src.core.base_agent import BaseAgent
from src.integrations.bigquery.client import get_client as get_bq_client
from src.integrations.bigquery.queries import CAMPAIGN_HEALTH_METRICS
from src.models.base import AgentType
from src.models.campaign import CampaignHealthData, CampaignMetrics
from src.models.recommendation import Recommendation


class CampaignHealthAgent(BaseAgent):
    """Agent for monitoring and diagnosing campaign health issues."""

    def __init__(self) -> None:
        """Initialize Campaign Health Agent."""
        super().__init__(AgentType.CAMPAIGN_HEALTH)
        self.llm = AnthropicClient(model="claude-sonnet-4-5")
        self.bq_client = get_bq_client()

    async def gather_data(self, context: dict[str, Any]) -> dict[str, Any]:
        """Gather campaign health metrics from BigQuery.

        Args:
            context: Context from orchestrator

        Returns:
            Dictionary with campaign health data
        """
        self.logger.info("gathering_campaign_health_data")

        # Calculate date range (last 30 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        # Format query
        query = CAMPAIGN_HEALTH_METRICS.format(
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset_raw,
            date_suffix="*",  # Use wildcard for table suffix
        )

        # Execute query
        rows = await self.bq_client.query(
            query,
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "customer_id": settings.google_ads_customer_id,
            },
        )

        # Parse into CampaignHealthData objects
        health_data = []
        for row in rows:
            metrics = CampaignMetrics(
                impressions=row["impressions"],
                clicks=row["clicks"],
                cost=row["cost"],
                conversions=row["conversions"],
                conversion_value=row["conversion_value"],
                ctr=row["ctr"],
                avg_cpc=row["avg_cpc"],
                conversion_rate=row["conversion_rate"],
                cost_per_conversion=row.get("cost_per_conversion"),
                roas=row.get("roas"),
                avg_quality_score=row.get("avg_quality_score"),
                impression_share=row.get("impression_share"),
                search_impression_share_lost_to_rank=row.get("impression_share_lost_to_rank"),
                search_impression_share_lost_to_budget=row.get(
                    "impression_share_lost_to_budget"
                ),
            )

            # Detect anomalies
            data = CampaignHealthData(
                campaign_id=row["campaign_id"],
                campaign_name=row["campaign_name"],
                ad_group_id=row.get("ad_group_id"),
                ad_group_name=row.get("ad_group_name"),
                date_start=start_date,
                date_end=end_date,
                current_metrics=metrics,
                is_paused=row.get("ad_group_status") == "PAUSED",
                has_quality_score_issues=metrics.avg_quality_score is not None
                and metrics.avg_quality_score < 5,
                has_zero_conversions=metrics.conversions == 0 and metrics.cost > 50,
                has_low_ctr=metrics.ctr < 0.01,  # Below 1%
                has_high_impression_share_loss=metrics.search_impression_share_lost_to_rank
                is not None
                and metrics.search_impression_share_lost_to_rank > 0.30,
            )

            health_data.append(data)

        self.logger.info("gathered_health_data", campaign_count=len(health_data))

        return {
            "health_data": health_data,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "flagged_count": sum(1 for d in health_data if d.health_flags),
        }

    async def analyze(self, data: dict[str, Any]) -> str:
        """Analyze campaign health using Claude.

        Args:
            data: Gathered health data

        Returns:
            Analysis from LLM
        """
        health_data: list[CampaignHealthData] = data["health_data"]

        # Filter to flagged campaigns only
        flagged = [d for d in health_data if d.health_flags]

        if not flagged:
            self.logger.info("no_health_issues_detected")
            return "All campaigns are healthy. No issues detected."

        self.logger.info("analyzing_flagged_campaigns", count=len(flagged))

        # Build prompt
        prompt = self._build_analysis_prompt(flagged)

        # Get LLM analysis (via Portkey with logging)
        analysis = await self.llm.generate(
            prompt=prompt,
            system="You are an expert SEM campaign analyst. Diagnose root causes of performance issues and recommend specific actions.",
            temperature=0.7,
            max_tokens=4096,
            run_id=str(self.run_id),
            agent_type=self.agent_type.value,
        )

        return analysis

    async def generate_recommendations(
        self,
        data: dict[str, Any],
        analysis: str,
    ) -> list[Recommendation]:
        """Generate structured recommendations from analysis.

        Args:
            data: Gathered data
            analysis: LLM analysis

        Returns:
            List of recommendations
        """
        health_data: list[CampaignHealthData] = data["health_data"]
        flagged = [d for d in health_data if d.health_flags]

        if not flagged:
            return []

        self.logger.info("generating_recommendations", flagged_count=len(flagged))

        recommendations = []

        # Parse analysis and create recommendations
        # For now, use simple heuristics
        for campaign in flagged:
            if campaign.has_zero_conversions and campaign.current_metrics.cost > 50:
                recommendations.append(
                    Recommendation(
                        agent_type=self.agent_type,
                        run_id=self.run_id,
                        title=f"Pause ad group: {campaign.ad_group_name}",
                        description=f"Spent ${campaign.current_metrics.cost:.2f} with zero conversions",
                        rationale=f"Ad group has high spend without any conversions. Analysis: {analysis[:200]}",
                        impact_estimate="Save $50+ per month",
                        risk_level="low",
                        action_type="pause_ad_group",
                        action_params={
                            "campaign_id": campaign.campaign_id,
                            "ad_group_id": campaign.ad_group_id,
                        },
                    )
                )

            if campaign.has_quality_score_issues:
                recommendations.append(
                    Recommendation(
                        agent_type=self.agent_type,
                        run_id=self.run_id,
                        title=f"Review keywords in: {campaign.ad_group_name}",
                        description=f"Average quality score: {campaign.current_metrics.avg_quality_score:.1f}",
                        rationale=f"Low quality score indicates relevance issues. Delegate to Keyword Agent.",
                        impact_estimate="Improve CPC by 20-30%",
                        risk_level="medium",
                        action_type="delegate_keyword_review",
                        action_params={
                            "campaign_id": campaign.campaign_id,
                            "ad_group_id": campaign.ad_group_id,
                        },
                    )
                )

        self.logger.info("recommendations_generated", count=len(recommendations))
        return recommendations

    async def _apply_single_recommendation(self, recommendation: Recommendation) -> None:
        """Apply a single recommendation to Google Ads.

        Args:
            recommendation: Recommendation to apply
        """
        action_type = recommendation.action_type

        if action_type == "pause_ad_group":
            await self._pause_ad_group(recommendation.action_params)
        elif action_type == "delegate_keyword_review":
            await self._delegate_keyword_review(recommendation.action_params)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    async def _pause_ad_group(self, params: dict[str, Any]) -> None:
        """Pause an ad group.

        Args:
            params: Action parameters with campaign_id and ad_group_id
        """
        from src.integrations.google_ads.client import get_client

        client = get_client()

        # Build operation
        operation = {
            "update": {
                "resource_name": f"customers/{settings.google_ads_customer_id}/adGroups/{params['ad_group_id']}",
                "status": "PAUSED",
            },
            "update_mask": {"paths": ["status"]},
        }

        # Execute
        await client.mutate([operation], "AdGroupOperation")

        self.logger.info("ad_group_paused", ad_group_id=params["ad_group_id"])

    async def _delegate_keyword_review(self, params: dict[str, Any]) -> None:
        """Delegate keyword review to Keyword Agent.

        Args:
            params: Action parameters
        """
        from src.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(run_id=self.run_id)
        await orchestrator.delegate_to_agent(AgentType.KEYWORD, params)

    def _build_analysis_prompt(self, flagged: list[CampaignHealthData]) -> str:
        """Build analysis prompt for Claude.

        Args:
            flagged: List of flagged campaigns

        Returns:
            Prompt string
        """
        prompt_parts = [
            "Analyze the following campaign health issues and diagnose root causes:\n\n"
        ]

        for i, campaign in enumerate(flagged[:20], 1):  # Limit to 20 for token efficiency
            prompt_parts.append(f"## Campaign {i}: {campaign.campaign_name}")
            prompt_parts.append(f"Ad Group: {campaign.ad_group_name}")
            prompt_parts.append(f"Flags: {', '.join(campaign.health_flags)}")
            prompt_parts.append("\nMetrics:")
            prompt_parts.append(f"- Impressions: {campaign.current_metrics.impressions:,}")
            prompt_parts.append(f"- Clicks: {campaign.current_metrics.clicks:,}")
            prompt_parts.append(f"- CTR: {campaign.current_metrics.ctr:.2%}")
            prompt_parts.append(f"- Cost: ${campaign.current_metrics.cost:.2f}")
            prompt_parts.append(f"- Conversions: {campaign.current_metrics.conversions:.1f}")
            if campaign.current_metrics.avg_quality_score:
                prompt_parts.append(
                    f"- Avg QS: {campaign.current_metrics.avg_quality_score:.1f}"
                )
            prompt_parts.append("\n")

        prompt_parts.append(
            "\nFor each flagged campaign, provide:\n"
            "1. Root cause diagnosis\n"
            "2. Recommended action (pause, keyword review, ad copy refresh, bid adjustment)\n"
            "3. Expected impact\n"
        )

        return "\n".join(prompt_parts)

    async def _create_summary(self, recommendations: list[Recommendation]) -> str:
        """Create summary for Slack message.

        Args:
            recommendations: List of recommendations

        Returns:
            Summary string
        """
        if not recommendations:
            return "All campaigns are healthy. No action needed."

        action_counts = {}
        for rec in recommendations:
            action_counts[rec.action_type] = action_counts.get(rec.action_type, 0) + 1

        summary_parts = [
            f"Found {len(recommendations)} campaign health issues:",
        ]

        for action, count in action_counts.items():
            summary_parts.append(f"- {count}x {action.replace('_', ' ')}")

        return "\n".join(summary_parts)
