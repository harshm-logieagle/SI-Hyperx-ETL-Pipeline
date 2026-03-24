"""
Script: ETL — Insert call_reasons in batches
DB: 10.0.4.194

Runs this query in batches (keyset pagination on cra.id):

    INSERT INTO call_reasons (...)
    SELECT cra.id, mocr.id, cra.master_outlet_id, ...
    FROM call_recording_analytics cra
    JOIN customer_call_recordings ccr ON cra.call_recording_id = ccr.id
    JOIN call_recording_analytics_details raw ON ccr.call_record_raw_id = raw.customer_call_record_id
    JOIN master_outlet_call_reasons mocr ON raw.reason = mocr.value AND mocr.master_outlet_id = cra.master_outlet_id
    WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = SI_MASTER_OUTLET_ID)
      AND cra.id > RESUME_ID;

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
        logging.FileHandler("insert_cr_by_outlet_ids.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CR")

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
RESUME_ID           = 1812136 # cra.id to start from (exclusive)

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2  # seconds (exponential backoff base)

# ── Queries ───────────────────────────────────────────────────────────────────

# Returns the max cra.id for the next BATCH_SIZE rows after last_id
_FETCH_BATCH_MAX_QUERY = """
SELECT MAX(cra_id) FROM (
    SELECT cra.id AS cra_id
    FROM call_recording_analytics cra
    WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
      AND cra.id > %s
    ORDER BY cra_id ASC
    LIMIT %s
) sub
"""

_INSERT_SELECT_QUERY = """
INSERT INTO call_reasons (
    call_recording_analytics_id,
    master_outlet_reason_id,
    master_outlet_id,
    outlet_id,
    call_recording_id,
    reason_verbatim
)
SELECT
    cra.id,
    mocr.id,
    cra.master_outlet_id,
    cra.outlet_id,
    cra.call_recording_id,
    raw.reason_verbatim
FROM call_recording_analytics cra
JOIN customer_call_recordings ccr ON cra.call_recording_id = ccr.id
JOIN call_recording_analytics_details raw ON ccr.call_record_raw_id = raw.customer_call_record_id
JOIN master_outlet_call_reasons mocr
    ON raw.reason COLLATE utf8mb4_unicode_ci = mocr.value COLLATE utf8mb4_unicode_ci
    AND mocr.master_outlet_id = cra.master_outlet_id
WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
  AND cra.id > %s AND cra.id <= %s
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

                # Step 1: find the max cra.id for this batch window
                with conn.cursor() as cur:
                    cur.execute(_FETCH_BATCH_MAX_QUERY, (SI_MASTER_OUTLET_ID, last_id, BATCH_SIZE))
                    row = cur.fetchone()

                if not row or row[0] is None:
                    logger.info(f"No more rows after id={last_id}. Done.")
                    break

                batch_max_id = row[0]
                logger.info(f"Batch {batch_num:04d} | id window: ({last_id} – {batch_max_id}]")

                # Step 2: INSERT...SELECT for this window, with retry
                attempt = 0
                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        with conn.cursor() as cur:
                            # params: SI_MASTER_OUTLET_ID (WHERE), last_id, batch_max_id (id window)
                            cur.execute(_INSERT_SELECT_QUERY, (SI_MASTER_OUTLET_ID, last_id, batch_max_id))
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
                                f"Skipping id window ({last_id} – {batch_max_id}]."
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
        logger.warning(f"Interrupted. Last processed id={last_id}. Re-run with RESUME_ID={last_id} to continue.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("ETL COMPLETED")
    logger.info(f"  Total inserted : {total_inserted}")
    logger.info(f"  Last id        : {last_id}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_etl()
