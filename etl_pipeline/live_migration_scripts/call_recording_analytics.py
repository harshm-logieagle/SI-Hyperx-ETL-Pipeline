"""
ETL Pipeline for Call Recording Analytics
Raw Query:
INSERT INTO call_recording_analytics (
    call_recording_id, 
    master_outlet_id, 
    outlet_id, 
    is_webhook, 
    analytic_type,
    text_status, 
    reason, 
    reason_verbatim,
    audio_to_text, 
    reason_type,
    end_of_call_status,
    call_language, 
    customer_gender, 
    customer_type, 
    overall_sentiment,
    summary, 
    is_valid_transcript, 
    transcript, 
    emotions,
    emotion_verbatims,
    emotions_json,
    products, 
    product_sentiments,
    product_verbatims,
    product_tags,
    product_categories,
    products_mentioned_json,
    l0_reason, 
    l1_reason, 
    l2_reason, 
    l3_reason, 
    brand_sentiment,
    created,
    modified
)
SELECT 
    ccr.id,
    ccr.master_outlet_id,
    ccr.outlet_id,
    raw.is_webhook, raw.analytic_type,
    raw.text_status, raw.reason, raw.reason_verbatim,
    raw.audio_to_text, raw.reason_type,
    raw.end_of_call_status,
    raw.call_language, raw.customer_gender, raw.customer_type, raw.overall_sentiment,
    raw.summary, raw.is_valid_transcript, raw.transcript, 
    raw.emotions, raw.emotion_verbatims, raw.emotions_json,
    raw.products, raw.product_sentiments, raw.product_verbatims, raw.product_tags,
    raw.product_categories, raw.products_mentioned_json,
    raw.l0_reason, raw.l1_reason, raw.l2_reason, raw.l3_reason, raw.brand_sentiment,
    raw.created, raw.modified
FROM call_recording_analytics_details raw
JOIN customer_call_recordings ccr ON raw.customer_call_record_id = ccr.call_record_raw_id;
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
        logging.FileHandler("etl_call_recording_analytics.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CALL_RECORDING_ANALYTICS")


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

SOURCE_TABLE = "call_recording_analytics_details"
TARGET_TABLE = "call_recording_analytics"

# INSERT IGNORE — silently skips duplicate call_recording_id conflicts on re-runs
INSERT_QUERY = """
    INSERT IGNORE INTO call_recording_analytics (
        call_recording_id,
        master_outlet_id,
        outlet_id,
        is_webhook,
        analytic_type,
        text_status,
        reason,
        reason_verbatim,
        audio_to_text,
        reason_type,
        end_of_call_status,
        call_language,
        customer_gender,
        customer_type,
        overall_sentiment,
        summary,
        is_valid_transcript,
        transcript,
        emotions,
        emotion_verbatims,
        emotions_json,
        products,
        product_sentiments,
        product_verbatims,
        product_tags,
        product_categories,
        products_mentioned_json,
        l0_reason,
        l1_reason,
        l2_reason,
        l3_reason,
        brand_sentiment,
        created,
        modified
    )
    VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s
    )
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
    Returns last_processed_id_raw for keyset pagination.
    Upsert logic:
      - If no checkpoint row exists for (source_table, target_table),
        inserts a fresh row with last_processed_id = 0 and
        last_processed_id_raw = 0 so subsequent saves always UPDATE.
      - If the row already exists, returns the saved last_processed_id_raw
        so the ETL resumes from where it left off.
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

    if row is not None:
        # ── Entry found: resume from the saved position ───────────────
        logger.info(
            f"Checkpoint found -- "
            f"call_recording_analytics_details.customer_call_record_id "
            f"(last_processed_id_raw) = {row[0]}"
        )
        return row[0]

    # ── Entry not found: insert a fresh checkpoint row (start from 0) ─
    logger.info("No checkpoint found -- inserting initial checkpoint and starting fresh.")
    cursor.execute(
        """
        INSERT INTO etl_checkpoints
            (source_table_name, target_table_name,
             last_processed_id, last_processed_id_raw)
        VALUES (%s, %s, %s, %s)
        """,
        (source_table, target_table, 0, 0),
    )
    return 0


# ─────────────────────────────────────────────────────────
# Core ETL Helpers
# ─────────────────────────────────────────────────────────
def get_total_count(cursor, last_processed_id_raw: int) -> int:
    """
    Counts total rows remaining in the source JOIN
    from last_processed_id_raw onwards, so progress % reflects
    actual work left in this run.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM call_recording_analytics_details raw
        JOIN customer_call_recordings ccr
          ON raw.customer_call_record_id = ccr.call_record_raw_id
        WHERE raw.customer_call_record_id > %s
        """,
        (last_processed_id_raw,),
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, last_id: int, batch_size: int) -> list:
    """
    Keyset pagination on raw.customer_call_record_id.
    Fetches the next batch of rows with customer_call_record_id > last_id,
    ordered ascending so the checkpoint always moves forward.
    Columns returned match INSERT_QUERY column order exactly.
    """
    cursor.execute(
        """
        SELECT
            ccr.id,
            ccr.master_outlet_id,
            ccr.outlet_id,
            raw.is_webhook,
            raw.analytic_type,
            raw.text_status,
            raw.reason,
            raw.reason_verbatim,
            raw.audio_to_text,
            raw.reason_type,
            raw.end_of_call_status,
            raw.call_language,
            raw.customer_gender,
            raw.customer_type,
            raw.overall_sentiment,
            raw.summary,
            raw.is_valid_transcript,
            raw.transcript,
            raw.emotions,
            raw.emotion_verbatims,
            raw.emotions_json,
            raw.products,
            raw.product_sentiments,
            raw.product_verbatims,
            raw.product_tags,
            raw.product_categories,
            raw.products_mentioned_json,
            raw.l0_reason,
            raw.l1_reason,
            raw.l2_reason,
            raw.l3_reason,
            raw.brand_sentiment,
            raw.created,
            raw.modified,
            raw.customer_call_record_id
        FROM (
            SELECT customer_call_record_id
            FROM call_recording_analytics_details
            WHERE customer_call_record_id > %s
            ORDER BY customer_call_record_id ASC
            LIMIT %s
        ) ids
        JOIN call_recording_analytics_details raw
          ON raw.customer_call_record_id = ids.customer_call_record_id
        JOIN customer_call_recordings ccr
          ON ccr.call_record_raw_id = ids.customer_call_record_id
        ORDER BY ids.customer_call_record_id ASC
        """,
        (last_id, batch_size),
    )
    return cursor.fetchall()


