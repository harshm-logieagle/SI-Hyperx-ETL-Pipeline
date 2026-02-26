"""
ETL Pipeline for Customer Call Recordings
Raw Query:
INSERT INTO customer_call_recordings (
    master_outlet_id, outlet_id, call_record_raw_id,
    caller_number, called_number, agent_number,
    call_date, call_time, call_date_time, call_start_time, call_end_time,
    call_duration, total_durations, call_status, call_uuid, call_recording_url,
    publisher_type, request_variable, response_variable, Branch, CustomerType,
    answerd_by, modified, ivr_type, waybeo_unique_call_id, called_client_store_id,
    waybeo_callid, answered_by, ivr_duration, ring_duration, lead_send_to_crm,
    call_type, transfer_status, destination_number, count_of_sale_query,
    count_of_service_query, is_new_customer, dealer_code, dealer_type,
    virtual_number, locality, am, rsm, city, state, hangup_leg, key_press,
    call_record_language, call_language_api_response, is_caller_notified
)
SELECT
    o.master_outlet_id, o.id, raw.id,
    raw.caller_number, raw.called_number, raw.agent_number,
    raw.call_date, raw.call_time, raw.call_date_time, raw.call_start_time, raw.call_end_time,
    raw.call_duration, raw.total_durations, raw.call_status, raw.call_uuid, raw.call_recording_url,
    raw.publisher_type, raw.request_variable, raw.response_variable, raw.Branch, raw.CustomerType,
    raw.answerd_by, raw.modified, raw.ivr_type, raw.waybeo_unique_call_id, raw.called_client_store_id,
    raw.waybeo_callid, raw.answered_by, raw.ivr_duration, raw.ring_duration, raw.lead_send_to_crm,
    raw.call_type, raw.transfer_status, raw.destination_number, raw.count_of_sale_query,
    raw.count_of_service_query, raw.is_new_customer, raw.dealer_code, raw.dealer_type,
    raw.virtual_number, raw.locality, raw.am, raw.rsm, raw.city, raw.state, raw.hangup_leg, raw.key_press,
    raw.call_record_language, raw.call_language_api_response, raw.is_caller_notified
FROM customer_call_record_logs raw
JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
WHERE raw.id > :last_id
  AND NOT EXISTS (
      SELECT 1 FROM customer_call_recordings c WHERE c.call_record_raw_id = raw.id
  )
ORDER BY raw.id
LIMIT :batch_size;
"""

import mysql.connector
from mysql.connector import Error, OperationalError, DatabaseError, InterfaceError
import logging
import time
import sys
from contextlib import contextmanager


# ─────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_customer_call_recordings.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CUSTOMER_CALL_RECORDINGS")


# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "10.0.4.194",
    "port": 4000,
    "user": "ai-team",
    "password": r"Zx4%shaU67&1@3slftyst",
    "database": "test_singleinterface_hyperx",
    "autocommit": False,
    "use_pure": True,
    "connection_timeout": 30,
}

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2

SOURCE_TABLE = "customer_call_record_logs"
TARGET_TABLE = "customer_call_recordings"

