import ast
import json
import logging

import boto3
import mysql.connector
import pandas as pd

from app.core.config import settings
from app.repositories.excel_push_repo import ExcelPushRepository

logger = logging.getLogger(__name__)


class ExcelPushService:
    """
    Background service that:
      1. Queries the sinterface DB for unanalysed call records matching the user's config.
      2. Fetches cluster data (product hierarchy, reasons) from the AI DB.
      3. Merges both datasets.
      4. Pushes SQS messages in batches of 10 (Vodafone vs General queues).
    All progress is written back to excel_push_jobs via ExcelPushRepository.
    """

    VODAFONE_OUTLET_ID = 127902
    BATCH_SIZE = 10

    # ------------------------------------------------------------------ helpers

    def _get_sqs_client(self):
        return boto3.client(
            "sqs",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name="ap-south-1",
        )

    def _get_source_conn(self):
        """Connection to the live sinterface DB (call logs)."""
        return mysql.connector.connect(
            host=settings.SOURCE_DB_HOST,
            user=settings.SOURCE_DB_USER,
            password=settings.SOURCE_DB_PASSWORD,
            database=settings.SOURCE_DB_NAME,
        )

    def _get_cluster_conn(self):
        """Connection to the AI DB (product clusters / reason tables)."""
        return mysql.connector.connect(
            host=settings.CLUSTER_DB_HOST,
            user=settings.CLUSTER_DB_USER,
            password=settings.CLUSTER_DB_PASSWORD,
            database=settings.CLUSTER_DB_NAME,
        )

    def _update(self, job_id: int, **kwargs):
        ExcelPushRepository.update_job(job_id, **kwargs)

    # -------------------------------------------------------- stage 1: fetch

    def fetch_call_records(self, config: dict) -> list:
        """
        Fetch unanalysed call records from sinterface matching the form config.
        Filters applied (all optional except master_outlet_id):
          - outlet_ids  : comma-separated list → c.outlet_id IN (...)
          - state       : o.state = ?
          - city        : o.city  = ?
          - from_date   : c.call_date_time >= ? 00:00:00
          - to_date     : c.call_date_time <= ? 23:59:59
          - num_records : LIMIT
        Only records NOT yet in call_recording_analytics_details (a.id IS NULL) are returned.
        """
        conn = self._get_source_conn()
        cursor = conn.cursor(dictionary=True)

        conditions = [
            "c.call_recording_url != ''",
            "c.call_recording_url IS NOT NULL",
            "LOWER(c.call_status) = 'connected'",
            "a.id IS NULL",           # not yet processed
        ]
        values = []

        # master_outlet_id is always required
        conditions.append("c.master_outlet_id = %s")
        values.append(str(config["master_outlet_id"]).strip())

        # outlet_ids — comma-separated from tag input
        if config.get("outlet_ids"):
            oids = [o.strip() for o in str(config["outlet_ids"]).split(",") if o.strip()]
            if oids:
                ph = ",".join(["%s"] * len(oids))
                conditions.append(f"c.outlet_id IN ({ph})")
                values.extend(oids)

        # state / city — join is on outlets table
        if config.get("state"):
            conditions.append("o.state = %s")
            values.append(config["state"])

        if config.get("city"):
            conditions.append("o.city = %s")
            values.append(config["city"])

        # date range
        if config.get("from_date"):
            conditions.append("c.call_date_time >= %s")
            values.append(f"{config['from_date']} 00:00:00")

        if config.get("to_date"):
            conditions.append("c.call_date_time <= %s")
            values.append(f"{config['to_date']} 23:59:59")

        limit = int(config.get("num_records") or 200000)

        query = f"""
            SELECT
                c.id,
                c.master_outlet_id,
                c.outlet_id,
                c.call_recording_url,
                o.state
            FROM customer_call_record_logs c
            LEFT JOIN call_recording_analytics_details a
                   ON c.id = a.customer_call_record_id
            JOIN  outlets o
                   ON c.outlet_id = o.id
            WHERE {' AND '.join(conditions)}
            ORDER BY c.call_date_time DESC
            LIMIT {limit}
        """

        cursor.execute(query, tuple(values))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info("fetch_call_records: %d rows for master_outlet_id=%s", len(results), config["master_outlet_id"])
        return results

    # -------------------------------------------------------- stage 2: clusters

    def fetch_clusters_bulk(self, master_outlet_ids: list) -> pd.DataFrame:
        """
        Pull product hierarchy + reason lists from the AI DB for each
        master_outlet_id and reconstruct the flat structure expected by SQS.
        """
        if not master_outlet_ids:
            return pd.DataFrame()

        conn = self._get_cluster_conn()
        cursor = conn.cursor(dictionary=True)
        fmt = ",".join(["%s"] * len(master_outlet_ids))
        ids = tuple(master_outlet_ids)

        cursor.execute(
            f"SELECT master_outlet_id, category, product_name FROM product_hierarchy WHERE master_outlet_id IN ({fmt})", ids
        )
        product_rows = cursor.fetchall()

        cursor.execute(
            f"SELECT master_outlet_id, reason FROM complaint_reasons WHERE master_outlet_id IN ({fmt})", ids
        )
        complaint_rows = cursor.fetchall()

        cursor.execute(
            f"SELECT master_outlet_id, reason FROM enquiry_reasons WHERE master_outlet_id IN ({fmt})", ids
        )
        enquiry_rows = cursor.fetchall()

        cursor.execute(
            f"SELECT master_outlet_id, reason FROM request_reasons WHERE master_outlet_id IN ({fmt})", ids
        )
        request_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        data = {
            int(oid): {
                "master_outlet_id": int(oid),
                "product_heirarchy_list": {},
                "complaint_reasons": [],
                "enquiry_reasons": [],
                "request_reasons": [],
                "brand_name": None,
            }
            for oid in master_outlet_ids
        }

        for row in product_rows:
            oid = int(row["master_outlet_id"])
            if oid in data:
                data[oid]["product_heirarchy_list"].setdefault(row["category"], []).append(row["product_name"])

        for row in complaint_rows:
            oid = int(row["master_outlet_id"])
            if oid in data:
                data[oid]["complaint_reasons"].append(row["reason"])

        for row in enquiry_rows:
            oid = int(row["master_outlet_id"])
            if oid in data:
                data[oid]["enquiry_reasons"].append(row["reason"])

        for row in request_rows:
            oid = int(row["master_outlet_id"])
            if oid in data:
                data[oid]["request_reasons"].append(row["reason"])

        logger.info("fetch_clusters_bulk: fetched cluster data for %d outlet(s)", len(master_outlet_ids))
        return pd.DataFrame(list(data.values()))

    # -------------------------------------------------------- stage 3: SQS push

    @staticmethod
    def _safe_parse(val):
        """Parse string-encoded lists/dicts back to Python objects."""
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str) and val:
            try:
                return ast.literal_eval(val)
            except Exception:
                return val
        return val

    def _build_message(self, row: dict) -> dict:
        msg = {
            "call_log_id":          int(row["id"]),
            "call_recording_url":   row["call_recording_url"],
            "master_outlet_id":     int(row["master_outlet_id"]),
            "outlet_id":            int(row["outlet_id"]),
            "brand_name":           row.get("brand_name"),
            "product_heirarchy_list": self._safe_parse(row.get("product_heirarchy_list")),
            "request_reasons":      self._safe_parse(row.get("request_reasons")),
            "enquiry_reasons":      self._safe_parse(row.get("enquiry_reasons")),
            "complaint_reasons":    self._safe_parse(row.get("complaint_reasons")),
        }
        if row.get("state") is not None:
            msg["state"] = row["state"]
        return msg

    def push_to_sqs(self, final_df: pd.DataFrame, job_id: int) -> int:
        """
        Send all rows in final_df to SQS in batches of 10.
        Vodafone records (master_outlet_id == 127902) go to the Vodafone queue;
        everything else goes to the general queue.
        Updates pushed_records count after every flushed batch.
        """
        sqs = self._get_sqs_client()
        pushed = 0

        def flush_batch(queue_url: str, batch: list):
            nonlocal pushed
            if not batch:
                return
            sqs.send_message_batch(QueueUrl=queue_url, Entries=batch)
            pushed += len(batch)
            self._update(job_id, pushed_records=pushed)

        voda_df = final_df[final_df["master_outlet_id"] == self.VODAFONE_OUTLET_ID]
        rest_df  = final_df[final_df["master_outlet_id"] != self.VODAFONE_OUTLET_ID]

        # --- Vodafone queue
        batch = []
        for _, row in voda_df.iterrows():
            batch.append({"Id": str(len(batch)), "MessageBody": json.dumps(self._build_message(row.to_dict()))})
            if len(batch) == self.BATCH_SIZE:
                flush_batch(settings.SQS_QUEUE_VODA, batch)
                batch = []
        flush_batch(settings.SQS_QUEUE_VODA, batch)

        # --- General queue
        batch = []
        for _, row in rest_df.iterrows():
            batch.append({"Id": str(len(batch)), "MessageBody": json.dumps(self._build_message(row.to_dict()))})
            if len(batch) == self.BATCH_SIZE:
                flush_batch(settings.SQS_QUEUE_GENERAL, batch)
                batch = []
        flush_batch(settings.SQS_QUEUE_GENERAL, batch)

        logger.info("push_to_sqs: pushed %d messages for job %d", pushed, job_id)
        return pushed

    # ---------------------------------------------------- main orchestrator

    def run_push_job(self, job_id: int, config: dict):
        """
        Entry point called by FastAPI BackgroundTasks.
        Runs the full pipeline and updates the job row at every stage.
        """
        try:
            # Stage 1 — fetch records
            self._update(job_id, status="running", stage="Connecting & fetching call records...")
            records = self.fetch_call_records(config)

            if not records:
                self._update(
                    job_id,
                    status="completed",
                    stage="Done — no unanalysed records found for this configuration",
                    total_records=0,
                    pushed_records=0,
                )
                return

            total = len(records)
            self._update(
                job_id,
                total_records=total,
                stage=f"Fetched {total:,} records. Loading cluster data...",
            )

            # Stage 2 — cluster data
            df_logs = pd.DataFrame(records)
            df_logs["master_outlet_id"] = df_logs["master_outlet_id"].astype(int)
            unique_ids = df_logs["master_outlet_id"].unique().tolist()
            df_clusters = self.fetch_clusters_bulk(unique_ids)

            # Stage 3 — merge
            self._update(job_id, stage="Merging call records with cluster data...")
            if not df_clusters.empty:
                df_clusters["master_outlet_id"] = df_clusters["master_outlet_id"].astype(int)
                final_df = df_logs.merge(df_clusters, on="master_outlet_id", how="left")
            else:
                final_df = df_logs

            # Stage 4 — push to SQS
            self._update(job_id, stage="Pushing messages to SQS...")
            pushed = self.push_to_sqs(final_df, job_id)

            self._update(
                job_id,
                status="completed",
                stage=f"Completed - {pushed:,} messages pushed to SQS",
                pushed_records=pushed,
            )

        except Exception as exc:
            logger.exception("Excel push job %d failed: %s", job_id, exc)
            self._update(job_id, status="failed", stage="Failed", error_message=str(exc))