def insert_batch_with_checkpoint(
    conn,
    rows: list,
    batch_num: int,
    source_table: str,
    target_table: str,
) -> tuple[int, int]:
    """
    Single atomic transaction:
      1. Bulk INSERT IGNORE into call_recording_analytics
         (rows[:34] are the 34 data columns; rows[34] is customer_call_record_id
          used only for checkpoint — stripped before insert)
      2. SELECT MAX(id) for accurate last_processed_id (TiDB-safe)
      3. Upsert etl_checkpoints — tracks both last_processed_id
         and last_processed_id_raw (max customer_call_record_id in this batch)
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Strip the trailing keyset column before INSERT ────
        # Each row = (34 data cols, customer_call_record_id)
        # customer_call_record_id is fetched for checkpoint tracking only.
        data_rows = [row[:34] for row in rows]
        last_raw_id = rows[-1][34]  # max customer_call_record_id in this batch

        # ── Step 2: Bulk INSERT IGNORE ────────────────────────────────
        cursor.executemany(INSERT_QUERY, data_rows)
        rows_inserted = cursor.rowcount

        # ── Step 3: Get actual last target ID (TiDB-safe) ─────────────
        cursor.execute("SELECT MAX(id) FROM call_recording_analytics")
        result     = cursor.fetchone()[0]
        last_cra_id = result if result is not None else 0

        # ── Step 4: Update checkpoint (row is guaranteed to exist after
        #           load_checkpoint inserted it at startup) ─────────────
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
            (source_table, target_table, last_cra_id, last_raw_id),
        )

        # ── Step 5: Commit all atomically ─────────────────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Attempted {len(rows)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(rows) - rows_inserted} | "
            f"call_recording_analytics.id (last_processed_id) -> {last_cra_id} | "
            f"customer_call_record_id (last_processed_id_raw) -> {last_raw_id}"
        )
        return rows_inserted, last_raw_id

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
    total_skipped  = 0
    total_failed   = 0
    batch_num      = 0
    last_id        = 0      # keyset cursor: last seen customer_call_record_id

    try:
        with get_db_connection() as conn:

            # buffered=True — prevents "Unread result found" on cursor.close()
            # when fetchone() doesn't drain the full result set
            with conn.cursor(buffered=True) as cur:
                last_id = load_checkpoint(cur, SOURCE_TABLE, TARGET_TABLE)
            conn.commit()   # persist the initial INSERT if no checkpoint existed

            with conn.cursor() as cur:
                total_records = get_total_count(cur, last_id)

            logger.info(
                f"Total rows remaining (customer_call_record_id > {last_id}) "
                f": {total_records}"
            )

            if total_records == 0:
                logger.warning("No records found. ETL exiting.")
                return

            read_cursor = conn.cursor()

            while True:
                batch_num += 1

                # ── Fetch next batch via keyset pagination ────────────
                rows = fetch_batch(read_cursor, last_id, BATCH_SIZE)
                if not rows:
                    logger.info("No more records to process. Exiting loop.")
                    break

                attempt         = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        inserted, last_id = insert_batch_with_checkpoint(
                            conn, rows, batch_num,
                            SOURCE_TABLE, TARGET_TABLE,
                        )
                        total_inserted += inserted
                        total_skipped  += len(rows) - inserted

                        processed = total_inserted + total_skipped + total_failed
                        progress  = min((processed / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {processed}/{total_records} "
                            f"({progress:.1f}%) | "
                            f"Total Inserted : {total_inserted} | "
                            f"Total Skipped : {total_skipped}"
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
                            total_failed += len(rows)
                            logger.error(
                                f"Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts. "
                                f"Skipping {len(rows)} rows "
                                f"(last_id was {last_id})."
                            )

                    except DatabaseError as e:
                        total_failed += len(rows)
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(last_id was {last_id})."
                        )
                        # Advance past the poisoned batch so the loop can continue
                        last_id = rows[-1][34]
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    # Advance past unrecoverable batch
                    last_id = rows[-1][34]

            read_cursor.close()

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
    logger.info(f"  Total Skipped  : {total_skipped}  (INSERT IGNORE duplicates)")
    logger.info(f"  Total Failed   : {total_failed}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_etl()
