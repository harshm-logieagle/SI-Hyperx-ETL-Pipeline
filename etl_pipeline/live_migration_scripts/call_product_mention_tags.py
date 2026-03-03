"""
ETL Pipeline for Call Product Mention Tags
Raw Query:
INSERT INTO call_product_mention_tags (
    call_product_mentions_id,
    tags
)
SELECT
    cpm.id,
    TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(cpm.tags, ',', numbers.n), ',', -1)) AS tag
FROM call_product_mentions cpm
JOIN (
    SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL
    SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL
    SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10
) numbers
ON CHAR_LENGTH(cpm.tags) - CHAR_LENGTH(REPLACE(cpm.tags, ',', '')) >= numbers.n - 1;
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
        logging.FileHandler("etl_call_product_mention_tags.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CALL_PRODUCT_MENTION_TAGS")


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

SOURCE_TABLE = "call_product_mentions"
TARGET_TABLE = "call_product_mention_tags"

# INSERT IGNORE — silently skips duplicate conflicts on re-runs
INSERT_QUERY = """
    INSERT IGNORE INTO call_product_mention_tags (
        call_product_mentions_id,
        tags
    )
    VALUES (%s, %s)
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
            f"call_product_mentions.id "
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
# Tag Expansion Helper
# ─────────────────────────────────────────────────────────
def expand_tags(rows: list) -> list:
    """
    Replicates the SQL numbers-table expansion in Python.
    Each source row (cpm_id, tags_csv) produces one (cpm_id, tag)
    tuple per comma-delimited tag value (capped at 10, matching
    the original query's numbers table).
    """
    expanded = []
    for row in rows:
        cpm_id, tags_csv = row[0], row[1]
        if not tags_csv:
            continue
        tags = [t.strip() for t in str(tags_csv).split(",") if t.strip()]
        for tag in tags[:10]:
            expanded.append((cpm_id, tag))
    return expanded


# ─────────────────────────────────────────────────────────
# Core ETL Helpers
# ─────────────────────────────────────────────────────────
def get_total_count(cursor, last_processed_id_raw: int) -> int:
    """
    Counts total rows remaining in call_product_mentions
    from last_processed_id_raw onwards, so progress % reflects
    actual work left in this run.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM call_product_mentions
        WHERE id > %s
        """,
        (last_processed_id_raw,),
    )
    return cursor.fetchone()[0]


def fetch_batch(cursor, last_id: int, batch_size: int) -> list:
    """
    Keyset pagination on call_product_mentions.id.
    Fetches the next batch of (id, tags) rows with id > last_id,
    ordered ascending so the checkpoint always moves forward.
    """
    cursor.execute(
        """
        SELECT id, tags
        FROM call_product_mentions
        WHERE id > %s
        ORDER BY id ASC
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
) -> tuple[int, int, int]:
    """
    Single atomic transaction:
      1. Expand comma-separated tags into individual (cpm_id, tag) pairs
         (replicates the SQL numbers-table JOIN in Python)
      2. Bulk INSERT IGNORE into call_product_mention_tags
      3. Upsert etl_checkpoints — tracks last_processed_id_raw
         (max call_product_mentions.id in this batch)
    Full rollback on any failure — data and checkpoint stay in sync.
    Returns (rows_inserted, expanded_count, last_raw_id).
    """
    cursor = conn.cursor()
    try:
        # ── Step 1: Expand tags in Python ────────────────────────────
        last_raw_id = rows[-1][0]           # max call_product_mentions.id in batch
        expanded    = expand_tags(rows)

        # ── Step 2: Bulk INSERT IGNORE ────────────────────────────────
        cursor.executemany(INSERT_QUERY, expanded)
        rows_inserted = cursor.rowcount

        # ── Step 3: Update checkpoint ─────────────────────────────────
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
            (source_table, target_table, last_raw_id, last_raw_id),
        )

        # ── Step 4: Commit all atomically ─────────────────────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Source rows {len(rows)} | "
            f"Expanded tags {len(expanded)} | "
            f"Inserted {rows_inserted} | "
            f"Skipped (IGNORE) {len(expanded) - rows_inserted} | "
            f"call_product_mentions.id (last_processed_id_raw) -> {last_raw_id}"
        )
        return rows_inserted, len(expanded), last_raw_id

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

    total_inserted        = 0
    total_skipped         = 0
    total_failed          = 0
    total_source_processed = 0
    batch_num             = 0
    last_id               = 0      # keyset cursor: last seen call_product_mentions.id

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
                f"Total rows remaining (call_product_mentions.id > {last_id}) "
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
                        inserted, expanded_count, last_id = insert_batch_with_checkpoint(
                            conn, rows, batch_num,
                            SOURCE_TABLE, TARGET_TABLE,
                        )
                        total_inserted         += inserted
                        total_skipped          += expanded_count - inserted
                        total_source_processed += len(rows)

                        progress = min((total_source_processed / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {total_source_processed}/{total_records} "
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
                        last_id = rows[-1][0]
                        break

                if not batch_succeeded and attempt >= MAX_RETRIES:
                    # Advance past unrecoverable batch
                    last_id = rows[-1][0]

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
