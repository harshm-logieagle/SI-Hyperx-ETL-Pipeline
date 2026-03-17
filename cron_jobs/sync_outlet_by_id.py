"""
Script: Sync Specific Outlet by ID
Source DB: SI DB (sinterface) — outlets table
Target DB: 10.0.4.194 — brands and outlets tables

Sync Logic:
1. Get last_inserted_id from custom_sync_tracking to support resume on restart.
2. Fetch the master outlet by TARGET_OUTLET_ID from source outlets table
   → upsert into target brands (name = source brand_name, si_master_outlet_id = TARGET_OUTLET_ID).
3. Fetch child outlets (outlet_type IN ('retail','enterprise'), parent_id = TARGET_OUTLET_ID)
   → upsert into target outlets (outlet_raw_id = source outlet id,
     master_outlet_id = target brands id resolved via si_master_outlet_id).
4. Update custom_sync_tracking with sync completion time on success.

Tracking row is keyed on (source_table_name, target_table) where
source_table_name = "outlets_<TARGET_OUTLET_ID>" making each outlet_id unique.
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
        logging.FileHandler("custom_sync_tracking.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("custom_sync_tracking")

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

# ── Configuration ─────────────────────────────────────────────────────────────

# The specific master outlet ID to sync — change this before running
TARGET_OUTLET_ID = 507806  # TODO: set the master outlet id here

BATCH_SIZE    = 1000
MAX_RETRIES   = 3
RETRY_BACKOFF = 2      # Exponential backoff base (seconds)

# Table names — swap to production names when done testing
BRANDS_TABLE  = "brands"
OUTLETS_TABLE = "outlets"
SYNC_TABLE    = "custom_sync_tracking"

# Identifies this job's row in custom_sync_tracking (unique per outlet id)
SYNC_SOURCE_TABLE = f"outlets_{TARGET_OUTLET_ID}"
SYNC_TARGET_TABLE = "outlets"

# ── Column Definitions ────────────────────────────────────────────────────────

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

# Source SELECT for child outlets filtered by a specific parent_id.
# Row layout: [0]=o.id (keyset+outlet_raw_id), [1]=o.parent_id, [2:]=business_name…location_group
_FETCH_CHILD_QUERY = f"""
    SELECT
        o.id,
        o.parent_id,
        {_SRC_OUTLET_COLS_SQL}
    FROM   outlets o
    WHERE  o.outlet_type IN ('retail', 'enterprise')
      AND  o.parent_id   = %s
      AND  o.id          > %s
    ORDER  BY o.id ASC
    LIMIT  %s
"""


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

def get_sync_state(cursor) -> int:
    """Returns last_inserted_id for this job's custom_sync_tracking row (0 if none)."""
    cursor.execute(
        f"SELECT last_inserted_id FROM {SYNC_TABLE} "
        f"WHERE source_table_name = %s AND target_table = %s LIMIT 1",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE),
    )
    row = cursor.fetchone()
    if row:
        last_inserted_id = row[0] if row[0] else 0
        logger.info(f"Resuming from last_inserted_id={last_inserted_id}.")
        return last_inserted_id
    logger.info(
        f"No sync record found for ({SYNC_SOURCE_TABLE}, {SYNC_TARGET_TABLE}). Starting fresh."
    )
    return 0


def update_sync_time(cursor, sync_time: datetime) -> None:
    """Called on full completion — persists last_sync_time and resets last_inserted_id."""
    cursor.execute(
        f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
        f"VALUES (%s, %s, %s, 0) "
        f"ON DUPLICATE KEY UPDATE last_sync_time = VALUES(last_sync_time), last_inserted_id = 0",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, sync_time),
    )


def checkpoint_last_id(cursor, last_id: int) -> None:
    """Persists last_inserted_id mid-sync for resumability on restart."""
    cursor.execute(
        f"INSERT INTO {SYNC_TABLE} (source_table_name, target_table, last_sync_time, last_inserted_id) "
        f"VALUES (%s, %s, NULL, %s) "
        f"ON DUPLICATE KEY UPDATE last_inserted_id = VALUES(last_inserted_id)",
        (SYNC_SOURCE_TABLE, SYNC_TARGET_TABLE, last_id),
    )


