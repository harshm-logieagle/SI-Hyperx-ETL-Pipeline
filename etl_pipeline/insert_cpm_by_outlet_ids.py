"""
Script: ETL — Insert call_product_mentions in batches
DB: 10.0.4.194

Runs this query in batches (keyset pagination on cra.call_recording_id):

    INSERT INTO call_product_mentions (...)
    SELECT tr.id, mop.id, tr.master_outlet_id, ...
    FROM ( ... JSON expansion of call_recording_analytics ... ) tr
    INNER JOIN master_outlet_categories moc ...
    INNER JOIN master_outlet_products mop ...
    WHERE tr.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = SI_MASTER_OUTLET_ID)
      AND cra.call_recording_id > RESUME_ID;

Usage:
    Set SI_MASTER_OUTLET_ID and RESUME_ID below, then run.
"""

import mysql.connector
from mysql.connector import Error, OperationalError, DatabaseError, InterfaceError
import logging
import time
import sys
from contextlib import contextmanager

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("insert_cpm_by_outlet_ids.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CPM")

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

# ── Inputs ─────────────────────────────────────────────────────────────────────

SI_MASTER_OUTLET_ID = 206309  # si_master_outlet_id value in brands table
RESUME_ID           = 1812133 # cra.call_recording_id to start from (exclusive)

BATCH_SIZE    = 500   # distinct call_recording_ids per batch (JSON expansion multiplies rows)
MAX_RETRIES   = 3
RETRY_BACKOFF = 2     # seconds (exponential backoff base)

# ── Queries ───────────────────────────────────────────────────────────────────

# Returns the max call_recording_id for the next BATCH_SIZE distinct ids after last_id
_FETCH_BATCH_MAX_QUERY = """
SELECT MAX(cra_id) FROM (
    SELECT DISTINCT cra.call_recording_id AS cra_id
    FROM call_recording_analytics cra
    WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
      AND cra.call_recording_id > %s
    ORDER BY cra_id ASC
    LIMIT %s
) sub
"""

_INSERT_SELECT_QUERY = """
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
            JSON_EXTRACT(cra.products_mentioned_json,             CONCAT('$[', prod_n.n, '].tags'))                AS tags_arr
        FROM call_recording_analytics cra
        INNER JOIN (
            SELECT (a.n + b.n * 10) AS n
            FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                  UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
            CROSS JOIN
                 (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                  UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
        ) prod_n ON prod_n.n < JSON_LENGTH(cra.products_mentioned_json)
        WHERE cra.call_recording_id > %s AND cra.call_recording_id <= %s
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
WHERE tr.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
"""

# ── Connection ─────────────────────────────────────────────────────────────────

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        logger.info("DB connection established.")
        yield conn
    except Error as e:
        logger.critical(f"Failed to connect to DB: {e}")
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()
            logger.info("DB connection closed.")


# ── Main ───────────────────────────────────────────────────────────────────────

def run_etl():
    logger.info("=" * 65)
    logger.info(f"ETL STARTED | si_master_outlet_id={SI_MASTER_OUTLET_ID} | resume_id={RESUME_ID}")
    logger.info("=" * 65)

    total_inserted = 0
    last_id        = RESUME_ID
    batch_num      = 0

    try:
        with get_db_connection() as conn:
            while True:
                batch_num += 1

                # Step 1: find the max call_recording_id for this batch window
                with conn.cursor() as cur:
                    cur.execute(_FETCH_BATCH_MAX_QUERY, (SI_MASTER_OUTLET_ID, last_id, BATCH_SIZE))
                    row = cur.fetchone()

                if not row or row[0] is None:
                    logger.info(f"No more rows after call_recording_id={last_id}. Done.")
                    break

                batch_max_id = row[0]
                logger.info(f"Batch {batch_num:04d} | call_recording_id window: ({last_id} – {batch_max_id}]")

                # Step 2: INSERT...SELECT for this window, with retry
                attempt = 0
                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        with conn.cursor() as cur:
                            # params: last_id, batch_max_id (inner WHERE), SI_MASTER_OUTLET_ID (outer WHERE)
                            cur.execute(_INSERT_SELECT_QUERY, (last_id, batch_max_id, SI_MASTER_OUTLET_ID))
                            inserted = cur.rowcount if cur.rowcount >= 0 else 0
                        conn.commit()

                        total_inserted += inserted
                        last_id = batch_max_id
                        logger.info(
                            f"Batch {batch_num:04d} | Inserted: {inserted} | "
                            f"Total: {total_inserted} | last_id={last_id}"
                        )
                        break

                    except OperationalError as e:
                        conn.rollback()
                        logger.warning(f"Batch {batch_num:04d} | OperationalError (attempt {attempt}/{MAX_RETRIES}): {e}")
                        if attempt < MAX_RETRIES:
                            sleep_time = RETRY_BACKOFF ** attempt
                            logger.info(f"Retrying in {sleep_time}s ...")
                            time.sleep(sleep_time)
                            if not conn.is_connected():
                                conn.reconnect(attempts=3, delay=2)
                                logger.info("Reconnected to DB.")
                        else:
                            logger.error(
                                f"Batch {batch_num:04d} | PERMANENTLY FAILED after {MAX_RETRIES} attempts. "
                                f"Skipping call_recording_id window ({last_id} – {batch_max_id}]."
                            )
                            last_id = batch_max_id

                    except DatabaseError as e:
                        conn.rollback()
                        logger.error(f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. Skipping window ({last_id} – {batch_max_id}].")
                        last_id = batch_max_id
                        break

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(f"Interrupted. Last processed call_recording_id={last_id}. Re-run with RESUME_ID={last_id} to continue.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("ETL COMPLETED")
    logger.info(f"  Total inserted       : {total_inserted}")
    logger.info(f"  Last call_recording_id : {last_id}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_etl()
