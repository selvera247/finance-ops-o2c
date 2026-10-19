from __future__ import annotations

"""BigQuery adapter. Falls back to DuckDB warehouse if BQ client/project unavailable."""

from typing import Any

from data_plane.config import bigquery_dataset, gcp_project


def _client():
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-cloud-bigquery not installed") from exc
    project = gcp_project()
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for BigQuery mode")
    return bigquery.Client(project=project), project


def bq_list_invoices(
    *, customer_id: str | None = None, open_only: bool = False
) -> list[dict[str, Any]]:
    try:
        client, project = _client()
        dataset = bigquery_dataset()
        sql = f"SELECT * FROM `{project}.{dataset}.invoices` WHERE 1=1"
        params = []
        if customer_id:
            sql += " AND customer_id = @customer_id"
            params.append(
                __import__("google.cloud.bigquery", fromlist=["bigquery"]).ScalarQueryParameter(
                    "customer_id", "STRING", customer_id
                )
            )
        if open_only:
            sql += " AND status IN ('open', 'past_due')"
        job_config = None
        if params:
            from google.cloud import bigquery

            job_config = bigquery.QueryJobConfig(query_parameters=params)
        return [dict(row) for row in client.query(sql, job_config=job_config)]
    except Exception:
        # Safe fallback for portfolio demos without live BQ
        from data_plane.warehouse import db

        sql = "SELECT * FROM invoices WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if open_only:
            sql += " AND status IN ('open', 'past_due')"
        return db.query_dicts(sql, params)


def bq_list_payments(
    *, customer_id: str | None = None, unmatched_only: bool = False
) -> list[dict[str, Any]]:
    try:
        client, project = _client()
        dataset = bigquery_dataset()
        sql = f"SELECT * FROM `{project}.{dataset}.payments` WHERE 1=1"
        job_config = None
        if customer_id:
            from google.cloud import bigquery

            sql += " AND customer_id = @customer_id"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id)
                ]
            )
        if unmatched_only:
            sql += " AND status IN ('unmatched', 'partial')"
        return [dict(row) for row in client.query(sql, job_config=job_config)]
    except Exception:
        from data_plane.warehouse import db

        sql = "SELECT * FROM payments WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if unmatched_only:
            sql += " AND status IN ('unmatched', 'partial')"
        return db.query_dicts(sql, params)


def bq_list_contracts(
    *, customer_id: str | None = None, active_only: bool = True
) -> list[dict[str, Any]]:
    try:
        client, project = _client()
        dataset = bigquery_dataset()
        sql = f"SELECT * FROM `{project}.{dataset}.contracts` WHERE 1=1"
        job_config = None
        if customer_id:
            from google.cloud import bigquery

            sql += " AND customer_id = @customer_id"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id)
                ]
            )
        if active_only:
            sql += " AND status = 'active'"
        return [dict(row) for row in client.query(sql, job_config=job_config)]
    except Exception:
        from data_plane.warehouse import db

        sql = "SELECT * FROM contracts WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if active_only:
            sql += " AND status = 'active'"
        return db.query_dicts(sql, params)
