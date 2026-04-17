"""
Cron Job: Sync Outlets
Source DB: SI DB (sinterface) — outlets table
Target DB: 10.0.4.194 — brands and outlets tables

Sync Logic:
1. Get last_sync_time from target cron_tracker table.
2. Master outlets (brand_name IS NOT NULL, outlet_type = 'master', modified > last_sync_time)
   → upsert into target brands (si_master_outlet_id = source outlet id).
3. Child outlets (outlet_type IN ('retail','enterprise'), modified > last_sync_time,
   parent_id references a master outlet) → upsert into target outlets
   (outlet_raw_id = source outlet id, master_outlet_id = target brands id).
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
        logging.FileHandler("cron_tracker.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("cron_tracker")

SOURCE_DB_CONFIG = {
    "host": "bi-googlereadreplica.c83fh8gbkqpw.ap-south-1.rds.amazonaws.com",
    "port": 3306,
    "user": "adarsh",
    "password": "XmbUd$5&haL&5^d*s#!2@",
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
BRANDS_TABLE  = "brands"
OUTLETS_TABLE = "outlets"
SYNC_TABLE    = "cron_tracker"

# Identifies this job's row in cron_tracker
SYNC_SOURCE_TABLE = "outlets"
SYNC_TARGET_TABLE = "outlets"

# Target outlets column order — drives INSERT and UPDATE query generation
_OUTLET_COLUMNS = [
    "master_outlet_id", "business_name", "url_alias", "joiningplan_id", "order_planid",
    "customer_id", "partner_id", "salesperson_id", "order_id", "category_id",
    "alternative_name", "business_email", "company_tagline", "location", "location_alias",
    "phone", "alternative_phone", "mobile_number", "tty_number", "country_id",
    "iso_alpha_2", "state_id", "city_id", "country", "circle", "circle_alias",
    "state", "state_alias", "city", "city_alias", "address", "address_2", "landmark",
    "zip", "website", "latitude", "longitude", "geo_coded_latitude", "geo_coded_longitude",
    "contact_person_name", "contact_person_designation", "contact_person_email",
    "contact_person_number", "toll_free_number", "fax_no", "facebook_page_url",
    "twitter_handle", "googleplus_url", "year_of_establishment", "brands_carried",
    "description", "short_description", "special_offer", "special_offer_url", "tags",
    "business_hours", "logo", "logo_from_csv", "logo_dir", "fav_icon", "fav_icon_dir",
    "copyright", "facebook_cover_photo", "facebook_cover_dir",
    "facebook_cover_photo_allow_publishing", "facebook_profile_photo",
    "facebook_profile_dir", "facebook_profile_photo_allow_publishing",
    "facebook_profile_photo_publishing_flag", "facebook_cover_photo_publishing_flag",
    "fb_cover_alt_text", "fb_cover_title_text", "meta_title", "meta_keyword",
    "meta_additional_keywords", "meta_description", "page_theme",
    "redirect_to_customer_website", "can_redirect_store_locator_to_client_website",
    "redirect_store_locator_to_client_website", "created", "modified",
    "outlet_id_from_csv", "state_code", "is_exists_in_publisher_data_table", "parent_id",
    "ga_tracking_id", "ga_account_id", "amp_ga_account_id", "mailer_trigger_id",
    "mailer_ml_id", "ga_tracking_script", "enterprise_client_id",
    "enterprise_client_store_id", "enterprise_actual_client_store_id", "lat_long_verify",
    "lat_long_verify_ip", "lat_long_verify_date", "lat_long_qc_pending",
    "enterprise_verifylatlong_emaildate", "facebook_profile_picture_url",
    "facebook_cover_photo_url", "youtube_channel_url", "pinterest", "instagram",
    "outlet_type", "brand_store_locator_name", "brand_website",
    "facebook_page_national_url", "google_plus_page_national_url",
    "google_play_store_national_url", "ios_app_store_national_url", "client_website",
    "toll_free_number_national", "brand_name", "buy_online_url", "category_feed_url",
    "category_feed_last_modified", "product_feed_url", "product_feed_last_modified",
    "ga_email_id", "ga_key", "ga_profile_id", "ga4_account_id", "amp_ga4_account_id",
    "amp_ga_email_id", "amp_ga_key", "amp_ga_profile_id", "google_account_name",
    "save_and_publish_flag", "close_outlet", "delete_outlet", "facebook_page_id",
    "facebook_page_name", "store_locator_search_type", "lead_form_type",
    "store_locator_search_type_responsive", "restaurant_order_types",
    "recaptcha_site_key", "recaptcha_secret_key", "schema_local_business_type",
    "add_website_to_webmaster", "can_use_one_page_css", "fetch_css_from_client_domain",
    "services", "amp_analytic_account", "hastag", "external_links",
    "is_website_hosted_on_client_side", "client_api_auth_key", "is_company_retail_store",
    "ifsc_code", "weekly_off", "url_alias_backup", "outlet_logo_url",
    "outlet_fav_icon_url", "outlet_cover_photo_url", "master_page_theme",
    "menu_category_name", "menu_category_id", "menu_category_alias", "custom_state",
    "custom_state_alias", "custom_city", "custom_city_alias", "custom_locality",
    "api_client_id", "api_custom_name", "api_phone_number", "location_group",
    "outlet_raw_id",
]

# Source columns to SELECT for child outlets (all except master_outlet_id and outlet_raw_id)
_SRC_OUTLET_COLS_SQL = ", ".join(f"o.{col}" for col in _OUTLET_COLUMNS[1:-1])

INSERT_OUTLET_QUERY = "INSERT INTO {} ({}) VALUES ({})".format(
    OUTLETS_TABLE,
    ", ".join(_OUTLET_COLUMNS),
    ", ".join(["%s"] * len(_OUTLET_COLUMNS)),
)

# SET uses all columns except outlet_raw_id; outlet_raw_id is the WHERE key (last tuple value)
UPDATE_OUTLET_QUERY = "UPDATE {} SET {} WHERE outlet_raw_id = %s".format(
    OUTLETS_TABLE,
    ", ".join(f"`{col}` = %s" for col in _OUTLET_COLUMNS[:-1]),
)

# Source SELECT for child outlets.
# Row layout: [0]=o.id (keyset+outlet_raw_id), [1]=o.parent_id, [2:]=business_name…location_group
_FETCH_CHILD_QUERY = f"""
    SELECT
        o.id,
        o.parent_id,
        {_SRC_OUTLET_COLS_SQL}
    FROM   outlets o
    JOIN   outlets m
           ON  m.id          = o.parent_id
           AND m.outlet_type = 'master'
           AND m.brand_name  IS NOT NULL
    WHERE  o.outlet_type IN ('retail', 'enterprise')
      AND  o.modified > %s
      AND  o.id > %s
    ORDER  BY o.id ASC
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
        # Avoid is_connected() here: it pings the server, which raises
        # IndexError on a socket left in a bad state (e.g. after KeyboardInterrupt
        # mid-query) and masks the original exception.
        if conn is not None:
            try:
                conn.close()
                logger.info("Source DB connection closed.")
            except Exception as close_err:
                logger.warning(f"Error while closing source DB connection: {close_err}")


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
        if conn is not None:
            try:
                conn.close()
                logger.info("Target DB connection closed.")
            except Exception as close_err:
                logger.warning(f"Error while closing target DB connection: {close_err}")


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
    """Called on full completion — persists last_sync_time and resets last_inserted_id.

    SELECT-then-UPDATE-or-INSERT: works without a unique key on
    (source_table_name, target_table), avoiding duplicate rows when the
    ON DUPLICATE KEY clause would otherwise silently insert.
    """
    cursor.execute(
        f"SELECT 1 FROM {SYNC_TABLE} "
        f"WHERE source_table_name = %s AND target_table = %s LIMIT 1",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
    )
    if cursor.fetchone():
        cursor.execute(
            f"UPDATE {SYNC_TABLE} "
            f"SET last_sync_time = %s, last_inserted_id = 0 "
            f"WHERE source_table_name = %s AND target_table = %s",
            (sync_time, SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
        )
    else:
        cursor.execute(
            f"INSERT INTO {SYNC_TABLE} "
            f"(source_table_name, target_table, last_sync_time, last_inserted_id) "
            f"VALUES (%s, %s, %s, 0)",
            (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, sync_time),
        )


# ── Core Sync Functions ──────────────────────────────────────────────────────

def sync_brands(src_conn, tgt_conn, last_sync_time: datetime) -> int:
    """
    Fetches master outlets modified since last_sync_time and upserts them into target brands.
    Returns total rows upserted.
    """
    src_cursor = src_conn.cursor()
    total_upserted = 0
    last_id = 0
    batch_num = 0

    try:
        while True:
            batch_num += 1
            src_cursor.execute(
                """
                SELECT id, brand_name
                FROM   outlets
                WHERE  outlet_type = 'master'
                  AND  brand_name IS NOT NULL
                  AND  modified > %s
                  AND  id > %s
                ORDER  BY id ASC
                LIMIT  %s
                """,
                (last_sync_time, last_id, BATCH_SIZE),
            )
            rows = src_cursor.fetchall()
            if not rows:
                break

            last_id    = rows[-1][0]
            source_ids = [r[0] for r in rows]

            tgt_cursor = tgt_conn.cursor()
            try:
                fmt = ", ".join(["%s"] * len(source_ids))
                tgt_cursor.execute(
                    f"SELECT si_master_outlet_id, brand_name FROM {BRANDS_TABLE} "
                    f"WHERE si_master_outlet_id IN ({fmt})",
                    source_ids,
                )
                # Map source id → current target brand_name, so unchanged rows can be skipped.
                # Post-migration, most rows will be identical; issuing UPDATEs for them is
                # what stalled the fresh sync long enough to require a KeyboardInterrupt.
                existing_map = {r[0]: r[1] for r in tgt_cursor.fetchall()}

                to_insert  = []
                to_update  = []
                unchanged  = 0
                for r in rows:
                    source_id, brand_name = r[0], r[1]
                    if source_id not in existing_map:
                        to_insert.append((brand_name, source_id))
                    elif existing_map[source_id] != brand_name:
                        to_update.append((brand_name, source_id))
                    else:
                        unchanged += 1

                attempt = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        if to_insert:
                            tgt_cursor.executemany(
                                f"INSERT INTO {BRANDS_TABLE} (brand_name, si_master_outlet_id) VALUES (%s, %s)",
                                to_insert,
                            )
                        if to_update:
                            tgt_cursor.executemany(
                                f"UPDATE {BRANDS_TABLE} SET brand_name = %s WHERE si_master_outlet_id = %s",
                                to_update,
                            )
                        tgt_conn.commit()
                        upserted = len(to_insert) + len(to_update)
                        total_upserted += upserted
                        logger.info(
                            f"Brands Batch {batch_num:04d} | "
                            f"Inserted {len(to_insert)}, Updated {len(to_update)}, "
                            f"Unchanged (skipped) {unchanged} | "
                            f"Total upserted: {total_upserted}"
                        )
                        batch_succeeded = True
                        break

                    except OperationalError as e:
                        tgt_conn.rollback()
                        logger.warning(
                            f"Brands Batch {batch_num:04d} | OperationalError "
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
                                f"Brands Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts. "
                                f"Skipping {len(rows)} rows "
                                f"(source id range: {rows[0][0]}-{last_id})."
                            )

                    except DatabaseError as e:
                        tgt_conn.rollback()
                        logger.error(
                            f"Brands Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
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


def cron_tracker(src_conn, tgt_conn, last_sync_time: datetime, resume_id: int = 0) -> int:
    """
    Fetches child outlets modified since last_sync_time and upserts them into target outlets.
    resume_id: keyset start — resumes from last successfully committed batch on restart.
    master_outlet_id is resolved from target brands via si_master_outlet_id = source parent_id.
    Rows whose parent brand is not yet in target are skipped with a warning.
    Returns total rows upserted.
    """
    src_cursor = src_conn.cursor()
    total_upserted = 0
    total_skipped  = 0
    last_id        = resume_id
    batch_num      = 0

    try:
        while True:
            batch_num += 1
            src_cursor.execute(_FETCH_CHILD_QUERY, (last_sync_time, last_id, BATCH_SIZE))
            rows = src_cursor.fetchall()
            if not rows:
                break

            # row layout: [0]=o.id, [1]=o.parent_id, [2:]=business_name…location_group
            last_id    = rows[-1][0]
            parent_ids = list({r[1] for r in rows})

            tgt_cursor = tgt_conn.cursor()
            try:
                # Resolve target brands.id for each unique parent_id in this batch
                fmt = ", ".join(["%s"] * len(parent_ids))
                tgt_cursor.execute(
                    f"SELECT id, si_master_outlet_id FROM {BRANDS_TABLE} WHERE si_master_outlet_id IN ({fmt})",
                    parent_ids,
                )
                master_id_map = {r[1]: r[0] for r in tgt_cursor.fetchall()}

                # Check which outlet_raw_ids already exist in target outlets
                outlet_raw_ids = [r[0] for r in rows]
                fmt2 = ", ".join(["%s"] * len(outlet_raw_ids))
                tgt_cursor.execute(
                    f"SELECT outlet_raw_id FROM {OUTLETS_TABLE} WHERE outlet_raw_id IN ({fmt2})",
                    outlet_raw_ids,
                )
                existing_raw_ids = {r[0] for r in tgt_cursor.fetchall()}

                to_insert = []
                to_update = []

                for row in rows:
                    outlet_raw_id    = row[0]
                    parent_id        = row[1]
                    master_outlet_id = master_id_map.get(parent_id)

                    if master_outlet_id is None:
                        # Parent brand not synced to target yet; will be caught in the next run
                        logger.warning(
                            f"Skipping outlet id={outlet_raw_id}: "
                            f"brand for parent_id={parent_id} not found in target brands."
                        )
                        total_skipped += 1
                        continue

                    # Build row matching _OUTLET_COLUMNS order:
                    # (master_outlet_id, business_name…location_group, outlet_raw_id)
                    outlet_row = (master_outlet_id, *row[2:], outlet_raw_id)

                    if outlet_raw_id in existing_raw_ids:
                        to_update.append(outlet_row)
                    else:
                        to_insert.append(outlet_row)

                if not to_insert and not to_update:
                    continue

                attempt = 0
                batch_succeeded = False

                while attempt < MAX_RETRIES:
                    attempt += 1
                    try:
                        if to_insert:
                            tgt_cursor.executemany(INSERT_OUTLET_QUERY, to_insert)
                        if to_update:
                            # Tuple layout for UPDATE: (master_outlet_id, …cols…, outlet_raw_id)
                            # First N-1 values → SET clause; last value → WHERE outlet_raw_id
                            tgt_cursor.executemany(UPDATE_OUTLET_QUERY, to_update)
                        # Checkpoint: persist last_inserted_id atomically with batch data.
                        # SELECT-then-UPDATE-or-INSERT: if a tracker row already exists for
                        # this (source, target), just bump last_inserted_id; otherwise create it.
                        tgt_cursor.execute(
                            f"SELECT 1 FROM {SYNC_TABLE} "
                            f"WHERE source_table_name = %s AND target_table = %s LIMIT 1",
                            (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
                        )
                        if tgt_cursor.fetchone():
                            tgt_cursor.execute(
                                f"UPDATE {SYNC_TABLE} "
                                f"SET last_inserted_id = %s "
                                f"WHERE source_table_name = %s AND target_table = %s",
                                (last_id, SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
                            )
                        else:
                            tgt_cursor.execute(
                                f"INSERT INTO {SYNC_TABLE} "
                                f"(source_table_name, target_table, last_sync_time, last_inserted_id) "
                                f"VALUES (%s, %s, NULL, %s)",
                                (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, last_id),
                            )
                        tgt_conn.commit()
                        upserted = len(to_insert) + len(to_update)
                        total_upserted += upserted
                        logger.info(
                            f"Outlets Batch {batch_num:04d} | "
                            f"Inserted {len(to_insert)}, Updated {len(to_update)} | "
                            f"Total upserted: {total_upserted} | last_inserted_id={last_id}"
                        )
                        batch_succeeded = True
                        break

                    except OperationalError as e:
                        tgt_conn.rollback()
                        logger.warning(
                            f"Outlets Batch {batch_num:04d} | OperationalError "
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
                                f"Outlets Batch {batch_num:04d} | PERMANENTLY FAILED "
                                f"after {MAX_RETRIES} attempts. "
                                f"Skipping {len(rows)} rows "
                                f"(source id range: {rows[0][0]}-{last_id})."
                            )

                    except DatabaseError as e:
                        tgt_conn.rollback()
                        logger.error(
                            f"Outlets Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(source id range: {rows[0][0]}-{last_id})."
                        )
                        break

            finally:
                tgt_cursor.close()

    finally:
        src_cursor.close()

    if total_skipped:
        logger.warning(f"Outlets sync: {total_skipped} rows skipped (unresolved parent brands).")

    return total_upserted


# ── Main ─────────────────────────────────────────────────────────────────────

def run_sync():
    logger.info("=" * 65)
    logger.info("SYNC JOB STARTED : outlets -> brands + outlets")
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

            logger.info("--- Syncing brands ---")
            brands_upserted = sync_brands(src_conn, tgt_conn, last_sync_time)

            logger.info("--- Syncing outlets ---")
            outlets_upserted = cron_tracker(src_conn, tgt_conn, last_sync_time, resume_id)

            # Update sync time only after both syncs complete successfully
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
    logger.info(f"  Brands upserted  : {brands_upserted}")
    logger.info(f"  Outlets upserted : {outlets_upserted}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_sync()
