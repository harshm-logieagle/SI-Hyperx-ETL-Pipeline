"""
ETL Pipeline for Outlets
Raw Query (Attached Below): 
INSERT INTO outlets (
    master_outlet_id, business_name, url_alias, joiningplan_id, order_planid, customer_id, partner_id, salesperson_id, order_id, category_id, alternative_name, business_email, 
    company_tagline, location, location_alias, phone, alternative_phone, mobile_number, tty_number, country_id, iso_alpha_2, state_id, city_id, country, circle, 
    circle_alias, state, state_alias, city, city_alias, address, address_2, landmark, zip, website, latitude, longitude, geo_coded_latitude, geo_coded_longitude, 
    contact_person_name, contact_person_designation, contact_person_email, contact_person_number, toll_free_number, fax_no, facebook_page_url, twitter_handle, 
    googleplus_url, year_of_establishment, brands_carried, description, short_description, special_offer, special_offer_url, tags, business_hours, logo, logo_from_csv, 
    logo_dir, fav_icon, fav_icon_dir, copyright, facebook_cover_photo, facebook_cover_dir, facebook_cover_photo_allow_publishing, facebook_profile_photo, 
    facebook_profile_dir, facebook_profile_photo_allow_publishing, facebook_profile_photo_publishing_flag, facebook_cover_photo_publishing_flag, fb_cover_alt_text, 
    fb_cover_title_text, meta_title, meta_keyword, meta_additional_keywords, meta_description, page_theme, redirect_to_customer_website, 
    can_redirect_store_locator_to_client_website, redirect_store_locator_to_client_website, created, modified, outlet_id_from_csv, state_code, 
    is_exists_in_publisher_data_table, parent_id, ga_tracking_id, ga_account_id, amp_ga_account_id, mailer_trigger_id, mailer_ml_id, ga_tracking_script, 
    enterprise_client_id, enterprise_client_store_id, enterprise_actual_client_store_id, lat_long_verify, lat_long_verify_ip, lat_long_verify_date, 
    lat_long_qc_pending, enterprise_verifylatlong_emaildate, facebook_profile_picture_url, facebook_cover_photo_url, youtube_channel_url, pinterest, 
    instagram, outlet_type, brand_store_locator_name, brand_website, facebook_page_national_url, google_plus_page_national_url, google_play_store_national_url, 
    ios_app_store_national_url, client_website, toll_free_number_national, brand_name, buy_online_url, category_feed_url, category_feed_last_modified, 
    product_feed_url, product_feed_last_modified, ga_email_id, ga_key, ga_profile_id, ga4_account_id, amp_ga4_account_id, amp_ga_email_id, amp_ga_key, 
    amp_ga_profile_id, google_account_name, save_and_publish_flag, close_outlet, delete_outlet, facebook_page_id, facebook_page_name, store_locator_search_type, 
    lead_form_type, store_locator_search_type_responsive, restaurant_order_types, recaptcha_site_key, recaptcha_secret_key, schema_local_business_type, 
    add_website_to_webmaster, can_use_one_page_css, fetch_css_from_client_domain, services, amp_analytic_account, hastag, external_links, 
    is_website_hosted_on_client_side, client_api_auth_key, is_company_retail_store, ifsc_code, weekly_off, url_alias_backup, outlet_logo_url, outlet_fav_icon_url, 
    outlet_cover_photo_url, master_page_theme, menu_category_name, menu_category_id, menu_category_alias, custom_state, custom_state_alias, custom_city, custom_city_alias, 
    custom_locality, api_client_id, api_custom_name, api_phone_number, location_group, outlet_raw_id
)
SELECT
    b.id AS master_outlet_id, c.business_name, c.url_alias, c.joiningplan_id, c.order_planid, c.customer_id, c.partner_id, c.salesperson_id, c.order_id, c.category_id, c.alternative_name, 
    c.business_email, c.company_tagline, c.location, c.location_alias, c.phone, c.alternative_phone, c.mobile_number, c.tty_number, c.country_id, c.iso_alpha_2, 
    c.state_id, c.city_id, c.country, c.circle, c.circle_alias, c.state, c.state_alias, c.city, c.city_alias, c.address, c.address_2, c.landmark, c.zip, c.website, 
    c.latitude, c.longitude, c.geo_coded_latitude, c.geo_coded_longitude, c.contact_person_name, c.contact_person_designation, c.contact_person_email, 
    c.contact_person_number, c.toll_free_number, c.fax_no, c.facebook_page_url, c.twitter_handle, c.googleplus_url, c.year_of_establishment, c.brands_carried, 
    c.description, c.short_description, c.special_offer, c.special_offer_url, c.tags, c.business_hours, c.logo, c.logo_from_csv, c.logo_dir, c.fav_icon, c.fav_icon_dir, 
    c.copyright, c.facebook_cover_photo, c.facebook_cover_dir, c.facebook_cover_photo_allow_publishing, c.facebook_profile_photo, c.facebook_profile_dir, 
    c.facebook_profile_photo_allow_publishing, c.facebook_profile_photo_publishing_flag, c.facebook_cover_photo_publishing_flag, c.fb_cover_alt_text, 
    c.fb_cover_title_text, c.meta_title, c.meta_keyword, c.meta_additional_keywords, c.meta_description, c.page_theme, c.redirect_to_customer_website, 
    c.can_redirect_store_locator_to_client_website, c.redirect_store_locator_to_client_website, c.created, c.modified, c.outlet_id_from_csv, c.state_code, 
    c.is_exists_in_publisher_data_table, c.parent_id, c.ga_tracking_id, c.ga_account_id, c.amp_ga_account_id, c.mailer_trigger_id, c.mailer_ml_id, c.ga_tracking_script, 
    c.enterprise_client_id, c.enterprise_client_store_id, c.enterprise_actual_client_store_id, c.lat_long_verify, c.lat_long_verify_ip, c.lat_long_verify_date, 
    c.lat_long_qc_pending, c.enterprise_verifylatlong_emaildate, c.facebook_profile_picture_url, c.facebook_cover_photo_url, c.youtube_channel_url, c.pinterest, 
    c.instagram, c.outlet_type, c.brand_store_locator_name, c.brand_website, c.facebook_page_national_url, c.google_plus_page_national_url, 
    c.google_play_store_national_url, c.ios_app_store_national_url, c.client_website, c.toll_free_number_national, c.brand_name, c.buy_online_url, c.category_feed_url, 
    c.category_feed_last_modified, c.product_feed_url, c.product_feed_last_modified, c.ga_email_id, c.ga_key, c.ga_profile_id, c.ga4_account_id, c.amp_ga4_account_id, 
    c.amp_ga_email_id, c.amp_ga_key, c.amp_ga_profile_id, c.google_account_name, c.save_and_publish_flag, c.close_outlet, c.delete_outlet, c.facebook_page_id, 
    c.facebook_page_name, c.store_locator_search_type, c.lead_form_type, c.store_locator_search_type_responsive, c.restaurant_order_types, c.recaptcha_site_key, 
    c.recaptcha_secret_key, c.schema_local_business_type, c.add_website_to_webmaster, c.can_use_one_page_css, c.fetch_css_from_client_domain, c.services, 
    c.amp_analytic_account, c.hastag, c.external_links, c.is_website_hosted_on_client_side, c.client_api_auth_key, c.is_company_retail_store, c.ifsc_code, 
    c.weekly_off, c.url_alias_backup, c.outlet_logo_url, c.outlet_fav_icon_url, c.outlet_cover_photo_url, c.master_page_theme, c.menu_category_name, c.menu_category_id, 
    c.menu_category_alias, c.custom_state, c.custom_state_alias, c.custom_city, c.custom_city_alias, c.custom_locality, c.api_client_id, c.api_custom_name, 
    c.api_phone_number, c.location_group, c.id
FROM outlets_raw c
JOIN outlets_raw m ON c.parent_id = m.id AND m.outlet_type = 'master'
JOIN brands b ON b.brand_name COLLATE utf8mb4_unicode_ci = m.brand_name COLLATE utf8mb4_unicode_ci
WHERE c.outlet_type IN ('retail','enterprise');
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

SCRIPT_NAME = "outlets"

# Logging Configuration
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_outlets.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ETL_OUTLETS")

# Configuration
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
RETRY_BACKOFF = 2       # Exponential backoff base (seconds)

SOURCE_TABLE  = "outlets_raw"
TARGET_TABLE  = "outlets"

# ── Pre-built INSERT with 171 placeholders (generated, not hard-coded) ────────
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

INSERT_QUERY = """
    INSERT INTO outlets ({columns})
    VALUES ({placeholders})
