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

    # Actions that can propagate to all campaigns in a SYNCED sync group
    PROPAGATABLE_ACTIONS = {"pause_ad_group", "delegate_keyword_review"}

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

        # Format query with customer ID as suffix (views don't support wildcards)
        query = CAMPAIGN_HEALTH_METRICS.format(
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset_raw,
            date_suffix=settings.google_ads_customer_id,
        )

        # Execute query
        rows = await self.bq_client.query(
            query,
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "customer_id": int(settings.google_ads_customer_id),
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

        # Load taxonomy data for campaigns (auto-populate if missing)
        from src.services.taxonomy import TaxonomyService
        from src.utils.taxonomy import parse_campaign_name

        taxonomy_service = TaxonomyService(bq_client=self.bq_client)
        taxonomy_map = {}
        sync_group_map = {}

        # Build campaign name lookup for auto-population
        campaign_name_map = {}
        for d in health_data:
            campaign_name_map[d.campaign_id] = d.campaign_name

        # Get unique campaign IDs
        campaign_ids = list(set(d.campaign_id for d in health_data))
        campaigns_seeded = 0

        for campaign_id in campaign_ids:
            taxonomy = await taxonomy_service.get_by_campaign_id(campaign_id)

            # Auto-populate taxonomy if missing
            if not taxonomy and campaign_id in campaign_name_map:
                campaign_name = campaign_name_map[campaign_id]
                self.logger.info(
                    "auto_populating_taxonomy",
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                )
                try:
                    taxonomy = parse_campaign_name(
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        customer_id=settings.google_ads_customer_id,
                        campaign_status="ENABLED",
                    )
                    await taxonomy_service.upsert_taxonomy(taxonomy)
                    campaigns_seeded += 1
                except Exception as e:
                    self.logger.warning(
                        "taxonomy_auto_populate_failed",
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        error=str(e),
                    )
                    taxonomy = None

            if taxonomy:
                taxonomy_map[campaign_id] = taxonomy

                # For SYNCED campaigns, load sync group context
                if taxonomy.management_strategy.value == "synced" and taxonomy.sync_group:
                    if taxonomy.sync_group not in sync_group_map:
                        sync_group_context = await taxonomy_service.get_sync_group_context(
                            taxonomy.sync_group
                        )
                        if sync_group_context:
                            sync_group_map[taxonomy.sync_group] = sync_group_context

        self.logger.info(
            "taxonomy_loaded",
            campaigns_with_taxonomy=len(taxonomy_map),
            campaigns_seeded=campaigns_seeded,
            sync_groups=len(sync_group_map),
        )

        # Load GA4 metrics if configured
        ga4_metrics = {}
        if settings.ga4_dataset:
            from src.integrations.bigquery.analytics_queries import get_ga4_campaign_metrics

            ga4_data = await get_ga4_campaign_metrics(
                bq_client=self.bq_client,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )

            # Index by campaign name for easy lookup
            for row in ga4_data:
                campaign_name = row["campaign_name"]
                ga4_metrics[campaign_name] = {
                    "users": row.get("users", 0),
                    "sessions": row.get("sessions", 0),
                    "page_views": row.get("page_views", 0),
                    "conversions_ga4": row.get("conversions", 0),
                    "engaged_visitors": row.get("engaged_visitors", 0),
                    "engagement_rate": row.get("engagement_rate", 0),
                    "engaged_visitor_rate": row.get("engaged_visitor_rate", 0),
                    "conversion_rate_ga4": row.get("conversion_rate_ga4", 0),
                    "avg_engagement_time_sec": row.get("avg_engagement_time_sec", 0),
                }

            self.logger.info(
                "ga4_metrics_loaded",
                campaigns_with_ga4_data=len(ga4_metrics),
            )

        return {
            "health_data": health_data,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "flagged_count": sum(1 for d in health_data if d.health_flags),
            "taxonomy_map": taxonomy_map,
            "sync_group_map": sync_group_map,
            "ga4_metrics": ga4_metrics,
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

        # Build prompt with taxonomy context and GA4 data
        taxonomy_map = data.get("taxonomy_map", {})
        sync_group_map = data.get("sync_group_map", {})
        ga4_metrics = data.get("ga4_metrics", {})
        prompt = self._build_analysis_prompt(flagged, taxonomy_map, sync_group_map, ga4_metrics)

        # Load knowledge context (determine dominant campaign type and conversion goal)
        dominant_campaign_type = self._get_dominant_campaign_type(flagged)
        dominant_conversion_goal = self._get_dominant_conversion_goal(flagged, taxonomy_map)
        knowledge = await self._load_knowledge_context(
            campaign_type=dominant_campaign_type,
            conversion_goal=dominant_conversion_goal,
        )

        # Build enhanced system prompt with knowledge context
        system_prompt = (
            "You are an expert SEM campaign analyst. Diagnose root causes of "
            "performance issues and recommend specific actions.\n\n"
            "## Account Knowledge\n\n"
            f"{knowledge}"
        )

        # Get LLM analysis (via Portkey with logging)
        analysis = await self.llm.generate(
            prompt=prompt,
            system=system_prompt,
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
        taxonomy_map = data.get("taxonomy_map", {})

        # Parse analysis and create recommendations
        # For now, use simple heuristics
        for campaign in flagged:
            # Get taxonomy metadata for this campaign
            taxonomy = taxonomy_map.get(campaign.campaign_id)
            metadata = {}
            if taxonomy:
                metadata = {
                    "sync_group": taxonomy.sync_group,
                    "management_strategy": taxonomy.management_strategy.value,
                    "campaign_type": taxonomy.campaign_type.value,
                    "geo": taxonomy.geo,
                    "is_template": taxonomy.is_template,
                }

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
                        metadata=metadata,
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
                        metadata=metadata,
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

    def _build_analysis_prompt(
        self,
        flagged: list[CampaignHealthData],
        taxonomy_map: dict[str, Any],
        sync_group_map: dict[str, Any],
        ga4_metrics: dict[str, Any],
    ) -> str:
        """Build analysis prompt for Claude with sync group context and GA4 data.

        Args:
            flagged: List of flagged campaigns
            taxonomy_map: Campaign ID -> taxonomy mapping
            sync_group_map: Sync group -> context mapping
            ga4_metrics: Campaign name -> GA4 metrics mapping

        Returns:
            Prompt string
        """
        prompt_parts = [
            "Analyze the following campaign health issues and diagnose root causes.\n\n"
        ]

        # Group campaigns by sync group
        synced_groups: dict[str, list[CampaignHealthData]] = {}
        individual_campaigns: list[CampaignHealthData] = []

        for campaign in flagged[:20]:  # Limit to 20 for token efficiency
            taxonomy = taxonomy_map.get(campaign.campaign_id)
            if taxonomy and taxonomy.management_strategy.value == "synced" and taxonomy.sync_group:
                if taxonomy.sync_group not in synced_groups:
                    synced_groups[taxonomy.sync_group] = []
                synced_groups[taxonomy.sync_group].append(campaign)
            else:
                individual_campaigns.append(campaign)

        # Add synced groups first
        for sync_group_name, campaigns in synced_groups.items():
            sync_context = sync_group_map.get(sync_group_name)
            if sync_context:
                geos = [c.geo for c in sync_context.campaigns]
                prompt_parts.append(
                    f"## Sync Group: {sync_group_name} (SYNCED, {len(geos)} geos: {', '.join(geos)})"
                )
                prompt_parts.append(
                    f"Template: {sync_context.template_campaign.campaign_name}"
                )
                prompt_parts.append(
                    "Strategy: Changes propagate to all geos.\n"
                )

            for campaign in campaigns:
                taxonomy = taxonomy_map.get(campaign.campaign_id)
                geo_suffix = f" ({taxonomy.geo})" if taxonomy else ""
                prompt_parts.append(f"### {campaign.campaign_name}{geo_suffix}")

                # Add conversion goal context if available
                if taxonomy and taxonomy.conversion_goal:
                    source_label = f" ({taxonomy.conversion_source})" if taxonomy.conversion_source else ""
                    prompt_parts.append(f"Primary Conversion: {taxonomy.conversion_goal}{source_label}")
                    prompt_parts.append(f"Optimize for: Cost per {taxonomy.conversion_goal}, Conversion Rate")

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

                # Add GA4 metrics if available
                if campaign.campaign_name in ga4_metrics:
                    ga4 = ga4_metrics[campaign.campaign_name]
                    prompt_parts.append("\nGA4 Web Metrics:")
                    prompt_parts.append(f"- Users: {ga4['users']:,}")
                    prompt_parts.append(f"- Sessions: {ga4['sessions']:,}")
                    prompt_parts.append(f"- Page Views: {ga4['page_views']:,}")
                    prompt_parts.append(f"- Engagement Rate: {ga4['engagement_rate']:.1%}")
                    prompt_parts.append(f"- Engaged Visitors: {ga4['engaged_visitors']:,} ({ga4['engaged_visitor_rate']:.1%} of users)")
                    prompt_parts.append(f"- GA4 Conversions: {ga4['conversions_ga4']:.1f}")
                    prompt_parts.append(f"- GA4 Conv Rate: {ga4['conversion_rate_ga4']:.1%}")

                prompt_parts.append("\n")

        # Add individual campaigns
        for campaign in individual_campaigns:
            taxonomy = taxonomy_map.get(campaign.campaign_id)
            prompt_parts.append(f"## Individual: {campaign.campaign_name}")

            # Add conversion goal context if available
            if taxonomy and taxonomy.conversion_goal:
                source_label = f" ({taxonomy.conversion_source})" if taxonomy.conversion_source else ""
                prompt_parts.append(f"Primary Conversion: {taxonomy.conversion_goal}{source_label}")
                prompt_parts.append(f"Optimize for: Cost per {taxonomy.conversion_goal}, Conversion Rate")

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

            # Add GA4 metrics if available
            if campaign.campaign_name in ga4_metrics:
                ga4 = ga4_metrics[campaign.campaign_name]
                prompt_parts.append("\nGA4 Web Metrics:")
                prompt_parts.append(f"- Users: {ga4['users']:,}")
                prompt_parts.append(f"- Sessions: {ga4['sessions']:,}")
                prompt_parts.append(f"- Page Views: {ga4['page_views']:,}")
                prompt_parts.append(f"- Engagement Rate: {ga4['engagement_rate']:.1%}")
                prompt_parts.append(f"- Engaged Visitors: {ga4['engaged_visitors']:,} ({ga4['engaged_visitor_rate']:.1%} of users)")
                prompt_parts.append(f"- GA4 Conversions: {ga4['conversions_ga4']:.1f}")
                prompt_parts.append(f"- GA4 Conv Rate: {ga4['conversion_rate_ga4']:.1%}")

            prompt_parts.append("\n")

        prompt_parts.append(
            "\nFor each flagged campaign, provide:\n"
            "1. Root cause diagnosis\n"
            "2. Recommended action (pause, keyword review, ad copy refresh, bid adjustment)\n"
            "3. Expected impact\n"
            "4. For SYNCED campaigns, note if the action should apply to all geos in the sync group\n"
        )

        return "\n".join(prompt_parts)

    def _get_dominant_campaign_type(self, flagged: list[CampaignHealthData]) -> str | None:
        """Determine dominant campaign type from flagged campaigns.

        Parses campaign names to infer type (Brand, NonBrand, Competitor).

        Args:
            flagged: List of flagged campaigns

        Returns:
            Campaign type string ("brand", "non_brand", "competitor") or None
        """
        type_counts = {"brand": 0, "non_brand": 0, "competitor": 0}

        for campaign in flagged:
            name_lower = campaign.campaign_name.lower()
            if "brand" in name_lower and "nonbrand" not in name_lower:
                type_counts["brand"] += 1
            elif "nonbrand" in name_lower or "non_brand" in name_lower:
                type_counts["non_brand"] += 1
            elif "competitor" in name_lower:
                type_counts["competitor"] += 1

        # Return most common type, or None if no campaigns match
        if sum(type_counts.values()) == 0:
            return None

        return max(type_counts, key=type_counts.get)

    def _get_dominant_conversion_goal(
        self,
        flagged: list[CampaignHealthData],
        taxonomy_map: dict[str, Any],
    ) -> str | None:
        """Determine dominant conversion goal from flagged campaigns.

        Args:
            flagged: List of flagged campaigns
            taxonomy_map: Campaign ID -> taxonomy mapping

        Returns:
            Conversion goal string or None
        """
        goal_counts: dict[str, int] = {}

        for campaign in flagged:
            taxonomy = taxonomy_map.get(campaign.campaign_id)
            if taxonomy and taxonomy.conversion_goal:
                # Normalize to lowercase with underscores for INDEX.md lookup
                normalized_goal = taxonomy.conversion_goal.lower().replace(" ", "_")
                goal_counts[normalized_goal] = goal_counts.get(normalized_goal, 0) + 1

        if not goal_counts:
            return None

        return max(goal_counts, key=goal_counts.get)

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
