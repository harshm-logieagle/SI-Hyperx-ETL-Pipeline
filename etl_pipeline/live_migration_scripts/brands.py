"""
ETL Pipeline for Brands
Raw Query (Attached Below): 
INSERT INTO brands (brand_name, sinterface_id)
SELECT brand_name, id FROM outlets_raw WHERE outlet_type = 'master';
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

SCRIPT_NAME = "brands"

# Logging Configuration
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_brands.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_BRANDS")

# Configuration
DB_CONFIG = {
    "host": "10.0.4.194",
    "port": 4000,
    "user": "ai-team",
    "password": r"Zx4%shaU67&1@3slftyst",
    "database": "test_singleinterface_hyperx",
    "autocommit": False,
    "use_pure": True,
    "connection_timeout": 30
}

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2       # Exponential backoff base (seconds)

# ── Checkpoint identifiers ────────────────────────────────
SOURCE_TABLE = "outlets_raw"
TARGET_TABLE = "brands"


# Connection Context Manager
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


# Checkpoint Helpers
def load_checkpoint(cursor, source_table: str, target_table: str) -> tuple[int, int]:
    """
    Returns (last_processed_id, last_processed_id_raw).

    last_processed_id     → last brands.id inserted       (target cursor)
    last_processed_id_raw → last outlets_raw.id processed  (source keyset cursor)

    Returns (0, 0) on a fresh run with no existing checkpoint.
    """
    cursor.execute(
        """
        SELECT last_processed_id, last_processed_id_raw
        FROM   etl_checkpoints
        WHERE  source_table_name = %s
          AND  target_table_name = %s
        """,
        (source_table, target_table),
    )
    row = cursor.fetchone()
    if row:
        logger.info(
            f"Checkpoint found — "
            f"brands.id (last_processed_id) = {row[0]} | "
            f"outlets_raw.id (last_processed_id_raw) = {row[1]}"
        )
        return row[0], row[1]
    logger.info("No checkpoint found — starting fresh from id = 0.")
    return 0, 0


# Core ETL Helpers
def get_total_count(cursor) -> int:
    cursor.execute(
        "SELECT COUNT(*) FROM outlets_raw WHERE outlet_type = 'master'"
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, last_raw_id: int, batch_size: int) -> list:
    """
    Keyset pagination on outlets_raw.id.
    Avoids slow OFFSET scans regardless of dataset size.
    """
    cursor.execute(
        """
        SELECT brand_name, id
        FROM   outlets_raw
        WHERE  outlet_type = 'master'
          AND  id > %s
        ORDER  BY id ASC
        LIMIT  %s
        """,
        (last_raw_id, batch_size),
    )
    return cursor.fetchall()


def insert_batch_with_checkpoint(
    conn,
    rows: list,
    batch_num: int,
    new_last_raw_id: int,
    source_table: str,
    target_table: str,
) -> tuple[int, int]:
    """
    Single atomic transaction:
      1. Bulk INSERT rows into brands
      2. Upsert etl_checkpoints with:
           last_processed_id     ← cursor.lastrowid  (brands.id)
           last_processed_id_raw ← new_last_raw_id   (outlets_raw.id)

    On any failure → full rollback; both tables stay in sync.
    Returns (rows_inserted, last_brands_id).
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Bulk insert into brands ──────────────
        cursor.executemany(
            "INSERT INTO brands (brand_name, sinterface_id) VALUES (%s, %s)",
            rows,
        )
        rows_inserted  = cursor.rowcount
        cursor.execute("SELECT MAX(id) FROM brands")
        last_brands_id = cursor.fetchone()[0]

        # ── Step 2: Upsert checkpoint (same transaction) ─
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
                (last_brands_id, new_last_raw_id, source_table, target_table),
            )
        else:
            cursor.execute(
                """
                INSERT INTO etl_checkpoints
                    (source_table_name, target_table_name,
                     last_processed_id, last_processed_id_raw)
                VALUES (%s, %s, %s, %s)
                """,
                (source_table, target_table, last_brands_id, new_last_raw_id),
            )

        # ── Step 3: Commit both atomically ───────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | ✅ Inserted {rows_inserted} rows "
            f"| brands.id (last_processed_id) → {last_brands_id} "
            f"| outlets_raw.id (last_processed_id_raw) → {new_last_raw_id}"
        )
        return rows_inserted, last_brands_id

    except Error as e:
        conn.rollback()
        logger.error(
            f"Batch {batch_num:04d} | ❌ Transaction rolled back "
            f"(insert + checkpoint undone). Error: {e}"
        )
        raise
    finally:
        cursor.close()