# ── Core Sync Functions ───────────────────────────────────────────────────────

def sync_brand(src_conn, tgt_conn, outlet_id: int) -> bool:
    """
    Fetches the master outlet by outlet_id from source and upserts it into target brands.
    Target brands columns used: name (= source brand_name), si_master_outlet_id (= outlet_id).
    Returns True if a brand row was found and processed.
    """
    src_cursor = src_conn.cursor()
    try:
        src_cursor.execute(
            """
            SELECT id, brand_name
            FROM   outlets
            WHERE  id          = %s
              AND  outlet_type = 'master'
              AND  brand_name  IS NOT NULL
            LIMIT  1
            """,
            (outlet_id,),
        )
        row = src_cursor.fetchone()
    finally:
        src_cursor.close()

    if not row:
        logger.error(
            f"Master outlet id={outlet_id} not found in source "
            f"(must exist, outlet_type='master', brand_name NOT NULL)."
        )
        return False

    source_id, brand_name = row

    tgt_cursor = tgt_conn.cursor()
    try:
        tgt_cursor.execute(
            f"SELECT id FROM {BRANDS_TABLE} WHERE si_master_outlet_id = %s LIMIT 1",
            (source_id,),
        )
        existing = tgt_cursor.fetchone()

        attempt = 0
        while attempt < MAX_RETRIES:
            attempt += 1
            try:
                if existing:
                    tgt_cursor.execute(
                        f"UPDATE {BRANDS_TABLE} SET brand_name = %s WHERE si_master_outlet_id = %s",
                        (brand_name, source_id),
                    )
                    logger.info(
                        f"Brand | Updated: brand_name='{brand_name}', si_master_outlet_id={source_id}"
                    )
                else:
                    tgt_cursor.execute(
                        f"INSERT INTO {BRANDS_TABLE} (brand_name, si_master_outlet_id) VALUES (%s, %s)",
                        (brand_name, source_id),
                    )
                    logger.info(
                        f"Brand | Inserted: brand_name='{brand_name}', si_master_outlet_id={source_id}"
                    )
                tgt_conn.commit()
                return True

            except OperationalError as e:
                tgt_conn.rollback()
                logger.warning(f"Brand | OperationalError (attempt {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    sleep_time = RETRY_BACKOFF ** attempt
                    logger.info(f"Retrying in {sleep_time}s ...")
                    time.sleep(sleep_time)
                    if not tgt_conn.is_connected():
                        tgt_conn.reconnect(attempts=3, delay=2)
                        logger.info("Reconnected to target DB.")
                else:
                    logger.error(f"Brand | PERMANENTLY FAILED after {MAX_RETRIES} attempts.")
                    return False

            except DatabaseError as e:
                tgt_conn.rollback()
                logger.error(f"Brand | DatabaseError (non-retriable): {e}")
                return False
    finally:
        tgt_cursor.close()

    return False


def sync_child_outlets(src_conn, tgt_conn, outlet_id: int, resume_id: int = 0) -> int:
    """
    Fetches all child outlets (retail/enterprise) with parent_id = outlet_id from source
    and upserts them into target outlets.
    resume_id: keyset start — resumes from last successfully committed batch on restart.
    master_outlet_id is resolved from target brands via si_master_outlet_id = outlet_id.
    Returns total rows upserted.
    """
    # Resolve target brands.id once — it must exist (sync_brand runs before this)
    tgt_cursor = tgt_conn.cursor()
    try:
        tgt_cursor.execute(
            f"SELECT id FROM {BRANDS_TABLE} WHERE si_master_outlet_id = %s LIMIT 1",
            (outlet_id,),
        )
        brand_row = tgt_cursor.fetchone()
    finally:
        tgt_cursor.close()

    if not brand_row:
        logger.error(
            f"Cannot sync child outlets: brand for si_master_outlet_id={outlet_id} "
            f"not found in target {BRANDS_TABLE}. Run brand sync first."
        )
        return 0

    master_outlet_id = brand_row[0]
    logger.info(f"Resolved target brands.id={master_outlet_id} for outlet_id={outlet_id}.")

    src_cursor = src_conn.cursor()
    total_upserted = 0
    last_id        = resume_id
    batch_num      = 0

    try:
        while True:
            batch_num += 1
            src_cursor.execute(_FETCH_CHILD_QUERY, (outlet_id, last_id, BATCH_SIZE))
            rows = src_cursor.fetchall()
            if not rows:
                break

            # row layout: [0]=o.id, [1]=o.parent_id, [2:]=business_name…location_group
            last_id        = rows[-1][0]
            outlet_raw_ids = [r[0] for r in rows]

            tgt_cursor = tgt_conn.cursor()
            try:
                # Check which outlet_raw_ids already exist in target outlets
                fmt = ", ".join(["%s"] * len(outlet_raw_ids))
                tgt_cursor.execute(
                    f"SELECT outlet_raw_id FROM {OUTLETS_TABLE} WHERE outlet_raw_id IN ({fmt})",
                    outlet_raw_ids,
                )
                existing_raw_ids = {r[0] for r in tgt_cursor.fetchall()}

                to_insert = []
                to_update = []

                for row in rows:
                    outlet_raw_id = row[0]
                    # Build row matching _OUTLET_COLUMNS order:
                    # (master_outlet_id, business_name…location_group, outlet_raw_id)
                    outlet_row = (master_outlet_id, *row[2:], outlet_raw_id)

                    if outlet_raw_id in existing_raw_ids:
                        to_update.append(outlet_row)
                    else:
                        to_insert.append(outlet_row)

                if not to_insert and not to_update:
                    logger.info(f"Outlets Batch {batch_num:04d} | Nothing to upsert, advancing.")
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
                        # Checkpoint: persist last_inserted_id atomically with batch data
                        checkpoint_last_id(tgt_cursor, last_id)
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

                if not batch_succeeded:
                    pass  # Keyset cursor advances regardless to avoid stalling on bad data

            finally:
                tgt_cursor.close()

    finally:
        src_cursor.close()

    return total_upserted


# ── Main ──────────────────────────────────────────────────────────────────────

def run_sync():
    if not TARGET_OUTLET_ID:
        logger.critical("TARGET_OUTLET_ID is not set. Edit the script and set it before running.")
        sys.exit(1)

    logger.info("=" * 65)
    logger.info(f"SYNC JOB STARTED : outlet_id={TARGET_OUTLET_ID} -> brands + outlets")
    logger.info("=" * 65)

    try:
        with get_source_connection() as src_conn, get_target_connection() as tgt_conn:

            with tgt_conn.cursor() as cur:
                resume_id = get_sync_state(cur)

            if resume_id:
                logger.info(f"Resuming interrupted child-outlet sync from id={resume_id}.")

            current_sync_time = datetime.utcnow()

            logger.info("--- Syncing brand ---")
            brand_ok = sync_brand(src_conn, tgt_conn, TARGET_OUTLET_ID)

            if not brand_ok:
                logger.critical(
                    "Brand sync failed — aborting outlet sync to avoid orphaned rows."
                )
                sys.exit(1)

            logger.info("--- Syncing child outlets ---")
            outlets_upserted = sync_child_outlets(
                src_conn, tgt_conn, TARGET_OUTLET_ID, resume_id
            )

            # Update sync time only after both syncs complete successfully
            with tgt_conn.cursor() as cur:
                update_sync_time(cur, current_sync_time)
                tgt_conn.commit()
                logger.info(f"custom_sync_tracking updated to {current_sync_time}.")

    except (OperationalError, InterfaceError) as e:
        logger.critical(f"Critical connection failure: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(
            "Sync interrupted by user (Ctrl+C). "
            "custom_sync_tracking NOT updated — re-run to retry."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("SYNC JOB COMPLETED")
    logger.info(f"  Outlet ID        : {TARGET_OUTLET_ID}")
    logger.info(f"  Outlets upserted : {outlets_upserted}")
    logger.info("=" * 65)


if __name__ == "__main__":
    run_sync()
