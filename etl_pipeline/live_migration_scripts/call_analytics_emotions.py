"""
ETL Pipeline for Call Analytics Emotions
Raw Query:
INSERT INTO call_analytics_emotions (
    call_recording_analytics_id,
    master_outlet_id,
    outlet_id,
    call_recording_id,
    emotion_id,
    emotion_verbatim
)
SELECT
    cra.id,
    cra.master_outlet_id,
    cra.outlet_id,
    cra.call_recording_id,
    em.id,
    JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json, CONCAT('$[', n.n, '].emotion_verbatim'))) AS verbatim
FROM call_recording_analytics cra
INNER JOIN (
    SELECT (a.n + b.n * 10) AS n
    FROM
        (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
         UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
    CROSS JOIN
        (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
         UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
) n ON n.n < JSON_LENGTH(cra.emotions_json)
INNER JOIN emotions_master em
    ON JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json, CONCAT('$[', n.n, '].emotion'))) COLLATE utf8mb4_unicode_ci
     = em.name COLLATE utf8mb4_unicode_ci;
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

SCRIPT_NAME = "call_analytics_emotions"


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
        logging.FileHandler("etl_call_analytics_emotions.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CALL_ANALYTICS_EMOTIONS")


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

SOURCE_TABLE = "call_recording_analytics"
TARGET_TABLE = "call_analytics_emotions"

# INSERT IGNORE — silently skips duplicate conflicts on re-runs
INSERT_QUERY = """
    INSERT IGNORE INTO call_analytics_emotions (
        call_recording_analytics_id,
        master_outlet_id,
        outlet_id,
        call_recording_id,
        emotion_id,
        emotion_verbatim
    )
    VALUES (%s, %s, %s, %s, %s, %s)
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
            f"call_recording_analytics.id "
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
    Counts total source rows remaining in call_recording_analytics
    from last_processed_id_raw onwards that have non-empty emotions_json,
    so progress % reflects actual work left in this run.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM call_recording_analytics
        WHERE id > %s
          AND emotions_json IS NOT NULL
          AND JSON_LENGTH(emotions_json) > 0
        """,
        (last_processed_id_raw,),
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, last_id: int, batch_size: int) -> list:
    """
    Keyset pagination on call_recording_analytics.id.
    Fetches the next batch of source rows (id > last_id), expands each
    emotions_json array into individual rows via the numbers table, and
    joins emotions_master for the emotion_id lookup.
    Columns returned: 6 data columns + cra.id (keyset tracker, index 6).
    """
    cursor.execute(
        """
        SELECT
            cra.id          AS call_recording_analytics_id,
            cra.master_outlet_id,
            cra.outlet_id,
            cra.call_recording_id,
            em.id           AS emotion_id,
            JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json,
                CONCAT('$[', n.n, '].emotion_verbatim'))) AS emotion_verbatim,
            cra.id          AS keyset_id
        FROM (
            SELECT id
            FROM call_recording_analytics
            WHERE id > %s
              AND emotions_json IS NOT NULL
              AND JSON_LENGTH(emotions_json) > 0
            ORDER BY id ASC
            LIMIT %s
        ) ids
        JOIN call_recording_analytics cra ON cra.id = ids.id
        INNER JOIN (
            SELECT (a.n + b.n * 10) AS n
            FROM
                (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
            CROSS JOIN
                (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
        ) n ON n.n < JSON_LENGTH(cra.emotions_json)
        INNER JOIN emotions_master em
            ON JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json,
                CONCAT('$[', n.n, '].emotion'))) COLLATE utf8mb4_unicode_ci
             = em.name COLLATE utf8mb4_unicode_ci
        ORDER BY ids.id ASC
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
      1. Bulk INSERT IGNORE into call_analytics_emotions
         (rows[:6] are the 6 data columns; rows[6] is cra.id
          used only for checkpoint — stripped before insert)
      2. SELECT MAX(id) for accurate last_processed_id (TiDB-safe)
      3. Upsert etl_checkpoints — tracks both last_processed_id
         and last_processed_id_raw (max cra.id in this batch)
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Strip the trailing keyset column before INSERT ────
        # Each row = (6 data cols, cra.id)
        # cra.id is fetched for checkpoint tracking only.
        data_rows = [row[:6] for row in rows]
        last_raw_id = rows[-1][6]  # max cra.id in this batch

        # ── Step 2: Bulk INSERT IGNORE ────────────────────────────────
        cursor.executemany(INSERT_QUERY, data_rows)
        rows_inserted = cursor.rowcount

        # ── Step 3: Get actual last target ID (TiDB-safe) ─────────────
        cursor.execute("SELECT MAX(id) FROM call_analytics_emotions")
        result = cursor.fetchone()[0]
        last_cae_id = result if result is not None else 0

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
                (last_cae_id, last_raw_id, source_table, target_table),
            )
        else:
            cursor.execute(
                """
                INSERT INTO etl_checkpoints
                    (source_table_name, target_table_name,
                     last_processed_id, last_processed_id_raw)
                VALUES (%s, %s, %s, %s)
                """,
                (source_table, target_table, last_cae_id, last_raw_id),
            )

        # ── Step 5: Commit all atomically ─────────────────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Attempted {len(rows)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(rows) - rows_inserted} | "
            f"call_analytics_emotions.id (last_processed_id) -> {last_cae_id} | "
            f"call_recording_analytics.id (last_processed_id_raw) -> {last_raw_id}"
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
    last_id        = 0      # keyset cursor: last seen call_recording_analytics.id

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
                f"Total source rows remaining (call_recording_analytics.id > {last_id}) "
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
                                (rows[0][6], rows[-1][6]), len(rows), e,
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
                            (rows[0][6], rows[-1][6]), len(rows), e,
                        )
                        # Advance past the poisoned batch so the loop can continue
                        last_id = rows[-1][6]
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    # Advance past unrecoverable batch
                    last_id = rows[-1][6]

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
    