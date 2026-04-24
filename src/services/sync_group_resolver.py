"""Service for resolving entities across campaigns in a sync group."""

from typing import Any

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient
from src.models.taxonomy import SyncGroupContext

logger = structlog.get_logger(__name__)


class SyncGroupResolver:
    """Service for matching entities by name across geos in a sync group.

    When propagating actions from a template campaign to other geos, we need to
    find equivalent entities (ad groups, keywords, ads) by name, since IDs differ.
    """

    def __init__(self, bq_client: BigQueryClient | None = None):
        """Initialize sync group resolver.

        Args:
            bq_client: BigQuery client for querying Google Ads data
        """
        self.bq_client = bq_client or BigQueryClient()
        self.logger = logger.bind(component="sync_group_resolver")
        self._cache: dict[str, Any] = {}

    async def resolve_ad_group(
        self,
        source_ad_group_name: str,
        target_campaign_id: str,
    ) -> str | None:
        """Find ad group in target campaign by name.

        Args:
            source_ad_group_name: Name of ad group to find
            target_campaign_id: Campaign to search in

        Returns:
            Ad group ID if found, None otherwise
        """
        cache_key = f"ag:{target_campaign_id}:{source_ad_group_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Query Google Ads raw data for ad group by name
            sql = f"""
            SELECT ad_group_id
            FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.ad_group_{settings.google_ads_customer_id}`
            WHERE campaign_id = @campaign_id
            AND ad_group_name = @ad_group_name
            AND ad_group_status != 'REMOVED'
            LIMIT 1
            """

            rows = await self.bq_client.query(
                sql,
                {
                    "campaign_id": target_campaign_id,
                    "ad_group_name": source_ad_group_name,
                },
            )

            if rows:
                ad_group_id = str(rows[0]["ad_group_id"])
                self._cache[cache_key] = ad_group_id
                return ad_group_id

            self.logger.warning(
                "ad_group_not_found",
                ad_group_name=source_ad_group_name,
                campaign_id=target_campaign_id,
            )
            return None

        except Exception as e:
            self.logger.error(
                "resolve_ad_group_failed",
                error=str(e),
                ad_group_name=source_ad_group_name,
                campaign_id=target_campaign_id,
            )
            return None

    async def resolve_keyword(
        self,
        keyword_text: str,
        match_type: str,
        source_ad_group_id: str,
        target_ad_group_id: str,
    ) -> str | None:
        """Find keyword in target ad group by text and match type.

        Args:
            keyword_text: Keyword text (e.g., "ai code editor")
            match_type: Match type (EXACT, PHRASE, BROAD)
            source_ad_group_id: Source ad group ID (for logging)
            target_ad_group_id: Target ad group to search in

        Returns:
            Keyword ID if found, None otherwise
        """
        cache_key = f"kw:{target_ad_group_id}:{keyword_text}:{match_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Query Google Ads raw data for keyword by text and match type
            sql = f"""
            SELECT criterion_id
            FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.keyword_{settings.google_ads_customer_id}`
            WHERE ad_group_id = @ad_group_id
            AND keyword_text = @keyword_text
            AND keyword_match_type = @match_type
            AND status != 'REMOVED'
            LIMIT 1
            """

            rows = await self.bq_client.query(
                sql,
                {
                    "ad_group_id": target_ad_group_id,
                    "keyword_text": keyword_text,
                    "match_type": match_type,
                },
            )

            if rows:
                keyword_id = str(rows[0]["criterion_id"])
                self._cache[cache_key] = keyword_id
                return keyword_id

            self.logger.warning(
                "keyword_not_found",
                keyword_text=keyword_text,
                match_type=match_type,
                ad_group_id=target_ad_group_id,
            )
            return None

        except Exception as e:
            self.logger.error(
                "resolve_keyword_failed",
                error=str(e),
                keyword_text=keyword_text,
                ad_group_id=target_ad_group_id,
            )
            return None

    async def resolve_entities_for_sync_group(
        self,
        action_params: dict[str, Any],
        source_campaign_id: str,
        sync_group_context: SyncGroupContext,
    ) -> list[dict[str, Any]]:
        """Resolve equivalent entities across all campaigns in sync group.

        Args:
            action_params: Original action parameters from source campaign
            source_campaign_id: Source campaign ID (to skip)
            sync_group_context: Context with all campaigns in sync group

        Returns:
            List of resolved action_params dicts for each target campaign
        """
        resolved = []

        # Get ad group name from source if present
        source_ad_group_name = action_params.get("ad_group_name")
        if not source_ad_group_name:
            # If no ad group name in params, need to look it up
            source_ad_group_id = action_params.get("ad_group_id")
            if source_ad_group_id:
                source_ad_group_name = await self._get_ad_group_name(source_ad_group_id)

        if not source_ad_group_name:
            self.logger.warning(
                "cannot_resolve_without_ad_group_name",
                action_params=action_params,
            )
            return []

        # Resolve for each campaign in sync group (except source)
        for campaign in sync_group_context.campaigns:
            if campaign.campaign_id == source_campaign_id:
                continue  # Skip source campaign

            # Resolve ad group
            target_ad_group_id = await self.resolve_ad_group(
                source_ad_group_name=source_ad_group_name,
                target_campaign_id=campaign.campaign_id,
            )

            if not target_ad_group_id:
                self.logger.warning(
                    "skip_campaign_ad_group_not_found",
                    campaign_id=campaign.campaign_id,
                    campaign_name=campaign.campaign_name,
                    ad_group_name=source_ad_group_name,
                )
                continue

            # Build resolved params
            resolved_params = {
                **action_params,
                "campaign_id": campaign.campaign_id,
                "ad_group_id": target_ad_group_id,
                "geo": campaign.geo,
            }

            # If keyword-level action, resolve keyword too
            if "keyword_text" in action_params and "match_type" in action_params:
                keyword_id = await self.resolve_keyword(
                    keyword_text=action_params["keyword_text"],
                    match_type=action_params["match_type"],
                    source_ad_group_id=action_params["ad_group_id"],
                    target_ad_group_id=target_ad_group_id,
                )
                if keyword_id:
                    resolved_params["keyword_id"] = keyword_id
                else:
                    # Skip if keyword not found
                    self.logger.warning(
                        "skip_campaign_keyword_not_found",
                        campaign_id=campaign.campaign_id,
                        keyword_text=action_params["keyword_text"],
                    )
                    continue

            resolved.append(resolved_params)

        self.logger.info(
            "entities_resolved",
            source_campaign=source_campaign_id,
            sync_group=sync_group_context.sync_group,
            resolved_count=len(resolved),
            total_campaigns=len(sync_group_context.campaigns),
        )

        return resolved

    async def _get_ad_group_name(self, ad_group_id: str) -> str | None:
        """Get ad group name by ID.

        Args:
            ad_group_id: Ad group ID

        Returns:
            Ad group name if found, None otherwise
        """
        cache_key = f"ag_name:{ad_group_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            sql = f"""
            SELECT ad_group_name
            FROM `{settings.gcp_project_id}.{settings.bq_dataset_raw}.ad_group_{settings.google_ads_customer_id}`
            WHERE ad_group_id = @ad_group_id
            LIMIT 1
            """

            rows = await self.bq_client.query(sql, {"ad_group_id": ad_group_id})
            if rows:
                name = rows[0]["ad_group_name"]
                self._cache[cache_key] = name
                return name

            return None

        except Exception as e:
            self.logger.error("get_ad_group_name_failed", error=str(e), ad_group_id=ad_group_id)
            return None
