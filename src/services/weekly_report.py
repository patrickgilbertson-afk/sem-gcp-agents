"""Service for generating weekly optimization reports."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from src.config import settings
from src.core import AnthropicClient
from src.integrations.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)


class WeeklyReportService:
    """Service for generating weekly optimization summary reports."""

    def __init__(self, bq_client: BigQueryClient | None = None):
        """Initialize weekly report service.

        Args:
            bq_client: BigQuery client for querying data
        """
        self.bq_client = bq_client or BigQueryClient()
        self.llm = AnthropicClient(model="claude-sonnet-4-5")
        self.logger = logger.bind(component="weekly_report")

    async def generate_report(self, days_back: int = 7) -> dict[str, Any]:
        """Generate weekly optimization report.

        Args:
            days_back: Number of days to look back (default 7)

        Returns:
            Report data dictionary with summary and sync group breakdowns
        """
        self.logger.info("generating_weekly_report", days_back=days_back)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Query recommendations created/approved/applied in the past week
        recommendations_sql = f"""
        SELECT
            r.id,
            r.run_id,
            r.agent_type,
            r.title,
            r.description,
            r.action_type,
            r.status,
            r.approval_status,
            r.created_at,
            r.approved_at,
            r.applied_at,
            r.metadata
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.agent_recommendations` r
        WHERE r.created_at >= @start_date
        AND r.status IN ('applied', 'approved')
        ORDER BY r.created_at DESC
        """

        recommendations = await self.bq_client.query(
            recommendations_sql,
            {
                "start_date": start_date.isoformat(),
            },
        )

        if not recommendations:
            self.logger.info("no_recommendations_this_week")
            return {
                "total_optimizations": 0,
                "sync_group_reports": [],
                "executive_summary": "No optimizations were applied this week.",
            }

        # Query performance metrics for applied recommendations
        performance_sql = f"""
        SELECT
            pm.recommendation_id,
            pm.metric_name,
            pm.before_value,
            pm.after_value,
            pm.change_value,
            pm.change_percent
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.performance_metrics` pm
        WHERE pm.outcome_recorded_at >= @start_date
        AND pm.after_value IS NOT NULL
        """

        performance_data = await self.bq_client.query(
            performance_sql,
            {
                "start_date": start_date.isoformat(),
            },
        )

        # Group by sync group
        import json
        sync_group_data: dict[str, list[dict]] = {}

        for rec in recommendations:
            metadata = json.loads(rec["metadata"]) if rec.get("metadata") else {}
            sync_group = metadata.get("sync_group", "individual")

            if sync_group not in sync_group_data:
                sync_group_data[sync_group] = []

            sync_group_data[sync_group].append({
                "id": rec["id"],
                "title": rec["title"],
                "description": rec["description"],
                "action_type": rec["action_type"],
                "status": rec["status"],
                "created_at": rec["created_at"],
                "metadata": metadata,
            })

        # Build performance index by recommendation_id
        perf_by_rec: dict[str, dict[str, dict]] = {}
        for perf in performance_data:
            rec_id = perf["recommendation_id"]
            if rec_id not in perf_by_rec:
                perf_by_rec[rec_id] = {}
            perf_by_rec[rec_id][perf["metric_name"]] = {
                "before": perf["before_value"],
                "after": perf["after_value"],
                "change": perf["change_value"],
                "change_pct": perf["change_percent"],
            }

        # Generate sync group reports
        sync_group_reports = []

        for sync_group, recs in sync_group_data.items():
            # Calculate aggregate performance for this sync group
            total_cost_before = 0
            total_cost_after = 0
            total_conversions_before = 0
            total_conversions_after = 0
            total_clicks_before = 0
            total_clicks_after = 0
            total_impressions_before = 0
            total_impressions_after = 0

            for rec in recs:
                rec_id = rec["id"]
                if rec_id in perf_by_rec:
                    metrics = perf_by_rec[rec_id]
                    if "cost" in metrics:
                        total_cost_before += metrics["cost"]["before"]
                        total_cost_after += metrics["cost"]["after"]
                    if "conversions" in metrics:
                        total_conversions_before += metrics["conversions"]["before"]
                        total_conversions_after += metrics["conversions"]["after"]
                    if "clicks" in metrics:
                        total_clicks_before += metrics["clicks"]["before"]
                        total_clicks_after += metrics["clicks"]["after"]
                    if "impressions" in metrics:
                        total_impressions_before += metrics["impressions"]["before"]
                        total_impressions_after += metrics["impressions"]["after"]

            # Calculate aggregate metrics
            cpa_before = total_cost_before / total_conversions_before if total_conversions_before > 0 else 0
            cpa_after = total_cost_after / total_conversions_after if total_conversions_after > 0 else 0
            cpa_change_pct = ((cpa_after - cpa_before) / cpa_before * 100) if cpa_before > 0 else 0

            ctr_before = total_clicks_before / total_impressions_before if total_impressions_before > 0 else 0
            ctr_after = total_clicks_after / total_impressions_after if total_impressions_after > 0 else 0
            ctr_change_pct = ((ctr_after - ctr_before) / ctr_before * 100) if ctr_before > 0 else 0

            sync_group_reports.append({
                "sync_group": sync_group,
                "optimization_count": len(recs),
                "optimizations": recs,
                "performance": {
                    "cpa": {
                        "before": cpa_before,
                        "after": cpa_after,
                        "change_pct": cpa_change_pct,
                    },
                    "ctr": {
                        "before": ctr_before,
                        "after": ctr_after,
                        "change_pct": ctr_change_pct,
                    },
                    "cost": {
                        "before": total_cost_before,
                        "after": total_cost_after,
                        "change": total_cost_after - total_cost_before,
                    },
                },
            })

        # Generate executive summary with Claude
        summary_prompt = self._build_summary_prompt(sync_group_reports, len(recommendations))
        executive_summary = await self.llm.generate(
            prompt=summary_prompt,
            system="You are a concise business analyst summarizing marketing optimization results. "
                   "Keep summaries to 2-3 sentences maximum, focusing on key wins and overall impact.",
            temperature=0.7,
            max_tokens=300,
        )

        self.logger.info(
            "weekly_report_generated",
            total_optimizations=len(recommendations),
            sync_groups=len(sync_group_reports),
        )

        return {
            "week_start": start_date.isoformat(),
            "week_end": end_date.isoformat(),
            "total_optimizations": len(recommendations),
            "sync_group_reports": sync_group_reports,
            "executive_summary": executive_summary.strip(),
        }

    def _build_summary_prompt(
        self,
        sync_group_reports: list[dict],
        total_optimizations: int,
    ) -> str:
        """Build prompt for generating executive summary.

        Args:
            sync_group_reports: List of sync group report data
            total_optimizations: Total number of optimizations

        Returns:
            Prompt string
        """
        prompt_parts = [
            f"Generate a concise 2-3 sentence executive summary for this week's optimizations.\n\n"
            f"Total Optimizations Applied: {total_optimizations}\n"
            f"Sync Groups Affected: {len(sync_group_reports)}\n\n"
            "Performance by Sync Group:\n"
        ]

        for report in sync_group_reports:
            sg = report["sync_group"]
            count = report["optimization_count"]
            perf = report["performance"]

            cpa_change = perf["cpa"]["change_pct"]
            ctr_change = perf["ctr"]["change_pct"]

            prompt_parts.append(
                f"- {sg}: {count} optimizations, "
                f"CPA {cpa_change:+.1f}%, CTR {ctr_change:+.1f}%"
            )

        prompt_parts.append(
            "\n\nSummarize:\n"
            "1. How many optimizations were applied\n"
            "2. Overall impact (CPA improvement, etc.)\n"
            "3. Biggest wins (which sync groups improved most)\n\n"
            "Keep it to 2-3 sentences maximum."
        )

        return "\n".join(prompt_parts)
