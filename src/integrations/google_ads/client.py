"""Google Ads API client wrapper."""

import time
from typing import Any

import structlog
from google.ads.googleads.client import GoogleAdsClient as GAClient
from google.ads.googleads.errors import GoogleAdsException

from src.config import settings

logger = structlog.get_logger(__name__)


class GoogleAdsClient:
    """Wrapper for Google Ads API client with rate limiting and error handling."""

    def __init__(self) -> None:
        """Initialize Google Ads client."""
        credentials = {
            "developer_token": settings.google_ads_developer_token,
            "client_id": settings.google_ads_client_id,
            "client_secret": settings.google_ads_client_secret,
            "refresh_token": settings.google_ads_refresh_token,
            "login_customer_id": settings.google_ads_login_customer_id,
            "use_proto_plus": True,
        }

        self.client = GAClient.load_from_dict(credentials)
        self.customer_id = settings.google_ads_customer_id
        self.rate_limit = settings.rate_limit_requests_per_second
        self.last_request_time = 0.0
        self.logger = logger.bind(component="google_ads_client")

    async def mutate(
        self,
        operations: list[Any],
        operation_type: str,
        partial_failure: bool = True,
    ) -> dict[str, Any]:
        """Execute mutate operations with rate limiting.

        Args:
            operations: List of operation objects
            operation_type: Type of operation (e.g., "AdGroupOperation")
            partial_failure: Enable partial failure mode

        Returns:
            Mutation results
        """
        self.logger.info(
            "executing_mutate",
            operation_type=operation_type,
            operation_count=len(operations),
        )

        # Enforce rate limiting
        await self._rate_limit()

        try:
            service_name = self._get_service_name(operation_type)
            service = self.client.get_service(service_name)

            # Chunk operations to avoid exceeding API limits
            chunk_size = 5000
            all_results = []

            for i in range(0, len(operations), chunk_size):
                chunk = operations[i : i + chunk_size]
                self.logger.info("mutating_chunk", chunk_size=len(chunk))

                response = service.mutate(
                    customer_id=self.customer_id,
                    operations=chunk,
                    partial_failure=partial_failure,
                )

                all_results.extend(response.results)

                # Rate limit between chunks
                if i + chunk_size < len(operations):
                    await self._rate_limit()

            self.logger.info("mutate_completed", result_count=len(all_results))

            return {
                "success": True,
                "results": all_results,
                "total_operations": len(operations),
            }

        except GoogleAdsException as ex:
            self.logger.error(
                "google_ads_error",
                error=ex.error.code().name,
                message=ex.error.message,
            )
            raise

        except Exception as e:
            self.logger.error("mutate_failed", error=str(e))
            raise

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        time_since_last = now - self.last_request_time
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_service_name(self, operation_type: str) -> str:
        """Map operation type to service name.

        Args:
            operation_type: Operation type (e.g., "AdGroupOperation")

        Returns:
            Service name
        """
        # Map operation types to services
        service_map = {
            "AdGroupOperation": "AdGroupService",
            "AdGroupAdOperation": "AdGroupAdService",
            "AdGroupCriterionOperation": "AdGroupCriterionService",
            "CampaignCriterionOperation": "CampaignCriterionService",
            "CampaignBidModifierOperation": "CampaignBidModifierService",
        }

        return service_map.get(operation_type, operation_type.replace("Operation", "Service"))


# Global client instance
_ads_client: GoogleAdsClient | None = None


def get_client() -> GoogleAdsClient:
    """Get or create Google Ads client singleton."""
    global _ads_client
    if _ads_client is None:
        _ads_client = GoogleAdsClient()
    return _ads_client
