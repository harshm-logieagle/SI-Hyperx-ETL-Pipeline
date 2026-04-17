"""
ETL Pipeline for Call Product Mentions
Raw Query (TiDB-compatible — uses cross-joined number sequences to expand JSON
arrays instead of JSON_TABLE + NESTED PATH which TiDB does not support):

INSERT INTO call_product_mentions (
    call_recording_analytics_id,
    master_outlet_product_id,
    master_outlet_id,
    outlet_id,
    call_recording_id,
    product_sentiment,
    product_verbatim,
    tags
)
SELECT
    tr.id,
    mop.id,
    tr.master_outlet_id,
    tr.outlet_id,
    tr.call_recording_id,
    tr.sentiment,
    tr.verbatim,
    tr.tags
FROM (
    SELECT
        pr.id, pr.master_outlet_id, pr.outlet_id, pr.call_recording_id,
        pr.p_name, pr.p_category, pr.sentiment, pr.verbatim,
        JSON_UNQUOTE(JSON_EXTRACT(pr.tags_arr, CONCAT('$[', tag_n.n, ']'))) AS tags
    FROM (
        SELECT
            cra.id, cra.master_outlet_id, cra.outlet_id, cra.call_recording_id,
            JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product')))           AS p_name,
            JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].category')))          AS p_category,
            JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product_sentiment'))) AS sentiment,
            JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product_verbatim')))  AS verbatim,
            JSON_EXTRACT(cra.products_mentioned_json,              CONCAT('$[', prod_n.n, '].tags'))               AS tags_arr
        FROM call_recording_analytics cra
        INNER JOIN (
            SELECT (a.n + b.n * 10) AS n
            FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                  UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
            CROSS JOIN
                 (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                  UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
        ) prod_n ON prod_n.n < JSON_LENGTH(cra.products_mentioned_json)
        WHERE cra.id > <last_id> AND cra.id <= <batch_max_id>
    ) pr
    INNER JOIN (
        SELECT (a.n + b.n * 10) AS n
        FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
              UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
        CROSS JOIN
             (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
              UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
    ) tag_n ON tag_n.n < JSON_LENGTH(pr.tags_arr)
) tr
INNER JOIN master_outlet_categories moc
    ON  tr.p_category COLLATE utf8mb4_unicode_ci = moc.category_name COLLATE utf8mb4_unicode_ci
    AND moc.master_outlet_id = tr.master_outlet_id
INNER JOIN master_outlet_products mop
    ON  tr.p_name     COLLATE utf8mb4_unicode_ci = mop.name           COLLATE utf8mb4_unicode_ci
    AND mop.category_id      = moc.id
    AND mop.master_outlet_id = tr.master_outlet_id
ORDER BY tr.id ASC;
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

SCRIPT_NAME = "call_product_mentions"


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
        logging.FileHandler("etl_call_product_mentions.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CALL_PRODUCT_MENTIONS")


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
TARGET_TABLE = "call_product_mentions"

# INSERT IGNORE — silently skips duplicate conflicts on re-runs
INSERT_QUERY = """
    INSERT IGNORE INTO call_product_mentions (
        call_recording_analytics_id,
        master_outlet_product_id,
        master_outlet_id,
        outlet_id,
        call_recording_id,
        product_sentiment,
        product_verbatim,
        tags
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
    Counts total source CRA rows remaining from last_processed_id_raw onwards.
    Progress % is expressed in terms of CRA rows scanned, not expanded output
    rows, since one CRA row can yield many call_product_mentions rows.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM call_recording_analytics
        WHERE id > %s
        """,
        (last_processed_id_raw,),
    )
    return cursor.fetchone()[0]


def fetch_raw_batch(cursor, last_id: int, batch_size: int) -> list:
    """
    Keyset pagination on call_recording_analytics.id.
    Returns the next batch of CRA ids — used solely to establish batch_max_id
    so fetch_expanded_batch knows which CRA id range to expand.

    Keeping boundary detection separate from expansion ensures we always
    advance the checkpoint even when a batch produces zero expanded rows
    (e.g. all products_mentioned_json are NULL or tags arrays are empty).
    """
    cursor.execute(
        """
        SELECT id
        FROM call_recording_analytics
        WHERE id > %s
        ORDER BY id ASC
        LIMIT %s
        """,
        (last_id, batch_size),
    )
    return cursor.fetchall()


def fetch_expanded_batch(cursor, last_id: int, batch_max_id: int) -> list:
    """
    Fetches all expanded product-mention rows for CRA ids in (last_id, batch_max_id].

    Uses cross-joined number sequences (0-99) as a TiDB-compatible replacement
    for JSON_TABLE + NESTED PATH:
      - prod_n iterates over each product entry in products_mentioned_json
      - tag_n  iterates over each tag within that product's tags array
    INNER JOIN filters on prod_n.n < JSON_LENGTH(...) and tag_n.n < JSON_LENGTH(...)
    so only valid indices are visited (no out-of-bounds nulls).

    The number sequences support up to 100 products per CRA row and 100 tags
    per product (0..99). Extend the cross-join if larger arrays are expected.

    Columns returned match INSERT_QUERY column order exactly (8 columns):
      (cra.id, mop.id, master_outlet_id, outlet_id, call_recording_id,
       sentiment, verbatim, tags)
    """
    cursor.execute(
        """
        SELECT
            tr.id,
            mop.id,
            tr.master_outlet_id,
            tr.outlet_id,
            tr.call_recording_id,
            tr.sentiment,
            tr.verbatim,
            tr.tags
        FROM (
            SELECT
                pr.id, pr.master_outlet_id, pr.outlet_id, pr.call_recording_id,
                pr.p_name, pr.p_category, pr.sentiment, pr.verbatim,
                JSON_UNQUOTE(JSON_EXTRACT(pr.tags_arr, CONCAT('$[', tag_n.n, ']'))) AS tags
            FROM (
                SELECT
                    cra.id, cra.master_outlet_id, cra.outlet_id, cra.call_recording_id,
                    JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product')))           AS p_name,
                    JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].category')))          AS p_category,
                    JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product_sentiment'))) AS sentiment,
                    JSON_UNQUOTE(JSON_EXTRACT(cra.products_mentioned_json, CONCAT('$[', prod_n.n, '].product_verbatim')))  AS verbatim,
                    JSON_EXTRACT(cra.products_mentioned_json,              CONCAT('$[', prod_n.n, '].tags'))               AS tags_arr
                FROM call_recording_analytics cra
                INNER JOIN (
                    SELECT (a.n + b.n * 10) AS n
                    FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                          UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
                    CROSS JOIN
                         (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                          UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
                ) prod_n ON prod_n.n < JSON_LENGTH(cra.products_mentioned_json)
                WHERE cra.id > %s AND cra.id <= %s
            ) pr
            INNER JOIN (
                SELECT (a.n + b.n * 10) AS n
                FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                      UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
                CROSS JOIN
                     (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                      UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
            ) tag_n ON tag_n.n < JSON_LENGTH(pr.tags_arr)
        ) tr
        INNER JOIN master_outlet_categories moc
            ON  tr.p_category COLLATE utf8mb4_unicode_ci = moc.category_name COLLATE utf8mb4_unicode_ci
            AND moc.master_outlet_id = tr.master_outlet_id
        INNER JOIN master_outlet_products mop
            ON  tr.p_name     COLLATE utf8mb4_unicode_ci = mop.name           COLLATE utf8mb4_unicode_ci
            AND mop.category_id      = moc.id
            AND mop.master_outlet_id = tr.master_outlet_id
        ORDER BY tr.id ASC
        """,
        (last_id, batch_max_id),
    )
    return cursor.fetchall()


def insert_batch_with_checkpoint(
    conn,
    rows: list,
    batch_max_id: int,
    batch_num: int,
    source_table: str,
    target_table: str,
) -> int:
    """
    Single atomic transaction:
      1. Bulk INSERT IGNORE into call_product_mentions (8 data columns per row)
      2. SELECT MAX(id) for accurate last_processed_id (TiDB-safe)
      3. Upsert etl_checkpoints — tracks both last_processed_id
         and last_processed_id_raw (= batch_max_id, the last CRA id in this batch)
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Bulk INSERT IGNORE ────────────────────────────────
        cursor.executemany(INSERT_QUERY, rows)
        rows_inserted = cursor.rowcount

        # ── Step 2: Get actual last target ID (TiDB-safe) ─────────────
        cursor.execute("SELECT MAX(id) FROM call_product_mentions")
        result      = cursor.fetchone()[0]
        last_cpm_id = result if result is not None else 0

        # ── Step 3: Upsert checkpoint ──────────────────────────────────
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
                (last_cpm_id, batch_max_id, source_table, target_table),
            )
        else:
            cursor.execute(
                """
                INSERT INTO etl_checkpoints
                    (source_table_name, target_table_name,
                     last_processed_id, last_processed_id_raw)
                VALUES (%s, %s, %s, %s)
                """,
                (source_table, target_table, last_cpm_id, batch_max_id),
            )

        # ── Step 4: Commit all atomically ─────────────────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Attempted {len(rows)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(rows) - rows_inserted} | "
            f"call_product_mentions.id (last_processed_id) -> {last_cpm_id} | "
            f"call_recording_analytics.id (last_processed_id_raw) -> {batch_max_id}"
        )
        return rows_inserted

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

    total_inserted      = 0
    total_skipped       = 0
    total_failed        = 0
    total_cra_processed = 0   # CRA rows scanned (for progress %)
    batch_num           = 0
    last_id             = 0   # keyset cursor: last seen call_recording_analytics.id

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
                f"Total source CRA rows remaining "
                f"(call_recording_analytics.id > {last_id}) : {total_records}"
            )

            if total_records == 0:
                logger.warning("No records found. ETL exiting.")
                return

            read_cursor = conn.cursor()

            while True:
                batch_num += 1

                # ── Step 1: Get next batch of CRA ids (boundary only) ──
                # Separate from expansion so we can advance the checkpoint
                # even when the full expansion produces zero output rows
                # (e.g. NULL products_mentioned_json or empty tags arrays).
                raw_ids = fetch_raw_batch(read_cursor, last_id, BATCH_SIZE)
                if not raw_ids:
                    logger.info("No more records to process. Exiting loop.")
                    break

                batch_max_id = raw_ids[-1][0]   # last cra.id in this batch

                # ── Step 2: Expand JSON via TiDB-compatible SQL ────────
                rows = fetch_expanded_batch(read_cursor, last_id, batch_max_id)

                if not rows:
                    # All CRA rows in this batch had NULL/empty JSON or
                    # tags arrays — no output rows generated.
                    # Advance the raw checkpoint so we don't re-scan on resume.
                    logger.info(
                        f"Batch {batch_num:04d} | "
                        f"No expanded rows for CRA id range "
                        f"({last_id}, {batch_max_id}] "
                        f"(NULL JSON or empty tags) — advancing checkpoint."
                    )
                    with conn.cursor() as cur:
                        # SELECT-then-UPDATE-or-INSERT: works without a unique
                        # key on (source_table_name, target_table_name), and
                        # avoids the rows-changed vs rows-matched gotcha of
                        # relying on UPDATE rowcount.
                        cur.execute(
                            """
                            SELECT 1 FROM etl_checkpoints
                            WHERE  source_table_name = %s
                              AND  target_table_name = %s
                            """,
                            (SOURCE_TABLE, TARGET_TABLE),
                        )
                        if cur.fetchone():
                            cur.execute(
                                """
                                UPDATE etl_checkpoints
                                SET    last_processed_id_raw = %s
                                WHERE  source_table_name = %s
                                  AND  target_table_name = %s
                                """,
                                (batch_max_id, SOURCE_TABLE, TARGET_TABLE),
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO etl_checkpoints
                                    (source_table_name, target_table_name,
                                     last_processed_id, last_processed_id_raw)
                                VALUES (%s, %s, 0, %s)
                                """,
                                (SOURCE_TABLE, TARGET_TABLE, batch_max_id),
                            )
                    conn.commit()
                    total_cra_processed += len(raw_ids)
                    last_id = batch_max_id
                    continue

                attempt         = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        inserted = insert_batch_with_checkpoint(
                            conn, rows, batch_max_id, batch_num,
                            SOURCE_TABLE, TARGET_TABLE,
                        )
                        total_inserted      += inserted
                        total_skipped       += len(rows) - inserted
                        total_cra_processed += len(raw_ids)

                        progress = min((total_cra_processed / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {total_cra_processed}/{total_records} CRA rows "
                            f"({progress:.1f}%) | "
                            f"Total Inserted : {total_inserted} | "
                            f"Total Skipped : {total_skipped}"
                        )
                        last_id         = batch_max_id
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
                                (last_id, batch_max_id), len(rows), e,
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
                            (last_id, batch_max_id), len(rows), e,
                        )
                        # Advance past the poisoned batch so the loop can continue
                        last_id = batch_max_id
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    # Advance past unrecoverable batch
                    last_id = batch_max_id

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
