"""Service for managing campaign taxonomy and sync groups."""

from datetime import datetime, timezone
from typing import Any

import structlog

from src.config import settings
from src.integrations.bigquery.client import BigQueryClient
from src.models.base import AgentType
from src.models.taxonomy import (
    CampaignTaxonomy,
    CampaignType,
    DetectionMethod,
    ManagementStrategy,
    SyncGroupContext,
)

logger = structlog.get_logger(__name__)


class TaxonomyService:
    """Service for campaign taxonomy operations."""

    def __init__(self, bq_client: BigQueryClient | None = None) -> None:
        """Initialize taxonomy service.

        Args:
            bq_client: Optional BigQuery client (creates one if not provided)
        """
        self.bq_client = bq_client or BigQueryClient()
        self.logger = logger.bind(component="taxonomy_service")

    async def get_by_campaign_id(self, campaign_id: str) -> CampaignTaxonomy | None:
        """Get taxonomy for a specific campaign.

        Args:
            campaign_id: Campaign ID to look up

        Returns:
            CampaignTaxonomy if found, None otherwise
        """
        sql = f"""
        SELECT
            campaign_id,
            campaign_name,
            customer_id,
            campaign_type,
            vertical,
            geo,
            sync_group,
            management_strategy,
            is_template,
            detection_method,
            detection_confidence,
            campaign_status,
            agent_exclusions,
            external_manager,
            created_at,
            updated_at,
            updated_by,
            notes
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
        WHERE campaign_id = @campaign_id
        LIMIT 1
        """

        rows = await self.bq_client.query(sql, {"campaign_id": campaign_id})
        if not rows:
            return None

        return self._row_to_taxonomy(rows[0])

    async def get_sync_group_context(self, sync_group: str) -> SyncGroupContext | None:
        """Get all campaigns in a sync group as a context object.

        Args:
            sync_group: Sync group identifier

        Returns:
            SyncGroupContext with all campaigns, or None if not found
        """
        sql = f"""
        SELECT
            campaign_id,
            campaign_name,
            customer_id,
            campaign_type,
            vertical,
            geo,
            sync_group,
            management_strategy,
            is_template,
            detection_method,
            detection_confidence,
            campaign_status,
            agent_exclusions,
            external_manager,
            created_at,
            updated_at,
            updated_by,
            notes
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
        WHERE sync_group = @sync_group
        ORDER BY is_template DESC, geo ASC
        """

        rows = await self.bq_client.query(sql, {"sync_group": sync_group})
        if not rows:
            return None

        campaigns = [self._row_to_taxonomy(row) for row in rows]
        template = next((c for c in campaigns if c.is_template), None) or campaigns[0]

        return SyncGroupContext(
            sync_group=sync_group,
            campaign_type=campaigns[0].campaign_type,
            vertical=campaigns[0].vertical,
            management_strategy=campaigns[0].management_strategy,
            campaigns=campaigns,
            template_campaign=template,
        )

    async def get_all_sync_groups(self, customer_id: str | None = None) -> list[SyncGroupContext]:
        """Get all sync groups, optionally filtered by customer.

        Args:
            customer_id: Optional customer ID filter

        Returns:
            List of SyncGroupContext objects
        """
        where_clause = "WHERE customer_id = @customer_id" if customer_id else ""
        params = {"customer_id": customer_id} if customer_id else None

        sql = f"""
        SELECT DISTINCT sync_group
        FROM `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
        {where_clause}
        ORDER BY sync_group
        """

        rows = await self.bq_client.query(sql, params)
        sync_groups = [row["sync_group"] for row in rows]

        contexts = []
        for sg in sync_groups:
            context = await self.get_sync_group_context(sg)
            if context:
                contexts.append(context)

        return contexts

    async def is_agent_excluded(self, campaign_id: str, agent_type: AgentType) -> bool:
        """Check if an agent should skip this campaign.

        Args:
            campaign_id: Campaign ID to check
            agent_type: Type of agent

        Returns:
            True if the agent should skip this campaign
        """
        taxonomy = await self.get_by_campaign_id(campaign_id)
        if taxonomy is None:
            # Unclassified campaigns are not excluded
            return False

        return agent_type.value in taxonomy.agent_exclusions

    async def is_agent_excluded_for_sync_group(
        self, sync_group: str, agent_type: AgentType
    ) -> bool:
        """Check if an agent should skip this sync group.

        Args:
            sync_group: Sync group identifier
            agent_type: Type of agent

        Returns:
            True if the agent should skip this sync group
        """
        context = await self.get_sync_group_context(sync_group)
        if context is None:
            return False

        return context.is_agent_excluded(agent_type.value)

    async def update_exclusions(
        self,
        campaign_id: str,
        agent_exclusions: list[str],
        external_manager: str | None,
        updated_by: str,
    ) -> None:
        """Update agent exclusions for a campaign.

        Args:
            campaign_id: Campaign ID to update
            agent_exclusions: List of AgentType values to exclude
            external_manager: Who manages the excluded scope
            updated_by: User or system that made the update
        """
        sql = f"""
        UPDATE `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
        SET
            agent_exclusions = @agent_exclusions,
            external_manager = @external_manager,
            updated_at = @updated_at,
            updated_by = @updated_by
        WHERE campaign_id = @campaign_id
        """

        params = {
            "campaign_id": campaign_id,
            "agent_exclusions": agent_exclusions,
            "external_manager": external_manager,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": updated_by,
        }

        await self.bq_client.query(sql, params)

        self.logger.info(
            "exclusions_updated",
            campaign_id=campaign_id,
            agent_exclusions=agent_exclusions,
            external_manager=external_manager,
        )

    async def upsert_taxonomy(self, taxonomy: CampaignTaxonomy) -> None:
        """Insert or update a campaign taxonomy record.

        Args:
            taxonomy: CampaignTaxonomy to upsert
        """
        # Check if exists
        existing = await self.get_by_campaign_id(taxonomy.campaign_id)

        if existing:
            # Update
            sql = f"""
            UPDATE `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
            SET
                campaign_name = @campaign_name,
                campaign_type = @campaign_type,
                vertical = @vertical,
                geo = @geo,
                sync_group = @sync_group,
                management_strategy = @management_strategy,
                is_template = @is_template,
                detection_method = @detection_method,
                detection_confidence = @detection_confidence,
                campaign_status = @campaign_status,
                agent_exclusions = @agent_exclusions,
                external_manager = @external_manager,
                updated_at = @updated_at,
                updated_by = @updated_by,
                notes = @notes
            WHERE campaign_id = @campaign_id
            """
        else:
            # Insert
            sql = f"""
            INSERT INTO `{settings.gcp_project_id}.{settings.bq_dataset_agents}.campaign_taxonomy`
            (campaign_id, campaign_name, customer_id, campaign_type, vertical, geo,
             sync_group, management_strategy, is_template, detection_method,
             detection_confidence, campaign_status, agent_exclusions, external_manager,
             created_at, updated_at, updated_by, notes)
            VALUES
            (@campaign_id, @campaign_name, @customer_id, @campaign_type, @vertical, @geo,
             @sync_group, @management_strategy, @is_template, @detection_method,
             @detection_confidence, @campaign_status, @agent_exclusions, @external_manager,
             @created_at, @updated_at, @updated_by, @notes)
            """

        params = {
            "campaign_id": taxonomy.campaign_id,
            "campaign_name": taxonomy.campaign_name,
            "customer_id": taxonomy.customer_id,
            "campaign_type": taxonomy.campaign_type.value,
            "vertical": taxonomy.vertical,
            "geo": taxonomy.geo,
            "sync_group": taxonomy.sync_group,
            "management_strategy": taxonomy.management_strategy.value,
            "is_template": taxonomy.is_template,
            "detection_method": taxonomy.detection_method.value,
            "detection_confidence": taxonomy.detection_confidence,
            "campaign_status": taxonomy.campaign_status,
            "agent_exclusions": taxonomy.agent_exclusions,
            "external_manager": taxonomy.external_manager,
            "created_at": taxonomy.created_at,
            "updated_at": taxonomy.updated_at,
            "updated_by": taxonomy.updated_by,
            "notes": taxonomy.notes,
        }

        await self.bq_client.query(sql, params)

        self.logger.info(
            "taxonomy_upserted",
            campaign_id=taxonomy.campaign_id,
            sync_group=taxonomy.sync_group,
        )

    def _row_to_taxonomy(self, row: dict[str, Any]) -> CampaignTaxonomy:
        """Convert a BigQuery row to a CampaignTaxonomy object.

        Args:
            row: Row dictionary from BigQuery

        Returns:
            CampaignTaxonomy object
        """
        return CampaignTaxonomy(
            campaign_id=row["campaign_id"],
            campaign_name=row["campaign_name"],
            customer_id=row["customer_id"],
            campaign_type=CampaignType(row["campaign_type"]),
            vertical=row["vertical"],
            geo=row["geo"],
            sync_group=row["sync_group"],
            management_strategy=ManagementStrategy(row["management_strategy"]),
            is_template=row["is_template"],
            detection_method=DetectionMethod(row["detection_method"]),
            detection_confidence=row.get("detection_confidence"),
            campaign_status=row.get("campaign_status"),
            agent_exclusions=row.get("agent_exclusions", []),
            external_manager=row.get("external_manager"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            updated_by=row.get("updated_by"),
            notes=row.get("notes"),
        )