INSERT_QUERY = """
    INSERT INTO customer_call_recordings (
        master_outlet_id, outlet_id, call_record_raw_id,
        caller_number, called_number, agent_number,
        call_date, call_time, call_date_time, call_start_time, call_end_time,
        call_duration, total_durations, call_status, call_uuid, call_recording_url,
        publisher_type, request_variable, response_variable, Branch, CustomerType,
        answerd_by, modified, ivr_type, waybeo_unique_call_id, called_client_store_id,
        waybeo_callid, answered_by, ivr_duration, ring_duration, lead_send_to_crm,
        call_type, transfer_status, destination_number, count_of_sale_query,
        count_of_service_query, is_new_customer, dealer_code, dealer_type,
        virtual_number, locality, am, rsm, city, state, hangup_leg, key_press,
        call_record_language, call_language_api_response, is_caller_notified
    )
    SELECT
        o.master_outlet_id, o.id, raw.id,
        raw.caller_number, raw.called_number, raw.agent_number,
        raw.call_date, raw.call_time, raw.call_date_time, raw.call_start_time, raw.call_end_time,
        raw.call_duration, raw.total_durations, raw.call_status, raw.call_uuid, raw.call_recording_url,
        raw.publisher_type, raw.request_variable, raw.response_variable, raw.Branch, raw.CustomerType,
        raw.answerd_by, raw.modified, raw.ivr_type, raw.waybeo_unique_call_id, raw.called_client_store_id,
        raw.waybeo_callid, raw.answered_by, raw.ivr_duration, raw.ring_duration, raw.lead_send_to_crm,
        raw.call_type, raw.transfer_status, raw.destination_number, raw.count_of_sale_query,
        raw.count_of_service_query, raw.is_new_customer, raw.dealer_code, raw.dealer_type,
        raw.virtual_number, raw.locality, raw.am, raw.rsm, raw.city, raw.state, raw.hangup_leg, raw.key_press,
        raw.call_record_language, raw.call_language_api_response, raw.is_caller_notified
    FROM customer_call_record_logs raw
    JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
    WHERE raw.id > %s
      AND NOT EXISTS (
          SELECT 1 FROM customer_call_recordings c WHERE c.call_record_raw_id = raw.id
      )
    ORDER BY raw.id
    LIMIT %s
"""


# ─────────────────────────────────────────────────────────
# Connection Context Manager
# ─────────────────────────────────────────────────────────
@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        logger.info("Database connection established.")
        yield conn
    except Error as e:
        logger.critical(f"Failed to establish DB connection: {e}")
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()
            logger.info("Database connection closed.")


# ─────────────────────────────────────────────────────────
# Checkpoint Helpers
# ─────────────────────────────────────────────────────────
def load_checkpoint(cursor, source_table: str, target_table: str) -> int:
    """
    Returns last_processed_id_raw (raw source id) from etl_checkpoints.
    Pagination is ID-keyed (WHERE raw.id > last_id), so last_processed_id_raw
    tracks the highest raw.id committed in the previous run.
    """
    cursor.execute(
        """
        SELECT last_processed_id_raw
        FROM   etl_checkpoints
        WHERE  source_table_name = %s
          AND  target_table_name = %s
        """,
        (source_table, target_table),
    )
    row = cursor.fetchone()
    if row:
        logger.info(
            f"Checkpoint found -- "
            f"customer_call_record_logs.id (last_processed_id_raw) = {row[0]}"
        )
        return row[0]
    logger.info("No checkpoint found -- starting fresh.")
    return 0


# ─────────────────────────────────────────────────────────
# Core ETL Helpers
# ─────────────────────────────────────────────────────────
def get_total_count(cursor, last_raw_id: int) -> int:
    """Counts pending source rows beyond the last checkpoint id."""
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM customer_call_record_logs raw
        JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
        WHERE raw.id > %s
          AND NOT EXISTS (
              SELECT 1 FROM customer_call_recordings c WHERE c.call_record_raw_id = raw.id
          )
        """,
        (last_raw_id,),
    )
    return cursor.fetchone()[0]


def insert_batch_with_checkpoint(
    conn,
    last_raw_id: int,
    batch_num: int,
    source_table: str,
    target_table: str,
) -> tuple[int, int]:
    """
    Single atomic transaction:
      1. INSERT … SELECT the next BATCH_SIZE rows from customer_call_record_logs
      2. SELECT MAX(call_record_raw_id) for accurate last_processed_id_raw (TiDB-safe)
      3. Upsert etl_checkpoints — last_processed_id_raw tracks highest source id committed
      4. Commit all atomically
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: INSERT … SELECT next batch ────────────
        cursor.execute(INSERT_QUERY, (last_raw_id, BATCH_SIZE))
        rows_inserted = cursor.rowcount

        # ── Step 2: Get actual last raw id (TiDB-safe) ────
        cursor.execute(
            "SELECT IFNULL(MAX(call_record_raw_id), %s) FROM customer_call_recordings",
            (last_raw_id,),
        )
        result      = cursor.fetchone()[0]
        last_ccr_id = result if result is not None else last_raw_id

        # ── Step 3: Get last target id for checkpoint ─────
        cursor.execute("SELECT MAX(id) FROM customer_call_recordings")
        target_max  = cursor.fetchone()[0] or 0

        # ── Step 4: Upsert checkpoint (same transaction) ──
        cursor.execute(
            """
            INSERT INTO etl_checkpoints
                (source_table_name, target_table_name,
                 last_processed_id, last_processed_id_raw)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_processed_id     = VALUES(last_processed_id),
                last_processed_id_raw = VALUES(last_processed_id_raw)
            """,
            (source_table, target_table, target_max, last_ccr_id),
        )

        # ── Step 5: Commit all atomically ─────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Inserted {rows_inserted} | "
            f"customer_call_record_logs.id (last_processed_id_raw) -> {last_ccr_id}"
        )
        return rows_inserted, last_ccr_id

    except Error as e:
        conn.rollback()
        logger.error(
            f"Batch {batch_num:04d} | "
            f"[FAIL] Transaction rolled back. Error: {e}"
        )
        raise
    finally:
        cursor.close()