""".format(
    columns=", ".join(_OUTLET_COLUMNS),
    placeholders=", ".join(["%s"] * len(_OUTLET_COLUMNS)),
)

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
    last_processed_id     -> last outlets.id inserted       (target cursor)
    last_processed_id_raw -> last outlets_raw.id processed   (source keyset cursor)
    Returns (0, 0) on a fresh run.
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
            f"Checkpoint found -- "
            f"outlets.id (last_processed_id) = {row[0]} | "
            f"outlets_raw.id (last_processed_id_raw) = {row[1]}"
        )
        return row[0], row[1]
    logger.info("No checkpoint found -- starting fresh from id = 0.")
    return 0, 0

# Core ETL Helpers
def get_total_count(cursor) -> int:
    """
    Mirrors the WHERE + JOIN logic of the main SELECT
    so the progress % stays accurate.
    """
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM   outlets_raw c
        JOIN   outlets_raw m
               ON  c.parent_id    = m.id
               AND m.outlet_type  = 'master'
        JOIN   brands b
               ON  b.brand_name COLLATE utf8mb4_unicode_ci
                 = m.brand_name COLLATE utf8mb4_unicode_ci
        WHERE  c.outlet_type IN ('retail', 'enterprise')
        """
    )
    return cursor.fetchone()[0]

