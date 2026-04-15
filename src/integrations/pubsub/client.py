"""Pub/Sub client for inter-agent messaging."""

import json
from typing import Any

import structlog
from google.cloud import pubsub_v1

from src.config import settings

logger = structlog.get_logger(__name__)


class PubSubClient:
    """Client for Google Cloud Pub/Sub."""

    def __init__(self) -> None:
        """Initialize Pub/Sub client."""
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.project_id = settings.gcp_project_id
        self.logger = logger.bind(component="pubsub_client")

    async def publish(
        self,
        topic_name: str,
        message: dict[str, Any],
    ) -> str:
        """Publish a message to a topic.

        Args:
            topic_name: Topic name (without project prefix)
            message: Message payload

        Returns:
            Message ID
        """
        topic_path = self.publisher.topic_path(self.project_id, topic_name)

        self.logger.info("publishing_message", topic=topic_name)

        try:
            # Convert message to JSON bytes
            data = json.dumps(message).encode("utf-8")

            # Publish message
            future = self.publisher.publish(topic_path, data)
            message_id = future.result()

            self.logger.info("message_published", message_id=message_id)
            return message_id

        except Exception as e:
            self.logger.error("publish_failed", error=str(e))
            raise


# Global client instance
_pubsub_client: PubSubClient | None = None


def get_client() -> PubSubClient:
    """Get or create Pub/Sub client singleton."""
    global _pubsub_client
    if _pubsub_client is None:
        _pubsub_client = PubSubClient()
    return _pubsub_client


async def publish_message(topic: str, message: dict[str, Any]) -> str:
    """Publish a message to a Pub/Sub topic.

    Args:
        topic: Topic name
        message: Message payload

    Returns:
        Message ID
    """
    client = get_client()
    return await client.publish(topic, message)


async def subscribe_to_topic(topic: str, subscription: str) -> None:
    """Subscribe to a Pub/Sub topic.

    Args:
        topic: Topic name
        subscription: Subscription name
    """
    # TODO: Implement subscription handling
    logger.info("subscribing_to_topic", topic=topic, subscription=subscription)
