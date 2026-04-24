"""Campaign taxonomy auto-detection utilities.

Supports two naming conventions:

1. Standard format (2026+):
   {Year}_Q{Quarter}_{Funnel}_{Type}_{Vertical}_{Region}_{SubRegion}_{Platform}_Search_{BidStrategy}
   Examples:
   - 2026_Q1_BOF_Brand_APJ_ANZ_Google_Search_Clicks_Beinc
   - 2026_Q1_MOF_NonBrand_AI-Code_EMEA_DE_Google_Search_Conversions
   - 2026_Q2_MOF_Competitor_Snyk_Global_Google_Search_Clicks
   - 2026_Q2_BOF_Enterprise_NA_AMER_Google_Leads_SLG

2. Legacy SQ format:
   SQ {Region} {SubRegion} - {Type} - {Suffix}
   Examples:
   - SQ APJ 1 Jap - Brand - Beinc
   - SQ EMEA ACH - Generic AI
   - SQ - Competitor - Aikido
"""

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

# Known geo regions/sub-regions for sync group detection
GEO_REGIONS = {
    "APJ": ["ANZ", "ASEAN", "EA", "JP"],
    "EMEA": ["ACH", "Benelux", "DE", "FR", "MEA", "Med", "Nord", "UKI"],
    "NA": ["CA", "US-East", "US-West"],
    "AMER": [],
    "Global": [],
}

# SQ legacy region mappings
SQ_GEO_MAP = {
    "APJ 1 Jap": "APJ_JP",
    "APJ 2 All": "APJ_All",
    "APJ 3 ANZ": "APJ_ANZ",
    "APJ 4 All": "APJ_ASEAN",
    "EMEA ACH": "EMEA_ACH",
    "EMEA East DACH": "EMEA_DACH",
    "EMEA North Nordics": "EMEA_Nord",
    "EMEA North UKI": "EMEA_UKI",
    "EMEA South MEA": "EMEA_MEA",
    "EMEA South South": "EMEA_Med",
    "NA East": "NA_US-East",
    "NA West": "NA_US-West",
    "NA CA": "NA_CA",
}


def parse_campaign_name(
    campaign_id: str,
    campaign_name: str,
    customer_id: str,
    campaign_status: str | None = None,
) -> CampaignTaxonomy:
    """Parse campaign name to extract taxonomy information.

    Args:
        campaign_id: Google Ads campaign ID
        campaign_name: Campaign name to parse
        customer_id: Google Ads customer ID
        campaign_status: Campaign status (ENABLED, PAUSED, etc.)

    Returns:
        CampaignTaxonomy with auto-detected fields
    """
    logger_ctx = logger.bind(campaign_id=campaign_id, campaign_name=campaign_name)

    # Try standard format first, then SQ legacy, then fallback
    result = _parse_standard_format(campaign_name, logger_ctx)
    if not result:
        result = _parse_sq_legacy_format(campaign_name, logger_ctx)
    if not result:
        result = _parse_other_format(campaign_name, logger_ctx)

    campaign_type, vertical, geo, sync_group, management_strategy, is_template, confidence = result

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
        agent_exclusions=[],
        external_manager=None,
        created_at=now,
        updated_at=now,
        updated_by="auto_detection",
        notes=None,
    )


