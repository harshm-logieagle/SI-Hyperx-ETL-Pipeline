"""
Cron Job: Sync Users
Source DB: SI LIVE DB (sinterface) — users table
Target DB: 10.0.4.194 — users_cron_test table

Sync Logic:
1. Get last_sync_time from cron_tracker table (source='users', target='users_cron_test').
2. Fetch users modified since last_sync_time in batches (keyset pagination on id).
3. Upsert into target users_cron_test:
   - INSERT rows whose id doesn't exist in target yet.
   - UPDATE rows whose id already exists in target.
4. Update cron_tracker with the sync start time on completion.
"""

import mysql.connector
from mysql.connector import Error, OperationalError, DatabaseError, InterfaceError
import logging
import time
import sys
from contextlib import contextmanager
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sync_users.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("SYNC_USERS")

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

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2       # Exponential backoff base (seconds)

# Table names — swap to production names when done testing
USERS_TABLE = "users_cron_test"
SYNC_TABLE  = "cron_tracker"

# Identifies this job's row in cron_tracker
SYNC_SOURCE_TABLE = "users"
SYNC_TARGET_TABLE = "users_cron_test"

# Target users column order — drives INSERT and UPDATE query generation
_USER_COLUMNS = [
    "id", "user_group_id", "username", "facebook_page_id", "password", "salt",
    "alternate_password", "email", "first_name", "last_name", "email_verified",
    "active", "ip_address", "created", "modified", "last_password_reset_date",
    "reset", "parent_id", "user_group_role_alias", "mobile", "franchise_id",
    "user_type", "location_specific", "is_moderator", "circles",
    "is_circle_data_sync", "created_by", "is_brand_moderator", "user_identifier",
    "is_hyperx", "new_dashboard_enabled", "password_plain_text",
    "forgot_password_request_date", "forgot_password_request_count",
    "rest_password_token", "wo_customer_id", "email_verification_token",
    "incorrect_password_count", "incorrect_password_date", "location_user",
    "social_common_user_id", "role", "team_members", "reporting_manager_id",
    "is_dashboard_editable",
]

_SRC_USERS_COLS_SQL = ", ".join(_USER_COLUMNS)

INSERT_USER_QUERY = "INSERT INTO {} ({}) VALUES ({})".format(
    USERS_TABLE,
    ", ".join(_USER_COLUMNS),
    ", ".join(["%s"] * len(_USER_COLUMNS)),
)

# SET uses all columns except id (index 0); id is the WHERE key (last tuple value)
UPDATE_USER_QUERY = "UPDATE {} SET {} WHERE id = %s".format(
    USERS_TABLE,
    ", ".join(f"`{col}` = %s" for col in _USER_COLUMNS[1:]),
)

_FETCH_USERS_QUERY = f"""
    SELECT {_SRC_USERS_COLS_SQL}
    FROM   users
    WHERE  modified > %s
      AND  id > %s
    ORDER  BY id ASC
    LIMIT  %s
"""


# ── Connection Context Managers ──────────────────────────────────────────────

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


# ── Sync Time Helpers ────────────────────────────────────────────────────────

def get_sync_state(cursor) -> tuple:
    """Returns (last_sync_time, last_inserted_id) for this job's cron_tracker row."""
    cursor.execute(
        f"SELECT last_sync_time, last_inserted_id FROM {SYNC_TABLE} "
        f"WHERE source_table_name = %s AND target_table = %s LIMIT 1",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
    )
    row = cursor.fetchone()
    if row:
        last_sync_time   = row[0] if row[0] else datetime(2000, 1, 1)
        last_inserted_id = row[1] if row[1] else 0
        logger.info(f"Resuming from last_sync_time={last_sync_time}, last_inserted_id={last_inserted_id}.")
        return last_sync_time, last_inserted_id
    fallback = datetime(2000, 1, 1)
    logger.info(f"No sync record found for ({SYNC_SOURCE_TABLE}, {SYNC_TARGET_TABLE}). Defaulting to {fallback}.")
    return fallback, 0


def update_sync_time(cursor, sync_time: datetime) -> None:
    """Called on full completion — persists last_sync_time and resets last_inserted_id."""
    cursor.execute(
        f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
        f"VALUES (%s, %s, %s, 0) "
        f"ON DUPLICATE KEY UPDATE last_sync_time = VALUES(last_sync_time), last_inserted_id = 0",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, sync_time),
    )


