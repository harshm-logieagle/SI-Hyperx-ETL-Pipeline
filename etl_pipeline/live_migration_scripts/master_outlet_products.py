"""
ETL Pipeline for Master Outlet Products
Raw Query:
INSERT INTO master_outlet_products (name, embedding, master_outlet_id, category_id)
SELECT DISTINCT 
    CONVERT(phr.product_name USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_name,
    CONVERT(phr.product_embedding USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_embedding,
    b.id,
    moc.id
FROM brands b
JOIN outlets_raw t 
    ON t.brand_name COLLATE utf8mb4_unicode_ci = b.brand_name COLLATE utf8mb4_unicode_ci
JOIN product_hierarchy phr 
    ON CONVERT(phr.master_outlet_id USING utf8mb4) COLLATE utf8mb4_unicode_ci = t.id
JOIN master_outlet_categories moc 
    ON CONVERT(phr.category USING utf8mb4) COLLATE utf8mb4_unicode_ci = moc.category_name;
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
        logging.FileHandler("etl_master_outlet_products.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_MASTER_OUTLET_PRODUCTS")


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

SOURCE_TABLE = "product_hierarchy"
TARGET_TABLE = "master_outlet_products"

# INSERT IGNORE — silently skips cross-batch DISTINCT duplicates
INSERT_QUERY = """
    INSERT IGNORE INTO master_outlet_products
        (name, embedding, master_outlet_id, category_id)
    VALUES (%s, %s, %s, %s)
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
    Returns last_processed_id only.
    last_processed_id_raw is NOT tracked for this ETL —
    pagination uses OFFSET; INSERT IGNORE handles re-runs idempotently.
    """
    cursor.execute(
        """
        SELECT last_processed_id
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
            f"master_outlet_products.id (last_processed_id) = {row[0]}"
        )
        return row[0]
    logger.info("No checkpoint found -- starting fresh.")
    return 0


# ─────────────────────────────────────────────────────────
# Core ETL Helpers
# ─────────────────────────────────────────────────────────
def get_total_count(cursor) -> int:
    """
    Counts total DISTINCT (product_name, product_embedding, b.id, moc.id)
    rows so progress % reflects actual unique rows to be inserted.
    """
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT 
                CONVERT(phr.product_name USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_name,
                CONVERT(phr.product_embedding USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_embedding,
                b.id as master_outlet_id,
                moc.id as category_id
            FROM brands b
            JOIN outlets_raw t 
                ON t.brand_name COLLATE utf8mb4_unicode_ci = b.brand_name COLLATE utf8mb4_unicode_ci
            JOIN product_hierarchy phr 
                ON CONVERT(phr.master_outlet_id USING utf8mb4) COLLATE utf8mb4_unicode_ci = t.id
            JOIN master_outlet_categories moc 
                ON CONVERT(phr.category USING utf8mb4) COLLATE utf8mb4_unicode_ci = moc.category_name
        ) AS distinct_pairs
        """
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, offset: int, batch_size: int) -> list:
    """
    OFFSET-based pagination on the full DISTINCT result set.
    Rows are exactly (name, embedding, master_outlet_id, category_id) —
    same column order as INSERT_QUERY. No stripping needed.
    """
    cursor.execute(
        """
        SELECT DISTINCT 
            CONVERT(phr.product_name USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_name,
            CONVERT(phr.product_embedding USING utf8mb4) COLLATE utf8mb4_unicode_ci AS product_embedding,
            b.id,
            moc.id
        FROM brands b
        JOIN outlets_raw t 
            ON t.brand_name COLLATE utf8mb4_unicode_ci = b.brand_name COLLATE utf8mb4_unicode_ci
        JOIN product_hierarchy phr 
            ON CONVERT(phr.master_outlet_id USING utf8mb4) COLLATE utf8mb4_unicode_ci = t.id
        JOIN master_outlet_categories moc 
            ON CONVERT(phr.category USING utf8mb4) COLLATE utf8mb4_unicode_ci = moc.category_name
        LIMIT  %s OFFSET %s
        """,
        (batch_size, offset),
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
      1. Bulk INSERT IGNORE into master_outlet_products
         (rows are already (name, embedding, master_outlet_id, category_id))
      2. SELECT MAX(id) for accurate last_processed_id (TiDB-safe)
      3. Upsert etl_checkpoints — only last_processed_id tracked;
         last_processed_id_raw = 0 intentionally
    Full rollback on any failure — data and checkpoint stay in sync.
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Bulk INSERT IGNORE ────────────────────
        cursor.executemany(INSERT_QUERY, rows)
        rows_inserted = cursor.rowcount

        # ── Step 2: Get actual last ID (TiDB-safe) ────────
        cursor.execute("SELECT MAX(id) FROM master_outlet_products")
        result      = cursor.fetchone()[0]
        last_mop_id = result if result is not None else 0

        # ── Step 3: Upsert checkpoint (same transaction) ──
        cursor.execute(
            """
            INSERT INTO etl_checkpoints
                (source_table_name, target_table_name,
                 last_processed_id, last_processed_id_raw)
            VALUES (%s, %s, %s, 0)
            ON DUPLICATE KEY UPDATE
                last_processed_id = VALUES(last_processed_id)
            """,
            (source_table, target_table, last_mop_id),
        )

        # ── Step 4: Commit all atomically ─────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Attempted {len(rows)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(rows) - rows_inserted} | "
            f"master_outlet_products.id (last_processed_id) -> {last_mop_id}"
        )
        return rows_inserted, last_mop_id

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
    offset         = 0

    try:
        with get_db_connection() as conn:

            # buffered=True — prevents "Unread result found" on cursor.close()
            # when fetchone() doesn't drain the full result set
            with conn.cursor(buffered=True) as cur:
                _ = load_checkpoint(cur, SOURCE_TABLE, TARGET_TABLE)

            with conn.cursor() as cur:
                total_records = get_total_count(cur)

            logger.info(
                f"Total DISTINCT (name, embedding, master_outlet_id, category_id) "
                f"rows : {total_records}"
            )

            if total_records == 0:
                logger.warning("No records found. ETL exiting.")
                return

            read_cursor = conn.cursor()

            while True:
                batch_num += 1

                # ── Fetch next batch via OFFSET ───────────
                rows = fetch_batch(read_cursor, offset, BATCH_SIZE)
                if not rows:
                    logger.info("No more records to process. Exiting loop.")
                    break

                attempt         = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        inserted, _ = insert_batch_with_checkpoint(
                            conn, rows, batch_num,
                            SOURCE_TABLE, TARGET_TABLE,
                        )
                        total_inserted += inserted
                        total_skipped  += len(rows) - inserted
                        offset         += len(rows)     # Advance OFFSET on success

                        progress = min((offset / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {offset}/{total_records} "
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
                                f"(offset {offset} - {offset + len(rows)})."
                            )

                    except DatabaseError as e:
                        total_failed += len(rows)
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(offset {offset} - {offset + len(rows)})."
                        )
                        offset += len(rows)     # Advance past poisoned batch
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    offset += len(rows)         # Advance past unrecoverable batch

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
    logger.info(f"  Total Skipped  : {total_skipped}  (cross-batch DISTINCT duplicates)")
    logger.info(f"  Total Failed   : {total_failed}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_etl()