def _parse_standard_format(campaign_name: str, logger_ctx) -> tuple | None:
    """Parse standard format: {Year}_Q{Q}_{Funnel}_{Type}_{...}

    Returns tuple of (campaign_type, vertical, geo, sync_group, management_strategy, is_template, confidence)
    or None if not matched.
    """
    # Match: 2026_Q1_BOF_Brand_APJ_ANZ_Google_Search_Clicks_Beinc
    # Match: 2026_Q1_MOF_NonBrand_AI-Code_EMEA_DE_Google_Search_Conversions
    # Match: 2026_Q2_MOF_Competitor_Snyk_Global_Google_Search_Clicks
    # Match: 2026_Q2_BOF_Enterprise_ANZ_APJ_Google_Leads_SLG
    match = re.match(
        r"^(\d{4})_Q(\d)_(BOF|MOF|TOF)_(\w+?)_(.+?)_Google_",
        campaign_name,
    )
    if not match:
        return None

    year = match.group(1)
    quarter = match.group(2)
    funnel = match.group(3)
    type_str = match.group(4)
    middle = match.group(5)  # Everything between type and _Google_

    # Determine campaign type
    type_lower = type_str.lower()
    if type_lower == "brand":
        campaign_type = CampaignType.BRAND
    elif type_lower == "nonbrand":
        campaign_type = CampaignType.NON_BRAND
    elif type_lower == "competitor":
        campaign_type = CampaignType.COMPETITOR
    elif type_lower == "enterprise":
        campaign_type = CampaignType.ENTERPRISE
    else:
        campaign_type = CampaignType.NON_BRAND

    # Parse the middle section based on type
    vertical, geo = _parse_middle_section(type_lower, middle)

    # Build sync group (campaigns sharing same type+vertical across geos)
    sync_group = f"{year}_Q{quarter}_{funnel}_{type_str}_{vertical}"

    # Determine management strategy
    if campaign_type == CampaignType.COMPETITOR:
        management_strategy = ManagementStrategy.INDIVIDUAL
        is_template = True
    else:
        # Brand, NonBrand, Enterprise with multiple geos are synced
        management_strategy = ManagementStrategy.SYNCED
        # US-East or first geo alphabetically is template
        is_template = "US" in geo or geo == "NA_US-East"

    logger_ctx.info(
        "parsed_standard_format",
        campaign_type=campaign_type.value,
        vertical=vertical,
        geo=geo,
        sync_group=sync_group,
    )

    return (campaign_type, vertical, geo, sync_group, management_strategy, is_template, 0.90)


def _parse_middle_section(type_lower: str, middle: str) -> tuple[str, str]:
    """Parse the middle section between type and _Google_ to extract vertical and geo.

    Returns (vertical, geo).
    """
    parts = middle.split("_")

    if type_lower == "brand":
        # Brand: middle is geo parts, possibly with product prefix
        # e.g., "APJ_ANZ" or "SonarSweep_Global" or "Translated-German_EMEA"
        if len(parts) >= 2:
            # Check if first part looks like a region
            if parts[0] in GEO_REGIONS:
                geo = f"{parts[0]}_{parts[1]}"
                vertical = "brand"
            else:
                # First part is a product/variant, rest is geo
                vertical = parts[0]
                geo = "_".join(parts[1:])
        else:
            vertical = "brand"
            geo = parts[0] if parts else "unknown"

    elif type_lower == "nonbrand":
        # NonBrand: first part is vertical, rest is geo
        # e.g., "AI-Code_EMEA_DE" or "Security_NA_US-East"
        if len(parts) >= 3:
            vertical = parts[0]
            geo = f"{parts[1]}_{parts[2]}"
        elif len(parts) == 2:
            vertical = parts[0]
            geo = parts[1]
        else:
            vertical = parts[0] if parts else "unknown"
            geo = "unknown"

    elif type_lower == "competitor":
        # Competitor: first part is competitor name, rest is geo
        # e.g., "Snyk_Global" or "Github-CodeQuality_Global"
        if len(parts) >= 2:
            vertical = parts[0]
            geo = "_".join(parts[1:])
        else:
            vertical = parts[0] if parts else "unknown"
            geo = "Global"

    elif type_lower == "enterprise":
        # Enterprise: first part is geo sub-region, second is region
        # e.g., "ANZ_APJ" or "NA_AMER" or "DE_EMEA"
        if len(parts) >= 2:
            vertical = "enterprise"
            geo = f"{parts[1]}_{parts[0]}"  # Region_SubRegion
        else:
            vertical = "enterprise"
            geo = parts[0] if parts else "unknown"

    else:
        vertical = middle
        geo = "unknown"

    return vertical, geo


