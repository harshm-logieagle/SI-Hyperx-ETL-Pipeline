"""
Script: ETL — Insert customer_call_recordings in batches
DB: 10.0.4.194

Runs this query in batches (keyset pagination on raw.id):

    INSERT INTO customer_call_recordings (...)
    SELECT o.master_outlet_id, o.id, raw.id, ...
    FROM customer_call_record_logs raw
    JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
    WHERE o.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = SI_MASTER_OUTLET_ID)
      AND raw.id > RESUME_ID;

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
        logging.FileHandler("insert_ccr_by_outlet_ids.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_CCR")

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

SI_MASTER_OUTLET_ID = 206309    # si_master_outlet_id value in brands table
RESUME_ID           = 75738351  # raw.id to start from (exclusive)

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2  # seconds (exponential backoff base)

# ── Queries ───────────────────────────────────────────────────────────────────

# Returns the max raw.id in the next BATCH_SIZE rows after last_id
_FETCH_BATCH_MAX_QUERY = """
SELECT MAX(raw_id) FROM (
    SELECT raw.id AS raw_id
    FROM customer_call_record_logs raw
    JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
    WHERE o.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
      AND raw.id > %s
    ORDER BY raw_id ASC
    LIMIT %s
) sub
"""

_INSERT_SELECT_QUERY = """
INSERT INTO customer_call_recordings (
    master_outlet_id,
    outlet_id,
    call_record_raw_id,
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
    o.master_outlet_id,
    o.id,
    raw.id,
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
WHERE o.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = %s)
  AND raw.id > %s AND raw.id <= %s
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

                # Step 1: find the max raw.id for this batch window
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
