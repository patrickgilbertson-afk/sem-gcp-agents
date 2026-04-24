"""Service for tracking before/after performance of applied recommendations."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient

logger = structlog.get_logger(__name__)


class PerformanceTracker:
    """Service for recording before/after metrics when recommendations are applied."""

    def __init__(self, bq_client: BigQueryClient | None = None):
        """Initialize performance tracker.

        Args:
            bq_client: BigQuery client for querying and writing data
        """
        self.bq_client = bq_client or BigQueryClient()
        self.logger = logger.bind(component="performance_tracker")

    async def record_baseline(
        self,
        recommendation_id: str,
        campaign_id: str,
        ad_group_id: str | None = None,
    ) -> None:
        """Record baseline metrics before applying a recommendation.

        Args:
            recommendation_id: Recommendation ID
            campaign_id: Campaign ID
            ad_group_id: Optional ad group ID (for ad-group-level actions)
        """
        try:
            # Query current metrics from Google Ads raw data (last 7 days)
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=7)

            if ad_group_id:
                # Ad group level metrics
                sql = f"""
                SELECT
                    SUM(metrics.impressions) as impressions,
                    SUM(metrics.clicks) as clicks,
                    SUM(metrics.cost_micros) / 1000000.0 as cost,
                    SUM(metrics.conversions) as conversions,
                    SUM(metrics.conversions_value) as conversion_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.ad_group_stats_{settings.google_ads_customer_id}`
                WHERE campaign_id = @campaign_id
                AND ad_group_id = @ad_group_id
                AND segments_date BETWEEN @start_date AND @end_date
                """
                params = {
                    "campaign_id": campaign_id,
                    "ad_group_id": ad_group_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            else:
                # Campaign level metrics
                sql = f"""
                SELECT
                    SUM(metrics.impressions) as impressions,
                    SUM(metrics.clicks) as clicks,
                    SUM(metrics.cost_micros) / 1000000.0 as cost,
                    SUM(metrics.conversions) as conversions,
                    SUM(metrics.conversions_value) as conversion_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.campaign_stats_{settings.google_ads_customer_id}`
                WHERE campaign_id = @campaign_id
                AND segments_date BETWEEN @start_date AND @end_date
                """
                params = {
                    "campaign_id": campaign_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }

            rows = await self.bq_client.query(sql, params)

            if not rows:
                self.logger.warning(
                    "no_baseline_metrics_found",
                    recommendation_id=recommendation_id,
                    campaign_id=campaign_id,
                )
                return

            metrics = rows[0]

            # Calculate derived metrics
            ctr = metrics["clicks"] / metrics["impressions"] if metrics["impressions"] > 0 else 0
            cpc = metrics["cost"] / metrics["clicks"] if metrics["clicks"] > 0 else 0
            cpa = metrics["cost"] / metrics["conversions"] if metrics["conversions"] > 0 else 0

            # Insert baseline into performance_metrics table
            await self.bq_client.insert_rows(
                "performance_metrics",
                [
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "impressions",
                        "before_value": float(metrics["impressions"]),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "clicks",
                        "before_value": float(metrics["clicks"]),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "cost",
                        "before_value": float(metrics["cost"]),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "conversions",
                        "before_value": float(metrics["conversions"]),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "ctr",
                        "before_value": float(ctr),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "cpc",
                        "before_value": float(cpc),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "recommendation_id": recommendation_id,
                        "metric_name": "cpa",
                        "before_value": float(cpa),
                        "measurement_window_days": 7,
                        "baseline_recorded_at": datetime.utcnow().isoformat(),
                    },
                ],
            )

            self.logger.info(
                "baseline_recorded",
                recommendation_id=recommendation_id,
                campaign_id=campaign_id,
            )

        except Exception as e:
            self.logger.error(
                "baseline_recording_failed",
                recommendation_id=recommendation_id,
                error=str(e),
            )
            # Don't raise - baseline recording is best-effort

    async def record_outcome(
        self,
        recommendation_id: str,
        campaign_id: str,
        ad_group_id: str | None = None,
        days_after: int = 7,
    ) -> None:
        """Record outcome metrics N days after applying a recommendation.

        Args:
            recommendation_id: Recommendation ID
            campaign_id: Campaign ID
            ad_group_id: Optional ad group ID
            days_after: Number of days after application to measure
        """
        try:
            # Query metrics for the same window as baseline, but shifted forward
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days_after)

            if ad_group_id:
                sql = f"""
                SELECT
                    SUM(metrics.impressions) as impressions,
                    SUM(metrics.clicks) as clicks,
                    SUM(metrics.cost_micros) / 1000000.0 as cost,
                    SUM(metrics.conversions) as conversions,
                    SUM(metrics.conversions_value) as conversion_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.ad_group_stats_{settings.google_ads_customer_id}`
                WHERE campaign_id = @campaign_id
                AND ad_group_id = @ad_group_id
                AND segments_date BETWEEN @start_date AND @end_date
                """
                params = {
                    "campaign_id": campaign_id,
                    "ad_group_id": ad_group_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            else:
                sql = f"""
                SELECT
                    SUM(metrics.impressions) as impressions,
                    SUM(metrics.clicks) as clicks,
                    SUM(metrics.cost_micros) / 1000000.0 as cost,
                    SUM(metrics.conversions) as conversions,
                    SUM(metrics.conversions_value) as conversion_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.campaign_stats_{settings.google_ads_customer_id}`
                WHERE campaign_id = @campaign_id
                AND segments_date BETWEEN @start_date AND @end_date
                """
                params = {
                    "campaign_id": campaign_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }

            rows = await self.bq_client.query(sql, params)

            if not rows:
                self.logger.warning(
                    "no_outcome_metrics_found",
                    recommendation_id=recommendation_id,
                    campaign_id=campaign_id,
                )
                return

            metrics = rows[0]

            # Calculate derived metrics
            ctr = metrics["clicks"] / metrics["impressions"] if metrics["impressions"] > 0 else 0
            cpc = metrics["cost"] / metrics["clicks"] if metrics["clicks"] > 0 else 0
            cpa = metrics["cost"] / metrics["conversions"] if metrics["conversions"] > 0 else 0

            # Update performance_metrics with after values
            metric_values = {
                "impressions": float(metrics["impressions"]),
                "clicks": float(metrics["clicks"]),
                "cost": float(metrics["cost"]),
                "conversions": float(metrics["conversions"]),
                "ctr": float(ctr),
                "cpc": float(cpc),
                "cpa": float(cpa),
            }

            for metric_name, after_value in metric_values.items():
                # Query baseline value
                sql = f"""
                SELECT before_value
                FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.performance_metrics`
                WHERE recommendation_id = @recommendation_id
                AND metric_name = @metric_name
                LIMIT 1
                """

                baseline_rows = await self.bq_client.query(
                    sql,
                    {"recommendation_id": recommendation_id, "metric_name": metric_name},
                )

                if baseline_rows:
                    before_value = baseline_rows[0]["before_value"]
                    change_value = after_value - before_value
                    change_percent = (
                        (change_value / before_value * 100) if before_value > 0 else 0
                    )

                    # Update record with after values
                    sql = f"""
                    UPDATE `{settings.gcp_project_id}.{settings.bq_dataset_agents}.performance_metrics`
                    SET
                        after_value = @after_value,
                        change_value = @change_value,
                        change_percent = @change_percent,
                        outcome_recorded_at = CURRENT_TIMESTAMP()
                    WHERE recommendation_id = @recommendation_id
                    AND metric_name = @metric_name
                    """

                    await self.bq_client.query(
                        sql,
                        {
                            "recommendation_id": recommendation_id,
                            "metric_name": metric_name,
                            "after_value": after_value,
                            "change_value": change_value,
                            "change_percent": change_percent,
                        },
                    )

            self.logger.info(
                "outcome_recorded",
                recommendation_id=recommendation_id,
                campaign_id=campaign_id,
                days_after=days_after,
            )

        except Exception as e:
            self.logger.error(
                "outcome_recording_failed",
                recommendation_id=recommendation_id,
                error=str(e),
            )
            # Don't raise - outcome recording is best-effort