def _parse_sq_legacy_format(campaign_name: str, logger_ctx) -> tuple | None:
    """Parse SQ legacy format: SQ {Region} - {Type} - {Suffix}

    Returns tuple or None if not matched.
    """
    if not campaign_name.startswith("SQ ") and not campaign_name.startswith("SQ -"):
        return None

    # Handle "SQ - Competitor - Name" (no region)
    competitor_match = re.match(r"^SQ\s*-\s*Competitor\s*-\s*(.+)$", campaign_name)
    if competitor_match:
        competitor_name = competitor_match.group(1).strip()
        logger_ctx.info("parsed_sq_competitor", competitor=competitor_name)
        return (
            CampaignType.COMPETITOR,
            f"competitor_{competitor_name.lower().replace(' ', '_')}",
            "Global",
            f"SQ_Competitor_{competitor_name}",
            ManagementStrategy.INDIVIDUAL,
            True,
            0.85,
        )

    # Parse region-based SQ campaigns
    # SQ {Region Info} - {Type} - {Suffix}
    # SQ {Region Info} - {Type}
    sq_match = re.match(r"^SQ\s+(.+?)\s*-\s*(Brand|Generic|NonBrand)\s*(?:-\s*(.*))?$", campaign_name)
    if not sq_match:
        # Try without type separator (e.g., "SQ APJ 1 Jap - Generic AI")
        sq_match = re.match(r"^SQ\s+(.+?)\s*-\s*(Generic\s+\w+|Brand\s*.*)$", campaign_name)
        if sq_match:
            region_str = sq_match.group(1).strip()
            type_and_suffix = sq_match.group(2).strip()

            if type_and_suffix.startswith("Brand"):
                campaign_type = CampaignType.BRAND
                vertical = "brand"
                suffix = type_and_suffix.replace("Brand", "").strip(" -")
            elif type_and_suffix.startswith("Generic"):
                campaign_type = CampaignType.NON_BRAND
                vertical = type_and_suffix.replace("Generic ", "").strip()
                suffix = ""
            else:
                return None

            geo = _resolve_sq_geo(region_str)
            sync_group = f"SQ_{campaign_type.value}_{vertical}"

            logger_ctx.info(
                "parsed_sq_legacy",
                campaign_type=campaign_type.value,
                vertical=vertical,
                geo=geo,
            )

            return (
                campaign_type,
                vertical,
                geo,
                sync_group,
                ManagementStrategy.SYNCED,
                "US" in geo,
                0.80,
            )
        return None

    region_str = sq_match.group(1).strip()
    type_str = sq_match.group(2).strip()
    suffix = (sq_match.group(3) or "").strip()

    if type_str == "Brand":
        campaign_type = CampaignType.BRAND
        vertical = "brand"
    elif type_str in ("Generic", "NonBrand"):
        campaign_type = CampaignType.NON_BRAND
        vertical = suffix if suffix else "general"
    else:
        campaign_type = CampaignType.NON_BRAND
        vertical = "general"

    geo = _resolve_sq_geo(region_str)
    sync_group = f"SQ_{campaign_type.value}_{vertical}"

    logger_ctx.info(
        "parsed_sq_legacy",
        campaign_type=campaign_type.value,
        vertical=vertical,
        geo=geo,
    )

    return (
        campaign_type,
        vertical,
        geo,
        sync_group,
        ManagementStrategy.SYNCED,
        "US" in geo,
        0.80,
    )


def _resolve_sq_geo(region_str: str) -> str:
    """Resolve SQ region string to a normalized geo identifier."""
    # Try exact match first
    if region_str in SQ_GEO_MAP:
        return SQ_GEO_MAP[region_str]

    # Try partial match
    for key, value in SQ_GEO_MAP.items():
        if key in region_str:
            return value

    # Extract region from the string
    region_str_clean = region_str.strip()
    if "APJ" in region_str_clean:
        return f"APJ_{region_str_clean.replace('APJ', '').strip()}"
    if "EMEA" in region_str_clean:
        return f"EMEA_{region_str_clean.replace('EMEA', '').strip()}"
    if "NA" in region_str_clean:
        return f"NA_{region_str_clean.replace('NA', '').strip()}"

    return region_str_clean


def _parse_other_format(campaign_name: str, logger_ctx) -> tuple:
    """Fallback parser for campaigns that don't match known patterns.

    Returns a tuple with defaults and low confidence.
    """
    logger_ctx.warning(
        "unparseable_campaign_name",
        message="Campaign name doesn't match expected patterns, using defaults",
    )

    # Try to detect type from keywords in the name
    name_lower = campaign_name.lower()
    if "brand" in name_lower and "nonbrand" not in name_lower:
        campaign_type = CampaignType.BRAND
    elif "competitor" in name_lower:
        campaign_type = CampaignType.COMPETITOR
    elif "enterprise" in name_lower:
        campaign_type = CampaignType.ENTERPRISE
    elif "pmax" in name_lower:
        campaign_type = CampaignType.SHOPPING
    else:
        campaign_type = CampaignType.NON_BRAND

    return (
        campaign_type,
        "unknown",
        "unknown",
        campaign_name,  # Use full name as sync group (unique)
        ManagementStrategy.INDIVIDUAL,
        True,
        0.10,
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