# Main ETL Runner
def run_etl():
    logger.info("═" * 65)
    logger.info(f"ETL PIPELINE STARTED : {SOURCE_TABLE} ➜ {TARGET_TABLE}")
    logger.info("═" * 65)

    total_inserted = 0
    total_failed   = 0
    batch_num      = 0

    try:
        with get_db_connection() as conn:

            # ── Load checkpoint & total count ─────────────
            with conn.cursor() as cur:
                _, last_raw_id = load_checkpoint(cur, SOURCE_TABLE, TARGET_TABLE)
                # last_processed_id (brands) not needed for pagination;
                # only last_processed_id_raw (outlets_raw) drives keyset cursor
                total_records  = get_total_count(cur)

            if last_raw_id > 0:
                logger.warning(
                    f"Checkpoint already present (last_processed_id_raw = {last_raw_id}). "
                    f"Skipping insert to prevent duplicates — ETL exiting."
                )
                return

            logger.info(
                f"Source records (outlet_type='master') : {total_records} | "
                f"Fresh run — processing all from outlets_raw.id > 0"
            )

            if total_records == 0:
                logger.warning("No records found. ETL exiting.")
                return

            read_cursor = conn.cursor()

            while True:
                batch_num += 1

                # ── Fetch next batch ──────────────────────
                rows = fetch_batch(read_cursor, last_raw_id, BATCH_SIZE)
                if not rows:
                    logger.info("No more records to process. Exiting loop.")
                    break

                new_last_raw_id = rows[-1][1]

                # ── Insert + checkpoint with retry logic ──
                attempt         = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        inserted, _ = insert_batch_with_checkpoint(
                            conn, rows, batch_num,
                            new_last_raw_id,
                            SOURCE_TABLE, TARGET_TABLE,
                        )
                        total_inserted += inserted
                        last_raw_id = new_last_raw_id

                        progress = min((total_inserted / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {total_inserted}/{total_records} "
                            f"({progress:.1f}%)"
                        )
                        batch_succeeded = True
                        break

                    except OperationalError as e:
                        # Retriable: deadlock, lock wait timeout, dropped connection
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
                                f"(outlets_raw.id range: {rows[0][1]}–{new_last_raw_id})."
                            )
                            notify_on_permanent_failure(
                                SCRIPT_NAME, batch_num,
                                (rows[0][1], new_last_raw_id), len(rows), e,
                            )

                    except DatabaseError as e:
                        # Non-retriable: constraint violation, type mismatch, etc.
                        total_failed += len(rows)
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(outlets_raw.id range: {rows[0][1]}–{new_last_raw_id})."
                        )
                        notify_on_permanent_failure(
                            SCRIPT_NAME, batch_num,
                            (rows[0][1], new_last_raw_id), len(rows), e,
                        )
                        # Still advance cursor to avoid infinite loop on poisoned data
                        last_raw_id = new_last_raw_id
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    last_raw_id = new_last_raw_id

            read_cursor.close()

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(
            "ETL interrupted by user (Ctrl+C). "
            "Last committed checkpoint is safe — re-run to resume."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    # ── Final Summary ─────────────────────────────────────
    logger.info("═" * 65)
    logger.info("ETL PIPELINE COMPLETED")
    logger.info(f"  Total Batches  : {batch_num}")
    logger.info(f"  Total Inserted : {total_inserted}")
    logger.info(f"  Total Failed   : {total_failed}")
    logger.info("═" * 65)


if __name__ == "__main__":
    install_crash_notifier(SCRIPT_NAME)
    run_etl()