def fetch_batch(cursor, last_raw_id: int, batch_size: int) -> list:
    """
    Keyset pagination on c.id (outlets_raw PK).
    Last column in SELECT is c.id aliased as outlet_raw_id —
    used both as the INSERT value and as the next-page cursor.
    """
    cursor.execute(
        """
        SELECT
            b.id,                               -- master_outlet_id
            c.business_name, c.url_alias, c.joiningplan_id, c.order_planid,
            c.customer_id, c.partner_id, c.salesperson_id, c.order_id, c.category_id,
            c.alternative_name, c.business_email, c.company_tagline, c.location,
            c.location_alias, c.phone, c.alternative_phone, c.mobile_number,
            c.tty_number, c.country_id, c.iso_alpha_2, c.state_id, c.city_id,
            c.country, c.circle, c.circle_alias, c.state, c.state_alias, c.city,
            c.city_alias, c.address, c.address_2, c.landmark, c.zip, c.website,
            c.latitude, c.longitude, c.geo_coded_latitude, c.geo_coded_longitude,
            c.contact_person_name, c.contact_person_designation,
            c.contact_person_email, c.contact_person_number, c.toll_free_number,
            c.fax_no, c.facebook_page_url, c.twitter_handle, c.googleplus_url,
            c.year_of_establishment, c.brands_carried, c.description,
            c.short_description, c.special_offer, c.special_offer_url, c.tags,
            c.business_hours, c.logo, c.logo_from_csv, c.logo_dir, c.fav_icon,
            c.fav_icon_dir, c.copyright, c.facebook_cover_photo, c.facebook_cover_dir,
            c.facebook_cover_photo_allow_publishing, c.facebook_profile_photo,
            c.facebook_profile_dir, c.facebook_profile_photo_allow_publishing,
            c.facebook_profile_photo_publishing_flag,
            c.facebook_cover_photo_publishing_flag, c.fb_cover_alt_text,
            c.fb_cover_title_text, c.meta_title, c.meta_keyword,
            c.meta_additional_keywords, c.meta_description, c.page_theme,
            c.redirect_to_customer_website,
            c.can_redirect_store_locator_to_client_website,
            c.redirect_store_locator_to_client_website, c.created, c.modified,
            c.outlet_id_from_csv, c.state_code, c.is_exists_in_publisher_data_table,
            c.parent_id, c.ga_tracking_id, c.ga_account_id, c.amp_ga_account_id,
            c.mailer_trigger_id, c.mailer_ml_id, c.ga_tracking_script,
            c.enterprise_client_id, c.enterprise_client_store_id,
            c.enterprise_actual_client_store_id, c.lat_long_verify,
            c.lat_long_verify_ip, c.lat_long_verify_date, c.lat_long_qc_pending,
            c.enterprise_verifylatlong_emaildate, c.facebook_profile_picture_url,
            c.facebook_cover_photo_url, c.youtube_channel_url, c.pinterest,
            c.instagram, c.outlet_type, c.brand_store_locator_name, c.brand_website,
            c.facebook_page_national_url, c.google_plus_page_national_url,
            c.google_play_store_national_url, c.ios_app_store_national_url,
            c.client_website, c.toll_free_number_national, c.brand_name,
            c.buy_online_url, c.category_feed_url, c.category_feed_last_modified,
            c.product_feed_url, c.product_feed_last_modified, c.ga_email_id,
            c.ga_key, c.ga_profile_id, c.ga4_account_id, c.amp_ga4_account_id,
            c.amp_ga_email_id, c.amp_ga_key, c.amp_ga_profile_id,
            c.google_account_name, c.save_and_publish_flag, c.close_outlet,
            c.delete_outlet, c.facebook_page_id, c.facebook_page_name,
            c.store_locator_search_type, c.lead_form_type,
            c.store_locator_search_type_responsive, c.restaurant_order_types,
            c.recaptcha_site_key, c.recaptcha_secret_key,
            c.schema_local_business_type, c.add_website_to_webmaster,
            c.can_use_one_page_css, c.fetch_css_from_client_domain, c.services,
            c.amp_analytic_account, c.hastag, c.external_links,
            c.is_website_hosted_on_client_side, c.client_api_auth_key,
            c.is_company_retail_store, c.ifsc_code, c.weekly_off, c.url_alias_backup,
            c.outlet_logo_url, c.outlet_fav_icon_url, c.outlet_cover_photo_url,
            c.master_page_theme, c.menu_category_name, c.menu_category_id,
            c.menu_category_alias, c.custom_state, c.custom_state_alias,
            c.custom_city, c.custom_city_alias, c.custom_locality, c.api_client_id,
            c.api_custom_name, c.api_phone_number, c.location_group,
            c.id AS outlet_raw_id           -- keyset cursor + outlet_raw_id value
        FROM   outlets_raw c
        JOIN   outlets_raw m
               ON  c.parent_id   = m.id
               AND m.outlet_type = 'master'
        JOIN   brands b
               ON  b.brand_name COLLATE utf8mb4_unicode_ci
                 = m.brand_name COLLATE utf8mb4_unicode_ci
        WHERE  c.outlet_type IN ('retail', 'enterprise')
          AND  c.id > %s
        ORDER  BY c.id ASC
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
    cursor = conn.cursor()
    try:
        # ── Step 1: Bulk insert ───────────────────────────
        cursor.executemany(INSERT_QUERY, rows)
        rows_inserted = cursor.rowcount

        # ── FIX: lastrowid = FIRST id of batch in MySQL/TiDB ──
        # Last inserted id = first_id + total_rows_inserted - 1
        cursor.execute("SELECT MAX(id) FROM outlets")
        last_outlets_id = cursor.fetchone()[0]

        # ── Step 2: Upsert checkpoint (same transaction) ──
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
                (last_outlets_id, new_last_raw_id, source_table, target_table),
            )
        else:
            cursor.execute(
                """
                INSERT INTO etl_checkpoints
                    (source_table_name, target_table_name,
                     last_processed_id, last_processed_id_raw)
                VALUES (%s, %s, %s, %s)
                """,
                (source_table, target_table, last_outlets_id, new_last_raw_id),
            )

        # ── Step 3: Commit both atomically ───────────────
        conn.commit()
        logger.info(
            f"Batch {batch_num:04d} | "
            f"[OK] Inserted {rows_inserted} rows | "
            f"outlets.id (last_processed_id) -> {last_outlets_id} | "
            f"outlets_raw.id (last_processed_id_raw) -> {new_last_raw_id}"
        )
        return rows_inserted, last_outlets_id

    except Error as e:
        conn.rollback()
        logger.error(
            f"Batch {batch_num:04d} | "
            f"[FAIL] Transaction rolled back (insert + checkpoint undone). "
            f"Error: {e}"
        )
        raise
    finally:
        cursor.close()

# Main ETL Runner
def run_etl():
    logger.info("=" * 65)
    logger.info(f"ETL PIPELINE STARTED : {SOURCE_TABLE} -> {TARGET_TABLE}")
    logger.info("=" * 65)

    total_inserted = 0
    total_failed   = 0
    batch_num      = 0

    try:
        with get_db_connection() as conn:

            # ── Load checkpoint & source count ────────────
            with conn.cursor() as cur:
                _, last_raw_id = load_checkpoint(cur, SOURCE_TABLE, TARGET_TABLE)
                total_records  = get_total_count(cur)

            logger.info(
                f"Source records (retail + enterprise with parent join) : {total_records} | "
                f"Resuming from outlets_raw.id > {last_raw_id}"
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

                # Last column of every row is c.id (outlet_raw_id) — keyset cursor
                new_last_raw_id = rows[-1][-1]

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
                        last_raw_id = new_last_raw_id   # Advance cursor only on success

                        progress = min((total_inserted / total_records) * 100, 100)
                        logger.info(
                            f"Progress : {total_inserted}/{total_records} "
                            f"({progress:.1f}%)"
                        )
                        batch_succeeded = True
                        break   # Move to next batch

                    except OperationalError as e:
                        # Retriable: deadlock, lock wait timeout, connection drop
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
                                f"(outlets_raw.id range: {rows[0][-1]}-{new_last_raw_id})."
                            )
                            notify_on_permanent_failure(
                                SCRIPT_NAME, batch_num,
                                (rows[0][-1], new_last_raw_id), len(rows), e,
                            )

                    except DatabaseError as e:
                        # Non-retriable: constraint violation, type mismatch, etc.
                        total_failed += len(rows)
                        logger.error(
                            f"Batch {batch_num:04d} | DatabaseError (non-retriable): {e}. "
                            f"Skipping {len(rows)} rows "
                            f"(outlets_raw.id range: {rows[0][-1]}-{new_last_raw_id})."
                        )
                        notify_on_permanent_failure(
                            SCRIPT_NAME, batch_num,
                            (rows[0][-1], new_last_raw_id), len(rows), e,
                        )
                        # Advance cursor to avoid infinite loop on poisoned data
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
            "Last committed checkpoint is safe -- re-run to resume."
        )
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    # ── Final Summary ─────────────────────────────────────
    logger.info("=" * 65)
    logger.info("ETL PIPELINE COMPLETED")
    logger.info(f"  Total Batches  : {batch_num}")
    logger.info(f"  Total Inserted : {total_inserted}")
    logger.info(f"  Total Failed   : {total_failed}")
    logger.info("=" * 65)


if __name__ == "__main__":
    install_crash_notifier(SCRIPT_NAME)
    run_etl()
