#!/usr/bin/env python3
"""Seed campaign taxonomy from Google Ads campaigns.

This script fetches all campaigns from Google Ads and auto-detects their taxonomy
(type, vertical, geo, sync groups) based on naming conventions.
"""

import argparse
import asyncio
import sys
from collections import defaultdict

import structlog

from src.config import settings
from src.services.taxonomy import TaxonomyService
from src.utils.taxonomy import parse_campaign_name, validate_taxonomy

logger = structlog.get_logger(__name__)


async def fetch_campaigns_from_google_ads(customer_id: str) -> list[dict]:
    """Fetch all campaigns from Google Ads.

    Args:
        customer_id: Google Ads customer ID

    Returns:
        List of campaign dictionaries with id, name, status
    """
    # TODO: Implement actual Google Ads API call
    # For now, return mock data for testing
    logger.warning(
        "using_mock_data",
        message="Google Ads API integration not yet implemented, using mock data",
    )

    return [
        {"id": "123456", "name": "Brand_US", "status": "ENABLED"},
        {"id": "123457", "name": "Brand_UK", "status": "ENABLED"},
        {"id": "123458", "name": "Brand_DE", "status": "ENABLED"},
        {"id": "234567", "name": "NonBrand_AI-Code_US", "status": "ENABLED"},
        {"id": "234568", "name": "NonBrand_AI-Code_UK", "status": "ENABLED"},
        {"id": "234569", "name": "NonBrand_LLM-Integration_US", "status": "ENABLED"},
        {"id": "345678", "name": "Competitor_GitHub_US", "status": "ENABLED"},
    ]


async def seed_taxonomy(
    customer_id: str,
    brand_exclusions: list[str] | None = None,
    brand_manager: str | None = None,
    dry_run: bool = False,
) -> None:
    """Seed campaign taxonomy table from Google Ads campaigns.

    Args:
        customer_id: Google Ads customer ID
        brand_exclusions: List of agent types to exclude for Brand campaigns
        brand_manager: External manager name for Brand campaigns
        dry_run: If True, only print what would be done
    """
    logger.info(
        "seed_taxonomy_started",
        customer_id=customer_id,
        brand_exclusions=brand_exclusions,
        brand_manager=brand_manager,
        dry_run=dry_run,
    )

    # Set defaults
    if brand_exclusions is None:
        brand_exclusions = ["keyword", "bid_modifier"]
    if brand_manager is None:
        brand_manager = "brand_vendor"

    # Fetch campaigns
    logger.info("fetching_campaigns_from_google_ads")
    campaigns = await fetch_campaigns_from_google_ads(customer_id)
    logger.info("campaigns_fetched", count=len(campaigns))

    if not campaigns:
        logger.warning("no_campaigns_found")
        return

    # Parse each campaign
    taxonomies = []
    validation_errors = []

    for campaign in campaigns:
        taxonomy = parse_campaign_name(
            campaign_id=campaign["id"],
            campaign_name=campaign["name"],
            customer_id=customer_id,
            campaign_status=campaign["status"],
        )

        # Override Brand exclusions if provided
        if taxonomy.campaign_type.value == "brand" and brand_exclusions:
            taxonomy.agent_exclusions = brand_exclusions
            taxonomy.external_manager = brand_manager

        # Validate
        is_valid, errors = validate_taxonomy(taxonomy)
        if not is_valid:
            logger.error(
                "validation_failed",
                campaign_id=taxonomy.campaign_id,
                campaign_name=taxonomy.campaign_name,
                errors=errors,
            )
            validation_errors.extend(errors)
            continue

        taxonomies.append(taxonomy)

        logger.info(
            "taxonomy_parsed",
            campaign_id=taxonomy.campaign_id,
            campaign_name=taxonomy.campaign_name,
            campaign_type=taxonomy.campaign_type.value,
            sync_group=taxonomy.sync_group,
            agent_exclusions=taxonomy.agent_exclusions,
            confidence=taxonomy.detection_confidence,
        )

    if validation_errors:
        logger.error(
            "validation_errors_found",
            error_count=len(validation_errors),
            errors=validation_errors,
        )
        sys.exit(1)

    # Group by sync group for summary
    sync_groups = defaultdict(list)
    for taxonomy in taxonomies:
        sync_groups[taxonomy.sync_group].append(taxonomy)

    logger.info(
        "taxonomy_summary",
        total_campaigns=len(taxonomies),
        sync_groups=len(sync_groups),
        by_type={
            "brand": len([t for t in taxonomies if t.campaign_type.value == "brand"]),
            "non_brand": len([t for t in taxonomies if t.campaign_type.value == "non_brand"]),
            "competitor": len([t for t in taxonomies if t.campaign_type.value == "competitor"]),
        },
    )

    # Print sync group summary
    print("\n=== Sync Group Summary ===")
    for sg, campaigns in sorted(sync_groups.items()):
        geos = [c.geo for c in campaigns]
        template = next((c for c in campaigns if c.is_template), None)
        exclusions = set()
        for c in campaigns:
            exclusions.update(c.agent_exclusions)

        print(f"\n{sg}:")
        print(f"  Type: {campaigns[0].campaign_type.value}")
        print(f"  Strategy: {campaigns[0].management_strategy.value}")
        print(f"  Campaigns: {len(campaigns)} ({', '.join(geos)})")
        print(f"  Template: {template.geo if template else 'none'}")
        if exclusions:
            print(f"  Agent Exclusions: {', '.join(sorted(exclusions))}")
            print(f"  External Manager: {campaigns[0].external_manager}")

    if dry_run:
        print("\n[DRY RUN] Would insert/update the following taxonomies:")
        for taxonomy in taxonomies:
            print(
                f"  - {taxonomy.campaign_name} ({taxonomy.campaign_type.value}, "
                f"sync_group={taxonomy.sync_group}, exclusions={taxonomy.agent_exclusions})"
            )
        return

    # Insert into BigQuery
    print("\n=== Upserting to BigQuery ===")
    taxonomy_service = TaxonomyService()

    for taxonomy in taxonomies:
        try:
            await taxonomy_service.upsert_taxonomy(taxonomy)
            print(f"✓ {taxonomy.campaign_name}")
        except Exception as e:
            logger.error(
                "upsert_failed",
                campaign_id=taxonomy.campaign_id,
                campaign_name=taxonomy.campaign_name,
                error=str(e),
            )
            print(f"✗ {taxonomy.campaign_name}: {e}")

    print(f"\n✓ Successfully seeded {len(taxonomies)} campaign taxonomies")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Seed campaign taxonomy from Google Ads")
    parser.add_argument(
        "--customer-id",
        default=settings.google_ads_customer_id,
        help="Google Ads customer ID (default: from settings)",
    )
    parser.add_argument(
        "--brand-exclusions",
        default="keyword,bid_modifier",
        help="Comma-separated list of agent types to exclude for Brand campaigns (default: keyword,bid_modifier)",
    )
    parser.add_argument(
        "--brand-manager",
        default="brand_vendor",
        help="External manager name for Brand campaigns (default: brand_vendor)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually insert, just show what would be done",
    )

    args = parser.parse_args()

    # Parse brand exclusions
    brand_exclusions = [x.strip() for x in args.brand_exclusions.split(",") if x.strip()]

    # Run async
    asyncio.run(
        seed_taxonomy(
            customer_id=args.customer_id,
            brand_exclusions=brand_exclusions,
            brand_manager=args.brand_manager,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
