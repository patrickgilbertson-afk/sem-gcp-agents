"""Campaign taxonomy auto-detection utilities."""

import re
from datetime import datetime, timezone

import structlog

from src.models.taxonomy import (
    CampaignTaxonomy,
    CampaignType,
    DetectionMethod,
    ManagementStrategy,
)

logger = structlog.get_logger(__name__)


def parse_campaign_name(
    campaign_id: str,
    campaign_name: str,
    customer_id: str,
    campaign_status: str | None = None,
) -> CampaignTaxonomy:
    """Parse campaign name to extract taxonomy information.

    Expected naming convention:
    - Brand campaigns: Brand_<Geo> (e.g., Brand_US, Brand_UK)
    - NonBrand campaigns: NonBrand_<Vertical>_<Geo> (e.g., NonBrand_AI-Code_US)
    - Competitor campaigns: Competitor_<Name>_<Geo> (e.g., Competitor_GitHub_US)

    Args:
        campaign_id: Google Ads campaign ID
        campaign_name: Campaign name to parse
        customer_id: Google Ads customer ID
        campaign_status: Campaign status (ENABLED, PAUSED, etc.)

    Returns:
        CampaignTaxonomy with auto-detected fields
    """
    logger_ctx = logger.bind(campaign_id=campaign_id, campaign_name=campaign_name)

    # Default values
    campaign_type = CampaignType.NON_BRAND
    vertical = "unknown"
    geo = "unknown"
    sync_group = campaign_name
    management_strategy = ManagementStrategy.INDIVIDUAL
    is_template = False
    confidence = 0.0
    agent_exclusions = []
    external_manager = None

    # Parse Brand campaigns: Brand_<Geo>
    brand_match = re.match(r"^Brand[_-]([A-Z]{2})$", campaign_name, re.IGNORECASE)
    if brand_match:
        campaign_type = CampaignType.BRAND
        geo = brand_match.group(1).upper()
        vertical = "brand"
        sync_group = "brand"  # All Brand campaigns share sync group
        management_strategy = ManagementStrategy.SYNCED
        is_template = geo == "US"  # US is template by default
        confidence = 0.95

        # Default exclusions for Brand campaigns
        agent_exclusions = ["keyword", "bid_modifier"]
        external_manager = "brand_vendor"

        logger_ctx.info(
            "parsed_brand_campaign",
            geo=geo,
            sync_group=sync_group,
            agent_exclusions=agent_exclusions,
        )

    # Parse NonBrand campaigns: NonBrand_<Vertical>_<Geo>
    else:
        nonbrand_match = re.match(
            r"^NonBrand[_-]([A-Za-z0-9-]+)[_-]([A-Z]{2})$",
            campaign_name,
            re.IGNORECASE,
        )
        if nonbrand_match:
            campaign_type = CampaignType.NON_BRAND
            vertical = nonbrand_match.group(1)
            geo = nonbrand_match.group(2).upper()
            sync_group = f"NonBrand_{vertical}"
            management_strategy = ManagementStrategy.SYNCED
            is_template = geo == "US"
            confidence = 0.95

            logger_ctx.info(
                "parsed_nonbrand_campaign",
                vertical=vertical,
                geo=geo,
                sync_group=sync_group,
            )

        # Parse Competitor campaigns: Competitor_<Name>_<Geo>
        else:
            competitor_match = re.match(
                r"^Competitor[_-]([A-Za-z0-9-]+)[_-]([A-Z]{2})$",
                campaign_name,
                re.IGNORECASE,
            )
            if competitor_match:
                campaign_type = CampaignType.COMPETITOR
                competitor_name = competitor_match.group(1)
                geo = competitor_match.group(2).upper()
                vertical = f"competitor_{competitor_name.lower()}"
                sync_group = f"Competitor_{competitor_name}_{geo}"
                management_strategy = ManagementStrategy.INDIVIDUAL
                is_template = True  # Each competitor campaign is its own template
                confidence = 0.90

                logger_ctx.info(
                    "parsed_competitor_campaign",
                    competitor=competitor_name,
                    geo=geo,
                    sync_group=sync_group,
                )

            # Fallback: couldn't parse
            else:
                logger_ctx.warning(
                    "unparseable_campaign_name",
                    message="Campaign name doesn't match expected patterns",
                )
                confidence = 0.0

    now = datetime.now(timezone.utc)

    return CampaignTaxonomy(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        customer_id=customer_id,
        campaign_type=campaign_type,
        vertical=vertical,
        geo=geo,
        sync_group=sync_group,
        management_strategy=management_strategy,
        is_template=is_template,
        detection_method=DetectionMethod.AUTO,
        detection_confidence=confidence,
        campaign_status=campaign_status,
        agent_exclusions=agent_exclusions,
        external_manager=external_manager,
        created_at=now,
        updated_at=now,
        updated_by="auto_detection",
        notes=None,
    )


def validate_taxonomy(taxonomy: CampaignTaxonomy) -> tuple[bool, list[str]]:
    """Validate a taxonomy object for consistency.

    Args:
        taxonomy: CampaignTaxonomy to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required fields
    if not taxonomy.campaign_id:
        errors.append("campaign_id is required")
    if not taxonomy.campaign_name:
        errors.append("campaign_name is required")
    if not taxonomy.customer_id:
        errors.append("customer_id is required")

    # Check geo format
    if taxonomy.geo != "unknown" and not re.match(r"^[A-Z]{2}$", taxonomy.geo):
        errors.append(f"Invalid geo format: {taxonomy.geo} (expected 2-letter country code)")

    # Check sync group consistency
    if taxonomy.management_strategy == ManagementStrategy.SYNCED:
        if taxonomy.campaign_type == CampaignType.BRAND:
            if taxonomy.sync_group != "brand":
                errors.append(f"Brand campaigns should have sync_group='brand', got '{taxonomy.sync_group}'")
        elif taxonomy.campaign_type == CampaignType.NON_BRAND:
            expected_prefix = f"NonBrand_{taxonomy.vertical}"
            if not taxonomy.sync_group.startswith(expected_prefix):
                errors.append(
                    f"NonBrand synced campaigns should have sync_group='{expected_prefix}', got '{taxonomy.sync_group}'"
                )

    # Check agent exclusions are valid
    from src.models.base import AgentType

    valid_agent_types = {at.value for at in AgentType}
    for exclusion in taxonomy.agent_exclusions:
        if exclusion not in valid_agent_types:
            errors.append(f"Invalid agent_exclusion: {exclusion} (valid: {valid_agent_types})")

    # If exclusions are set, external_manager should be set
    if taxonomy.agent_exclusions and not taxonomy.external_manager:
        errors.append("external_manager should be set when agent_exclusions are present")

    return len(errors) == 0, errors
