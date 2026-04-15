"""BigQuery client for reading and writing agent data."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from google.cloud import bigquery

from src.config import settings
from src.models.base import AgentType, EventType

logger = structlog.get_logger(__name__)


class BigQueryClient:
    """Client for BigQuery operations."""

    def __init__(self) -> None:
        """Initialize BigQuery client."""
        self.client = bigquery.Client(project=settings.gcp_project_id)
        self.dataset_raw = settings.bq_dataset_raw
        self.dataset_agents = settings.bq_dataset_agents
        self.logger = logger.bind(component="bigquery_client")

    async def query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of row dictionaries
        """
        self.logger.info("executing_query", query_length=len(sql))

        try:
            job_config = bigquery.QueryJobConfig()
            if params:
                # Convert params to BigQuery format
                job_config.query_parameters = self._convert_params(params)

            query_job = self.client.query(sql, job_config=job_config)
            results = query_job.result()

            rows = [dict(row) for row in results]
            self.logger.info("query_completed", row_count=len(rows))
            return rows

        except Exception as e:
            self.logger.error("query_failed", error=str(e))
            raise

    async def insert_rows(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert rows into a BigQuery table.

        Args:
            table_name: Table name (without dataset prefix)
            rows: List of row dictionaries
        """
        table_id = f"{settings.gcp_project_id}.{self.dataset_agents}.{table_name}"
        self.logger.info("inserting_rows", table=table_name, row_count=len(rows))

        try:
            errors = self.client.insert_rows_json(table_id, rows)
            if errors:
                self.logger.error("insert_errors", errors=errors)
                raise Exception(f"Insert failed: {errors}")

            self.logger.info("rows_inserted", count=len(rows))

        except Exception as e:
            self.logger.error("insert_failed", error=str(e))
            raise

    def _convert_params(
        self, params: dict[str, Any]
    ) -> list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]:
        """Convert Python params to BigQuery format.

        Args:
            params: Python dictionary of parameters

        Returns:
            List of BigQuery query parameters
        """
        bq_params = []
        for key, value in params.items():
            # Handle None values
            if value is None:
                bq_params.append(bigquery.ScalarQueryParameter(key, "STRING", None))
            # Handle arrays (lists)
            elif isinstance(value, list):
                if not value:
                    # Empty array - default to STRING type
                    bq_params.append(bigquery.ArrayQueryParameter(key, "STRING", []))
                else:
                    # Infer type from first element
                    first_elem = value[0]
                    if isinstance(first_elem, bool):
                        array_type = "BOOL"
                    elif isinstance(first_elem, int):
                        array_type = "INT64"
                    elif isinstance(first_elem, float):
                        array_type = "FLOAT64"
                    else:
                        array_type = "STRING"
                    bq_params.append(bigquery.ArrayQueryParameter(key, array_type, value))
            # Handle scalar values
            elif isinstance(value, bool):
                param_type = "BOOL"
                bq_params.append(bigquery.ScalarQueryParameter(key, param_type, value))
            elif isinstance(value, int):
                param_type = "INT64"
                bq_params.append(bigquery.ScalarQueryParameter(key, param_type, value))
            elif isinstance(value, float):
                param_type = "FLOAT64"
                bq_params.append(bigquery.ScalarQueryParameter(key, param_type, value))
            elif isinstance(value, datetime):
                param_type = "TIMESTAMP"
                bq_params.append(bigquery.ScalarQueryParameter(key, param_type, value.isoformat()))
            else:
                param_type = "STRING"
                bq_params.append(bigquery.ScalarQueryParameter(key, param_type, str(value)))

        return bq_params


# Global client instance
_bq_client: BigQueryClient | None = None


def get_client() -> BigQueryClient:
    """Get or create BigQuery client singleton."""
    global _bq_client
    if _bq_client is None:
        _bq_client = BigQueryClient()
    return _bq_client


async def log_audit_event(
    run_id: UUID,
    agent_type: AgentType,
    event_type: EventType,
    details: dict[str, Any],
) -> None:
    """Log an audit event to BigQuery.

    Args:
        run_id: Run identifier
        agent_type: Agent type
        event_type: Event type
        details: Event details
    """
    client = get_client()

    row = {
        "run_id": str(run_id),
        "agent_type": agent_type.value,
        "event_type": event_type.value,
        "timestamp": datetime.utcnow().isoformat(),
        "details": str(details),  # Store as JSON string
    }

    await client.insert_rows("agent_audit_log", [row])