# ── Core Sync Function ───────────────────────────────────────────────────────

def sync_users(src_conn, tgt_conn, last_sync_time: datetime, resume_id: int = 0) -> int:
    """
    Fetches users modified since last_sync_time and upserts them into target users_cron_test.
    resume_id: keyset start — resumes from last successfully committed batch on restart.
    Returns total rows upserted.
    """
    src_cursor = src_conn.cursor()
    total_upserted = 0
    last_id        = resume_id
    batch_num      = 0

    try:
        while True:
            batch_num += 1
            src_cursor.execute(_FETCH_USERS_QUERY, (last_sync_time, last_id, BATCH_SIZE))
            rows = src_cursor.fetchall()
            if not rows:
                break

            # row layout matches _USER_COLUMNS: [0]=id, [1]=user_group_id, ...
            last_id    = rows[-1][0]
            source_ids = [r[0] for r in rows]

            tgt_cursor = tgt_conn.cursor()
            try:
                fmt = ", ".join(["%s"] * len(source_ids))
                tgt_cursor.execute(
                    f"SELECT id FROM {USERS_TABLE} WHERE id IN ({fmt})",
                    source_ids,
                )
                existing_ids = {r[0] for r in tgt_cursor.fetchall()}

                to_insert = [row for row in rows if row[0] not in existing_ids]
                # UPDATE tuple: (non-id cols..., id) — id goes last for the WHERE clause
                to_update = [(*row[1:], row[0]) for row in rows if row[0] in existing_ids]

                if not to_insert and not to_update:
                    continue

                attempt = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        if to_insert:
                            tgt_cursor.executemany(INSERT_USER_QUERY, to_insert)
                        if to_update:
                            tgt_cursor.executemany(UPDATE_USER_QUERY, to_update)
                        # Checkpoint: persist last_inserted_id atomically with batch data
                        tgt_cursor.execute(
                            f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
                            f"VALUES (%s, %s, NULL, %s) "
                            f"ON DUPLICATE KEY UPDATE last_inserted_id = VALUES(last_inserted_id)",
                            (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, last_id),
                        )
                        tgt_conn.commit()
                        upserted = len(to_insert) + len(to_update)
                        total_upserted += upserted
                        logger.info(
                            f"Users Batch {batch_num:04d} | "
                            f"Inserted {len(to_insert)}, Updated {len(to_update)} | "
                            f"Total upserted: {total_upserted} | last_inserted_id={last_id}"
                        )
                        batch_succeeded = True
                        break

                    except OperationalError as e:
                        tgt_conn.rollback()
                        logger.warning(
                            f"Users Batch {batch_num:04d} | OperationalError "
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
                                f"Users Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts. "
                                f"Skipping {len(rows)} rows "
                                f"(source id range: {rows[0][0]}-{last_id})."
                            )

                    except DatabaseError as e:
                        tgt_conn.rollback()
                        logger.error(
                            f"Users Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(source id range: {rows[0][0]}-{last_id})."
                        )
                        break

                if not batch_succeeded:
                    pass  # Keyset cursor advances regardless to avoid stalling on bad data

            finally:
                tgt_cursor.close()

    finally:
        src_cursor.close()

    return total_upserted


# ── Main ─────────────────────────────────────────────────────────────────────

def run_sync():
    logger.info("=" * 65)
    logger.info("SYNC JOB STARTED : users -> users_cron_test")
    logger.info("=" * 65)

    try:
        with get_source_connection() as src_conn, get_target_connection() as tgt_conn:

            with tgt_conn.cursor() as cur:
                last_sync_time, resume_id = get_sync_state(cur)

            if resume_id:
                logger.info(f"Resuming interrupted sync from id={resume_id}.")

            # Capture sync start time before fetching so records modified during
            # this run are safely picked up by the next run
            current_sync_time = datetime.utcnow()

            logger.info("--- Syncing users ---")
            users_upserted = sync_users(src_conn, tgt_conn, last_sync_time, resume_id)

            # Update sync time only after sync completes successfully
            with tgt_conn.cursor() as cur:
                update_sync_time(cur, current_sync_time)
                tgt_conn.commit()
                logger.info(f"cron_tracker updated to {current_sync_time}.")

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(
            "Sync interrupted by user (Ctrl+C). "
            "cron_tracker NOT updated — re-run to retry."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("SYNC JOB COMPLETED")
    logger.info(f"  Users upserted : {users_upserted}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_sync()
