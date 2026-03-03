set foreign_key_checks=0;
DROP TABLE decision_nodes;
DROP TABLE level_reasons;
DROP TABLE call_analytics_emotions;
DROP TABLE call_product_mentions;
DROP TABLE call_product_mention_tags;
DROP TABLE emotions_master;
DROP TABLE call_reasons;
DROP TABLE call_recording_analytics;
DROP TABLE customer_call_recordings;
DROP TABLE master_outlet_call_reasons;
DROP TABLE master_outlet_categories;
DROP TABLE master_outlet_products;
DROP TABLE outlets;
DROP TABLE brands;

-- -1. Checkpoints table to check the last processed id of each table
CREATE TABLE etl_checkpoints (
    id BIGINT AUTO_INCREMENT,
    table_name VARCHAR(70) NOT NULL,
    last_processed_id BIGINT NOT NULL DEFAULT 0,
	last_processed_id_raw BIGINT NULL,
    updated_at TIMESTAMP NOT NULL 
        DEFAULT CURRENT_TIMESTAMP 
        ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_table_name (table_name)
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

-- 0. Start with Brands table to get (master_outlet_id)
CREATE TABLE brands (
    id INT AUTO_INCREMENT PRIMARY KEY,
    brand_name VARCHAR(50) NOT NULL,
    industry VARCHAR(50) DEFAULT NULL
);

-- 1. Outlets table to get (outlet_id)
CREATE TABLE outlets (
	`id` INT auto_increment primary key,
	`master_outlet_id` INT,
	`business_name` VARCHAR(200),
    `outlet_raw_id` INT,
	`url_alias` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`joiningplan_id` int DEFAULT NULL,
	`order_planid` int DEFAULT NULL,
	`customer_id` int DEFAULT NULL,
	`partner_id` int DEFAULT NULL,
	`salesperson_id` int DEFAULT NULL,
	`order_id` int DEFAULT NULL,
	`category_id` int DEFAULT NULL,
	`alternative_name` varchar(90) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`business_email` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`company_tagline` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`location` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`location_alias` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`phone` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`alternative_phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`mobile_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`tty_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`country_id` int DEFAULT NULL,
	`iso_alpha_2` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`state_id` int DEFAULT NULL,
	`city_id` int DEFAULT NULL,
	`country` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`circle` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`circle_alias` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`state` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`state_alias` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`city` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`city_alias` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`address_2` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`landmark` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`zip` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`website` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`latitude` varchar(17) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`longitude` varchar(17) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`geo_coded_latitude` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`geo_coded_longitude` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`contact_person_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`contact_person_designation` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`contact_person_email` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`contact_person_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`toll_free_number` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`fax_no` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_page_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`twitter_handle` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`googleplus_url` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`year_of_establishment` int DEFAULT NULL,
	`brands_carried` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`description` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`short_description` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`special_offer` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`special_offer_url` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`tags` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`business_hours` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`logo` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`logo_from_csv` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`logo_dir` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`fav_icon` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`fav_icon_dir` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`copyright` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_cover_photo` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_cover_dir` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_cover_photo_allow_publishing` tinyint(1) DEFAULT NULL,
	`facebook_profile_photo` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_profile_dir` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_profile_photo_allow_publishing` tinyint(1) DEFAULT NULL,
	`facebook_profile_photo_publishing_flag` tinyint(1) DEFAULT NULL,
	`facebook_cover_photo_publishing_flag` tinyint(1) DEFAULT NULL,
	`fb_cover_alt_text` varchar(125) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`fb_cover_title_text` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`meta_title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`meta_keyword` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`meta_additional_keywords` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`meta_description` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`page_theme` int DEFAULT NULL,
	`redirect_to_customer_website` tinyint(1) DEFAULT NULL,
	`can_redirect_store_locator_to_client_website` tinyint DEFAULT NULL,
	`redirect_store_locator_to_client_website` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`created` datetime DEFAULT NULL,
	`modified` datetime DEFAULT NULL,
	`outlet_id_from_csv` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`state_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`is_exists_in_publisher_data_table` tinyint unsigned DEFAULT NULL,
	`parent_id` int unsigned DEFAULT NULL,
	`ga_tracking_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`ga_account_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`amp_ga_account_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`mailer_trigger_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`mailer_ml_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`ga_tracking_script` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`enterprise_client_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`enterprise_client_store_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`enterprise_actual_client_store_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`lat_long_verify` tinyint(1) DEFAULT NULL,
	`lat_long_verify_ip` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`lat_long_verify_date` datetime DEFAULT NULL,
	`lat_long_qc_pending` tinyint(1) DEFAULT NULL,
	`enterprise_verifylatlong_emaildate` datetime DEFAULT NULL,
	`facebook_profile_picture_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`facebook_cover_photo_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`youtube_channel_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`pinterest` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`instagram` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`outlet_type` enum('retail','enterprise','master') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`brand_store_locator_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`brand_website` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`facebook_page_national_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`google_plus_page_national_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`google_play_store_national_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`ios_app_store_national_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`client_website` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`toll_free_number_national` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`brand_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`buy_online_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`category_feed_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`category_feed_last_modified` date DEFAULT NULL,
	`product_feed_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`product_feed_last_modified` date DEFAULT NULL,
	`ga_email_id` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`ga_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`ga_profile_id` int DEFAULT NULL,
	`ga4_account_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`amp_ga4_account_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`amp_ga_email_id` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`amp_ga_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`amp_ga_profile_id` int DEFAULT NULL,
	`google_account_name` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`save_and_publish_flag` tinyint(1) DEFAULT NULL,
	`close_outlet` tinyint(1) DEFAULT NULL,
	`delete_outlet` tinyint(1) DEFAULT NULL,
	`facebook_page_id` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`facebook_page_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`store_locator_search_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`lead_form_type` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`store_locator_search_type_responsive` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`restaurant_order_types` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`recaptcha_site_key` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`recaptcha_secret_key` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`schema_local_business_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`add_website_to_webmaster` tinyint DEFAULT NULL,
	`can_use_one_page_css` tinyint DEFAULT NULL,
	`fetch_css_from_client_domain` tinyint DEFAULT NULL,
	`services` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`amp_analytic_account` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`hastag` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`external_links` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`is_website_hosted_on_client_side` tinyint DEFAULT NULL,
	`client_api_auth_key` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`is_company_retail_store` tinyint DEFAULT NULL,
	`ifsc_code` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`weekly_off` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`url_alias_backup` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`outlet_logo_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`outlet_fav_icon_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`outlet_cover_photo_url` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`master_page_theme` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`menu_category_name` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`menu_category_id` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`menu_category_alias` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
	`custom_state` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`custom_state_alias` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`custom_city` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`custom_city_alias` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`custom_locality` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`api_client_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`api_custom_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`api_phone_number` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	`location_group` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	constraint fk_outlets_brands_id
		foreign key (master_outlet_id)
		references brands(id)
		on delete cascade 
		on update cascade	
);

ALTER TABLE outlets ADD INDEX idx_outlets_outlet_raw_id (outlet_raw_id);

-- 2. Master Outlet Categories Table
create table master_outlet_categories (
	id INT auto_increment primary key,
	master_outlet_id INT,
	category_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	constraint fk_categories_brands_id
		foreign key (master_outlet_id)
		references brands(id)
		on delete cascade 
		on update cascade	
);

-- 3. Master Outlet Products Table
create table master_outlet_products (
	id INT auto_increment primary key,
	master_outlet_id INT,
	outlet_id INT,
	name VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	embedding TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	description TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	category_id INT,
    CONSTRAINT fk_products_brands_id
        FOREIGN KEY (master_outlet_id)
        REFERENCES brands(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_products_outlets_id
        FOREIGN KEY (outlet_id)
        REFERENCES outlets(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_products_category_id
        FOREIGN KEY (category_id)
        REFERENCES master_outlet_categories(id)
        ON DELETE CASCADE
        ON UPDATE cascade
);

-- 4. Master Outlet Call Reasons
CREATE TABLE IF NOT EXISTS master_outlet_call_reasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    master_outlet_id INT NOT NULL,
    outlet_id INT,
    type VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    value VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
    CONSTRAINT fk_mocr_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_mocr_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- 5. Customer Call Recordings
CREATE TABLE IF NOT EXISTS customer_call_recordings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    master_outlet_id INT NOT NULL,
    outlet_id INT NOT NULL,
    call_record_raw_id INT, 
    caller_number VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    called_number VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    agent_number VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_date DATE,
    call_time VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_date_time DATETIME,
    call_start_time DATETIME,
    call_end_time DATETIME,
    call_duration TIME,
    total_durations TIME,
    call_status VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_uuid VARCHAR(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_recording_url VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    publisher_type VARCHAR(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    request_variable MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    response_variable MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    Branch VARCHAR(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    CustomerType VARCHAR(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    answerd_by VARCHAR(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    modified DATETIME,
    ivr_type VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    waybeo_unique_call_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    called_client_store_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    waybeo_callid VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    answered_by VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    ivr_duration TIME,
    ring_duration TIME,
    lead_send_to_crm TINYINT DEFAULT 0,
    call_type VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    transfer_status VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    destination_number VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    count_of_sale_query TINYINT,
    count_of_service_query TINYINT,
    is_new_customer VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    dealer_code VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    dealer_type VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    virtual_number VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    locality VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    am VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    rsm VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    city VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    state VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    hangup_leg VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    key_press VARCHAR(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_record_language VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_language_api_response MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    is_caller_notified TINYINT(1) DEFAULT 0,
    CONSTRAINT fk_ccr_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ccr_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

ALTER TABLE customer_call_recordings ADD INDEX idx_ccr_call_record_raw_id (call_record_raw_id);

-- 6. Call Recording Analytics
CREATE TABLE IF NOT EXISTS call_recording_analytics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_recording_id INT NOT NULL,
    master_outlet_id INT NOT NULL,
    outlet_id INT NOT NULL,
    is_webhook TINYINT DEFAULT 0,
    analytic_type TINYINT,
    text_status TINYINT,
    reason VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    reason_verbatim TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    audio_to_text TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    reason_type VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    end_of_call_status VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    call_language VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    customer_gender VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    customer_type VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    overall_sentiment VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    summary TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    is_valid_transcript TINYINT(1) DEFAULT 0,
    transcript LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    emotions VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    emotion_verbatims TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    emotions_json JSON,
    products TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    product_sentiments TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    product_verbatims TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    product_tags TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    product_categories TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    products_mentioned_json JSON,
    l0_reason VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    l1_reason VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    l2_reason VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    l3_reason VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    brand_sentiment VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    created DATETIME,
    modified DATETIME,
    CONSTRAINT fk_cra_call_rec FOREIGN KEY (call_recording_id) REFERENCES customer_call_recordings(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cra_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cra_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_ccr_uuid ON customer_call_recordings(call_uuid);
CREATE INDEX idx_ccr_date ON customer_call_recordings(call_date);
CREATE INDEX idx_cra_sentiment ON call_recording_analytics(overall_sentiment);
CREATE INDEX idx_cra_reason ON call_recording_analytics(reason);

-- 7. Call Product Mentions
create table call_product_mentions (
	id INT auto_increment primary key,
	call_recording_analytics_id INT,
	master_outlet_product_id INT,
    master_outlet_id INT,
    outlet_id INT,
    call_recording_id INT,
	product_sentiment VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	product_verbatim VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	tags VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    CONSTRAINT fk_product_mentions_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_product_mentions_outlet_products_id
        FOREIGN KEY (master_outlet_product_id)
        REFERENCES master_outlet_products(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_product_mentions_master_outlet_id
        FOREIGN KEY (master_outlet_id)
        REFERENCES brands(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_product_mentions_outlet_id
        FOREIGN KEY (outlet_id)
        REFERENCES outlets(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_product_mentions_call_recording_id
        FOREIGN KEY (call_recording_id)
        REFERENCES customer_call_recordings(id)
        ON DELETE CASCADE
        ON UPDATE cascade
);

-- Normalized table (child)
CREATE TABLE call_product_mention_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_product_mentions_id INT,
    tags VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    CONSTRAINT fk_call_product_mention_tags_call_product_mentions_id
        FOREIGN KEY (call_product_mentions_id)
        REFERENCES call_product_mentions(id)
        ON DELETE CASCADE
        ON UPDATE cascade
);

-- 8. Call Reasons
create table call_reasons (
	id INT auto_increment primary key,
	call_recording_analytics_id INT,
	master_outlet_reason_id INT,
    master_outlet_id INT,
    outlet_id INT,
    call_recording_id INT,
	reason_verbatim TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    CONSTRAINT fk_call_reasons_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_call_reasons_call_resp_id
        FOREIGN KEY (master_outlet_reason_id)
        REFERENCES master_outlet_call_reasons(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_call_reasons_master_outlet_id
        FOREIGN KEY (master_outlet_id)
        REFERENCES brands(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_reasons_outlet_id
        FOREIGN KEY (outlet_id)
        REFERENCES outlets(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_reasons_call_recording_id
        FOREIGN KEY (call_recording_id)
        REFERENCES customer_call_recordings(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 9. Emotions Master
CREATE TABLE IF NOT EXISTS emotions_master (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `description` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
);

-- 10. Call Analytics Emotions
CREATE TABLE IF NOT EXISTS call_analytics_emotions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_recording_analytics_id INT,
    master_outlet_id INT,
    outlet_id INT,
    call_recording_id INT,
    emotion_id INT,
    emotion_verbatim VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    CONSTRAINT fk_call_analytics_emotions_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_analytics_emotions_emotion_id
        FOREIGN KEY (emotion_id)
        REFERENCES emotions_master(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_analytics_emotions_master_outlet_id
        FOREIGN KEY (master_outlet_id)
        REFERENCES brands(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_analytics_emotions_outlet_id
        FOREIGN KEY (outlet_id)
        REFERENCES outlets(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_analytics_emotions_call_recording_id
        FOREIGN KEY (call_recording_id)
        REFERENCES customer_call_recordings(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 11. Decision Nodes
CREATE TABLE IF NOT EXISTS decision_nodes (
	id INT AUTO_INCREMENT PRIMARY KEY,
	master_outlet_id INT,
	parent_id INT DEFAULT NULL,
	node_type ENUM('classification', 'extraction'),
	label VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	description TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	is_active TINYINT,
	CONSTRAINT fk_decision_nodes_mo_id
		FOREIGN KEY (master_outlet_id)
		REFERENCES brands(id)
		ON DELETE CASCADE 
		ON UPDATE CASCADE,
	CONSTRAINT fk_decision_nodes_parent_id
		FOREIGN KEY (parent_id)
		REFERENCES decision_nodes(id)
		ON DELETE CASCADE 
		ON UPDATE CASCADE
);

-- 12. Level Reasons
create table level_reasons (
	id INT auto_increment primary key,
	master_outlet_id INT,
	call_recording_id INT,
    path_id INT,
	level VARCHAR(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	value VARCHAR(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
	constraint fk_level_reasons_master_outlet_id
	foreign key (master_outlet_id)
	references brands(id)
	on delete cascade
	on update cascade,
	constraint fk_level_reasons_call_recording_id
	foreign key (call_recording_id)
	references customer_call_recordings(id)
	on delete cascade
	on update cascade
);
