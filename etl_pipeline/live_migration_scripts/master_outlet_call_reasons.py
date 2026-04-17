"""
ETL Pipeline for Master Outlet Call Reasons
Raw Query:
INSERT INTO master_outlet_call_reasons (value, master_outlet_id, type)
SELECT
    raw.reason,
    o.master_outlet_id,
    raw.reason_type
FROM call_recording_analytics_details raw
JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
WHERE raw.reason IS NOT NULL
AND raw.id = (
    SELECT MAX(r2.id)
    FROM call_recording_analytics_details r2
    WHERE r2.reason = raw.reason
);
"""

import mysql.connector
from mysql.connector import Error, OperationalError, DatabaseError, InterfaceError
import logging
import time
import sys
from contextlib import contextmanager

from _etl_utils import (
    install_crash_notifier,
    notify_on_permanent_failure,
)

SCRIPT_NAME = "master_outlet_call_reasons"


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
        logging.FileHandler("etl_master_outlet_call_reasons.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_MASTER_OUTLET_CALL_REASONS")


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
TARGET_TABLE = "master_outlet_call_reasons"

# INSERT IGNORE — silently skips duplicate (master_outlet_id, type, value)
# conflicts on re-runs; correlated subquery in fetch ensures one row per unique reason
INSERT_QUERY = """
    INSERT IGNORE INTO master_outlet_call_reasons (
        value,
        master_outlet_id,
        type
    )
    VALUES (
        %s, %s, %s
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
            f"call_recording_analytics_details.id "
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
        JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
        WHERE raw.reason IS NOT NULL
          AND raw.id > %s
          AND raw.id = (
              SELECT MAX(r2.id)
              FROM call_recording_analytics_details r2
              WHERE r2.reason = raw.reason
          )
        """,
        (last_processed_id_raw,),
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, last_id: int, batch_size: int) -> list:
    """
    Keyset pagination on raw.id.
    Fetches the next batch of deduplicated rows: one row per unique reason
    (the row with the highest id for that reason), filtered to id > last_id,
    ordered ascending so the checkpoint always moves forward.
    Columns returned: 3 data columns + raw.id (keyset tracker, index 3).
    """
    cursor.execute(
        """
        SELECT
            raw.reason,
            o.master_outlet_id,
            raw.reason_type,
            raw.id          AS keyset_id
        FROM call_recording_analytics_details raw
        JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
        WHERE raw.reason IS NOT NULL
          AND raw.id > %s
          AND raw.id = (
              SELECT MAX(r2.id)
              FROM call_recording_analytics_details r2
              WHERE r2.reason = raw.reason
          )
        ORDER BY raw.id ASC
        LIMIT %s
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
      1. Bulk INSERT IGNORE into master_outlet_call_reasons
         (rows[:3] are the 3 data columns; rows[3] is raw.id
          used only for checkpoint — stripped before insert)
      2. SELECT MAX(id) for accurate last_processed_id (TiDB-safe)
      3. Upsert etl_checkpoints — tracks both last_processed_id
         and last_processed_id_raw (max raw.id in this batch)
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Strip the trailing keyset column before INSERT ────
        # Each row = (3 data cols, raw.id)
        # raw.id is fetched for checkpoint tracking only.
        data_rows = [row[:3] for row in rows]
        last_raw_id = rows[-1][3]  # max raw.id in this batch

        # ── Step 2: Bulk INSERT IGNORE ────────────────────────────────
        cursor.executemany(INSERT_QUERY, data_rows)
        rows_inserted = cursor.rowcount

        # ── Step 3: Get actual last target ID (TiDB-safe) ─────────────
        cursor.execute("SELECT MAX(id) FROM master_outlet_call_reasons")
        result      = cursor.fetchone()[0]
        last_mocr_id = result if result is not None else 0

        # ── Step 4: Upsert checkpoint ─────────────────────────────────
        # SELECT-then-UPDATE-or-INSERT: works without a unique key on
        # (source_table_name, target_table_name), and avoids the
        # rows-changed vs rows-matched gotcha of relying on UPDATE rowcount.
        cursor.execute(
            """
            SELECT 1 FROM etl_checkpoints
            WHERE  source_table_name = %s
              AND  target_table_name = %s
            """,
            (source_table, target_table),
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE etl_checkpoints
                SET    last_processed_id     = %s,
                       last_processed_id_raw = %s
                WHERE  source_table_name = %s
                  AND  target_table_name = %s
                """,
                (last_mocr_id, last_raw_id, source_table, target_table),
            )
        else:
            cursor.execute(
                """
                INSERT INTO etl_checkpoints
                    (source_table_name, target_table_name,
                     last_processed_id, last_processed_id_raw)
                VALUES (%s, %s, %s, %s)
                """,
                (source_table, target_table, last_mocr_id, last_raw_id),
            )

        # ── Step 5: Commit all atomically ─────────────────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Attempted {len(rows)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(rows) - rows_inserted} | "
            f"master_outlet_call_reasons.id (last_processed_id) -> {last_mocr_id} | "
            f"call_recording_analytics_details.id (last_processed_id_raw) -> {last_raw_id}"
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
    last_id        = 0      # keyset cursor: last seen call_recording_analytics_details.id

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
                f"Total rows remaining (call_recording_analytics_details.id > {last_id}) "
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
                            notify_on_permanent_failure(
                                SCRIPT_NAME, batch_num,
                                (rows[0][3], rows[-1][3]), len(rows), e,
                            )

                    except DatabaseError as e:
                        total_failed += len(rows)
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(last_id was {last_id})."
                        )
                        notify_on_permanent_failure(
                            SCRIPT_NAME, batch_num,
                            (rows[0][3], rows[-1][3]), len(rows), e,
                        )
                        # Advance past the poisoned batch so the loop can continue
                        last_id = rows[-1][3]
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    # Advance past unrecoverable batch
                    last_id = rows[-1][3]

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
    install_crash_notifier(SCRIPT_NAME)
    run_etl()
