"""
Script: Sync call_recording_analytics_details by Master Outlet IDs
Source DB: SI LIVE DB (sinterface) — call_recording_analytics_details table
Target DB: 10.0.4.194 — call_recording_analytics_details table

Sync Logic:
1. Iterate over each master_outlet_id in TARGET_OUTLET_IDS.
2. For each outlet_id, look up custom_sync_tracking to get last_inserted_id
   (keyed on source_table_name = "call_recording_analytics_details_<outlet_id>").
3. Fetch rows with master_outlet_id = X AND id > last_inserted_id from source
   in batches (keyset pagination).
4. INSERT IGNORE into target (id-based dedup — append-only sync).
5. Checkpoint last_inserted_id in custom_sync_tracking atomically after each batch.
6. Stamp last_sync_time in custom_sync_tracking on full completion of each outlet_id.

Tracking table: custom_sync_tracking
Tracking key per outlet: (source_table_name="call_recording_analytics_details_<id>", target_table="call_recording_analytics_details")
"""

import mysql.connector
from mysql.connector import Error, OperationalError, DatabaseError, InterfaceError
import logging
import time
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sync_crad_by_outlet_ids.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("SYNC_CRAD_BY_IDS")

SOURCE_DB_CONFIG = {
    "host": "live-si-db.c83fh8gbkqpw.ap-south-1.rds.amazonaws.com",
    "port": 3306,
    "user": "siddant",
    "password": "v&G8gbU<d+.6AT_=f4:iOu(T6pEiOZOxPmk6JeWePKjNKmrAwrC5x^!XNft",
    "database": "sinterface",
    "autocommit": True,
    "use_pure": True,
    "connection_timeout": 30,
}

TARGET_DB_CONFIG = {
    "host": "10.0.4.194",
    "port": 4000,
    "user": "ai-team",
    "password": r"Zx4%shaU67&1@3slftyst",
    "database": "test_singleinterface_hyperx",
    "autocommit": False,
    "use_pure": True,
    "connection_timeout": 30,
}

# ── Configuration ──────────────────────────────────────────────────────────────

# Add / remove master_outlet_ids here before running
TARGET_OUTLET_IDS = [286487, 206309, 321091, 294333, 275470, 127035, 126696, 261121, 126712, 76409, 4844, 61535, 271756, 377407, 472433, 337572, 374460, 507806]  # TODO: set the master outlet ids here

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2  # seconds (exponential backoff base)

SOURCE_TABLE = "call_recording_analytics_details"
TARGET_TABLE = "call_recording_analytics_details"
SYNC_TABLE   = "custom_sync_tracking"

# ── Column Definitions ────────────────────────────────────────────────────────

_COLUMNS = [
    "id", "is_webhook", "customer_call_record_id", "analytic_type", "created",
    "modified", "text_status", "reason", "reason_verbatim", "master_outlet_id",
    "outlet_id", "audio_to_text", "reason_type", "end_of_call_status",
    "call_language", "customer_gender", "customer_type", "overall_sentiment",
    "summary", "is_valid_transcript", "transcript", "emotions", "emotion_verbatims",
    "emotions_json", "products", "product_sentiments", "product_verbatims",
    "product_tags", "product_categories", "products_mentioned_json", "l1_reason",
    "l2_reason", "l3_reason", "brand_sentiment", "l0_reason",
]

_COLS_SQL     = ", ".join(f"`{c}`" for c in _COLUMNS)
_PLACEHOLDERS = ", ".join(["%s"] * len(_COLUMNS))

_FETCH_QUERY = (
    f"SELECT {_COLS_SQL} FROM `{SOURCE_TABLE}` "
    f"WHERE master_outlet_id = %s AND id > %s ORDER BY id ASC LIMIT %s"
)

_INSERT_QUERY = (
    f"INSERT IGNORE INTO `{TARGET_TABLE}` ({_COLS_SQL}) "
    f"VALUES ({_PLACEHOLDERS})"
)


# ── Connection Context Managers ───────────────────────────────────────────────

@contextmanager
def get_source_connection():
    conn = None
    try:
        conn = mysql.connector.connect(**SOURCE_DB_CONFIG)
        logger.info("Source DB connection established.")
        yield conn
    except Error as e:
        logger.critical(f"Failed to connect to source DB: {e}")
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()
            logger.info("Source DB connection closed.")


@contextmanager
def get_target_connection():
    conn = None
    try:
        conn = mysql.connector.connect(**TARGET_DB_CONFIG)
        logger.info("Target DB connection established.")
        yield conn
    except Error as e:
        logger.critical(f"Failed to connect to target DB: {e}")
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()
            logger.info("Target DB connection closed.")


# ── Tracking Helpers ──────────────────────────────────────────────────────────

def _sync_source_key(outlet_id: int) -> str:
    return f"call_recording_analytics_details_{outlet_id}"


def get_sync_state(cursor, outlet_id: int) -> int:
    """Returns last_inserted_id for this outlet's custom_sync_tracking row (0 if none)."""
    cursor.execute(
        f"SELECT last_inserted_id FROM {SYNC_TABLE} "
        f"WHERE source_table_name = %s AND target_table = %s LIMIT 1",
        (_sync_source_key(outlet_id), TARGET_TABLE),
    )
    row = cursor.fetchone()
    if row:
        last_inserted_id = row[0] if row[0] else 0
        logger.info(f"[outlet={outlet_id}] Resuming from last_inserted_id={last_inserted_id}.")
        return last_inserted_id
    logger.info(f"[outlet={outlet_id}] No tracking record found — starting from id=0.")
    return 0


