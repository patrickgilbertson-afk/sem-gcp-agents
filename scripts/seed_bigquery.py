#!/usr/bin/env python3
"""Seed BigQuery with initial configuration data."""

import asyncio
from datetime import datetime

from src.config import settings
from src.integrations.bigquery.client import get_client


async def seed_brand_guidelines():
    """Seed initial brand guidelines."""
    client = get_client()

    guidelines = [
        {
            "customer_id": settings.google_ads_customer_id,
            "brand_voice": "Professional, helpful, and data-driven. Focus on ROI and performance.",
            "prohibited_terms": ["cheap", "free", "click here", "amazing deal"],
            "required_phrases": [],
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": "system",
        }
    ]

    await client.insert_rows("brand_guidelines", guidelines)
    print("✓ Brand guidelines seeded")


async def seed_agent_config():
    """Seed initial agent configuration."""
    client = get_client()

    configs = [
        {
            "agent_type": "campaign_health",
            "config_key": "min_quality_score",
            "config_value": "5",
            "description": "Minimum acceptable quality score",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "agent_type": "campaign_health",
            "config_key": "min_ctr_threshold",
            "config_value": "0.01",
            "description": "Minimum acceptable CTR (1%)",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "agent_type": "campaign_health",
            "config_key": "zero_conversion_spend_threshold",
            "config_value": "50",
            "description": "Dollar threshold for zero conversion alert",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "agent_type": "keyword",
            "config_key": "min_clicks_for_negative",
            "config_value": "10",
            "description": "Minimum clicks before considering negative keyword",
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "agent_type": "bid_modifier",
            "config_key": "min_clicks_segment",
            "config_value": "100",
            "description": "Minimum clicks required per segment for analysis",
            "updated_at": datetime.utcnow().isoformat(),
        },
    ]

    await client.insert_rows("agent_config", configs)
    print("✓ Agent config seeded")


async def main():
    """Run all seed operations."""
    print("Seeding BigQuery with initial data...")

    try:
        await seed_brand_guidelines()
        await seed_agent_config()
        print("\n✓ All data seeded successfully")
    except Exception as e:
        print(f"\n✗ Error seeding data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