# ─────────────────────────────────────────────────────────
# Main ETL Runner
# ─────────────────────────────────────────────────────────
def run_etl():
    logger.info("=" * 65)
    logger.info(f"ETL PIPELINE STARTED : {SOURCE_TABLE} -> {TARGET_TABLE}")
    logger.info("=" * 65)

    total_inserted = 0
    total_failed   = 0
    batch_num      = 0

    try:
        with get_db_connection() as conn:

            # buffered=True — prevents "Unread result found" on cursor.close()
            with conn.cursor(buffered=True) as cur:
                last_raw_id = load_checkpoint(cur, SOURCE_TABLE, TARGET_TABLE)

            with conn.cursor(buffered=True) as cur:
                total_records = get_total_count(cur, last_raw_id)

            logger.info(f"Pending source rows to process : {total_records}")

            if total_records == 0:
                logger.warning("No records found. ETL exiting.")
                return

            processed = 0

            while True:
                batch_num += 1
                attempt         = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        inserted, last_raw_id = insert_batch_with_checkpoint(
                            conn, last_raw_id, batch_num,
                            SOURCE_TABLE, TARGET_TABLE,
                        )

                        if inserted == 0:
                            # No more eligible rows for this batch
                            batch_succeeded = True
                            break

                        total_inserted += inserted
                        processed      += inserted

                        progress = min((processed / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {processed}/{total_records} "
                            f"({progress:.1f}%) | "
                            f"Total Inserted : {total_inserted}"
                        )
                        batch_succeeded = True
                        break

                    except OperationalError as e:
                        logger.warning(
                            f"Batch {batch_num:04d} | OperationalError "
                            f"(attempt {attempt}/{MAX_RETRIES}): {e}"
                        )
                        if attempt < MAX_RETRIES:
                            sleep_time = RETRY_BACKOFF ** attempt
                            logger.info(f"Retrying in {sleep_time}s ...")
                            time.sleep(sleep_time)
                            if not conn.is_connected():
                                conn.reconnect(attempts=3, delay=2)
                                logger.info("Reconnected to TiDB.")
                        else:
                            total_failed += BATCH_SIZE
                            logger.error(
                                f"Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts."
                            )

                    except DatabaseError as e:
                        total_failed += BATCH_SIZE
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping batch."
                        )
                        batch_succeeded = True  # Advance past poisoned batch
                        break

                # No rows returned — all done
                if batch_succeeded and total_inserted > 0 and inserted == 0:
                    logger.info("No more records to process. Exiting loop.")
                    break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    logger.error(f"Batch {batch_num:04d} | Advancing past unrecoverable batch.")

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(
            "ETL interrupted by user (Ctrl+C). "
            "Last committed checkpoint is safe -- re-run to resume."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("ETL PIPELINE COMPLETED")
    logger.info(f"  Total Batches  : {batch_num}")
    logger.info(f"  Total Inserted : {total_inserted}")
    logger.info(f"  Total Failed   : {total_failed}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_etl()