def checkpoint_last_id(cursor, outlet_id: int, last_id: int) -> None:
    """Persists last_inserted_id mid-sync for resumability on restart."""
    cursor.execute(
        f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
        f"VALUES (%s, %s, NULL, %s) "
        f"ON DUPLICATE KEY UPDATE last_inserted_id = VALUES(last_inserted_id)",
        (_sync_source_key(outlet_id), TARGET_TABLE, last_id),
    )


def finalize_sync_time(cursor, outlet_id: int, sync_time: datetime) -> None:
    """Stamps last_sync_time on full completion and resets last_inserted_id to 0."""
    cursor.execute(
        f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
        f"VALUES (%s, %s, %s, 0) "
        f"ON DUPLICATE KEY UPDATE last_sync_time = VALUES(last_sync_time), last_inserted_id = 0",
        (_sync_source_key(outlet_id), TARGET_TABLE, sync_time),
    )


# ── Core Sync Function ────────────────────────────────────────────────────────

def sync_outlet(src_conn, tgt_conn, outlet_id: int, resume_id: int = 0) -> int:
    """
    Fetches rows with master_outlet_id = outlet_id AND id > resume_id from source
    and INSERT IGNOREs into target in batches.
    Checkpoints last_inserted_id in custom_sync_tracking after each committed batch.
    Returns total rows inserted.
    """
    src_cursor     = src_conn.cursor()
    total_inserted = 0
    last_id        = resume_id
    batch_num      = 0

    try:
        while True:
            batch_num += 1
            src_cursor.execute(_FETCH_QUERY, (outlet_id, last_id, BATCH_SIZE))
            rows = src_cursor.fetchall()
            if not rows:
                logger.info(f"[outlet={outlet_id}] No more rows after id={last_id}. Done.")
                break

            last_id    = rows[-1][0]
            tgt_cursor = tgt_conn.cursor()
            attempt    = 0

            try:
                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        tgt_cursor.executemany(_INSERT_QUERY, rows)
                        checkpoint_last_id(tgt_cursor, outlet_id, last_id)
                        tgt_conn.commit()

                        inserted = tgt_cursor.rowcount if tgt_cursor.rowcount >= 0 else len(rows)
                        total_inserted += inserted
                        logger.info(
                            f"[outlet={outlet_id}] Batch {batch_num:04d} | "
                            f"Fetched: {len(rows)}, Inserted: {inserted} | "
                            f"Total: {total_inserted} | last_id={last_id}"
                        )
                        break

                    except OperationalError as e:
                        tgt_conn.rollback()
                        logger.warning(
                            f"[outlet={outlet_id}] Batch {batch_num:04d} | OperationalError "
                            f"(attempt {attempt}/{MAX_RETRIES}): {e}"
                        )
                        if attempt < MAX_RETRIES:
                            sleep_time = RETRY_BACKOFF ** attempt
                            logger.info(f"Retrying in {sleep_time}s ...")
                            time.sleep(sleep_time)
                            if not tgt_conn.is_connected():
                                tgt_conn.reconnect(attempts=3, delay=2)
                                logger.info("Reconnected to target DB.")
                        else:
                            logger.error(
                                f"[outlet={outlet_id}] Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts. Skipping {len(rows)} rows "
                                f"(id range: {rows[0][0]}-{last_id})."
                            )

                    except DatabaseError as e:
                        tgt_conn.rollback()
                        logger.error(
                            f"[outlet={outlet_id}] Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows (id range: {rows[0][0]}-{last_id})."
                        )
                        break

            finally:
                tgt_cursor.close()

    finally:
        src_cursor.close()

    return total_inserted


# ── Main ──────────────────────────────────────────────────────────────────────

def run_sync():
    if not TARGET_OUTLET_IDS:
        logger.critical("TARGET_OUTLET_IDS is empty. Add master_outlet_ids before running.")
        sys.exit(1)

    logger.info("=" * 65)
    logger.info(f"SYNC JOB STARTED : call_recording_analytics_details for {len(TARGET_OUTLET_IDS)} outlet(s)")
    logger.info(f"  Outlet IDs: {TARGET_OUTLET_IDS}")
    logger.info("=" * 65)

    grand_total       = 0
    failed_ids        = []
    current_sync_time = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        with get_source_connection() as src_conn, get_target_connection() as tgt_conn:
            for outlet_id in TARGET_OUTLET_IDS:
                logger.info("-" * 65)
                logger.info(f"Processing outlet_id={outlet_id}")

                try:
                    with tgt_conn.cursor() as cur:
                        resume_id = get_sync_state(cur, outlet_id)

                    if resume_id:
                        logger.info(f"[outlet={outlet_id}] Resuming interrupted sync from id={resume_id}.")

                    total_inserted = sync_outlet(src_conn, tgt_conn, outlet_id, resume_id)

                    with tgt_conn.cursor() as cur:
                        finalize_sync_time(cur, outlet_id, current_sync_time)
                        tgt_conn.commit()
                        logger.info(f"[outlet={outlet_id}] custom_sync_tracking updated with sync_time={current_sync_time}.")

                    grand_total += total_inserted
                    logger.info(f"[outlet={outlet_id}] Completed — rows inserted: {total_inserted}")

                except Exception as e:
                    logger.error(f"[outlet={outlet_id}] Failed with error: {e}", exc_info=True)
                    failed_ids.append(outlet_id)
                    # Continue to next outlet rather than aborting the whole run

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(
            "Sync interrupted by user (Ctrl+C). "
            "custom_sync_tracking NOT finalized for in-progress outlet — re-run to resume."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("SYNC JOB COMPLETED")
    logger.info(f"  Outlets processed : {len(TARGET_OUTLET_IDS) - len(failed_ids)}/{len(TARGET_OUTLET_IDS)}")
    logger.info(f"  Total inserted    : {grand_total}")
    if failed_ids:
        logger.warning(f"  Failed outlet IDs : {failed_ids}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_sync()
