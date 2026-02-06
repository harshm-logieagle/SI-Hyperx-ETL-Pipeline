-- 0. Start with Brands table to get (master_outlet_id)
CREATE TABLE brands (
    id INT AUTO_INCREMENT PRIMARY KEY,
    brand_name VARCHAR(50) NOT NULL,
    industry VARCHAR(50) DEFAULT NULL
);

INSERT INTO brands (
	brand_name
)
SELECT brand_name FROM outlets_raw WHERE outlet_type = 'master';

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

INSERT INTO outlets (
    master_outlet_id,
    business_name, url_alias, joiningplan_id, order_planid, customer_id, partner_id, salesperson_id, order_id, category_id, alternative_name, business_email, 
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
    custom_locality, api_client_id, api_custom_name, api_phone_number, location_group
)
SELECT
    b.id AS master_outlet_id,
    c.business_name, c.url_alias, c.joiningplan_id, c.order_planid, c.customer_id, c.partner_id, c.salesperson_id, c.order_id, c.category_id, c.alternative_name, 
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
    c.api_phone_number, c.location_group
FROM outlets_raw c
JOIN outlets_raw m
    ON c.parent_id = m.id
   AND m.outlet_type = 'master'
JOIN brands b
    ON b.brand_name COLLATE utf8mb4_unicode_ci
     = m.brand_name COLLATE utf8mb4_unicode_ci
WHERE c.outlet_type IN ('retail','enterprise');

UPDATE outlets o
JOIN outlets_raw r
  ON o.business_name collate utf8mb4_unicode_ci = r.business_name collate utf8mb4_unicode_ci 
SET o.outlet_raw_id = r.id;

-- 2. Master Outlet Categories Table
create table master_outlet_categories (
	id INT auto_increment primary key,
	master_outlet_id INT,
	category_name VARCHAR(255),
	constraint fk_categories_brands_id
		foreign key (master_outlet_id)
		references brands(id)
		on delete cascade 
		on update cascade	
);

INSERT INTO master_outlet_categories (
	master_outlet_id,
	category_name
)
SELECT DISTINCT
	b.id,
	ph.category
FROM brands b
JOIN outlets_raw t ON t.brand_name COLLATE utf8mb4_unicode_ci = b.brand_name COLLATE utf8mb4_unicode_ci
JOIN product_hierarchy_raw ph ON ph.master_outlet_id = t.id;

-- 3. Master Outlet Products Table
create table master_outlet_products (
	id INT auto_increment primary key,
	master_outlet_id INT,
	outlet_id INT,
	name VARCHAR(200),
	embedding TEXT,
	description TEXT,
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

insert into master_outlet_products (
	name,
	embedding,
	master_outlet_id,
	category_id
)
select distinct phr.product_name, phr.product_embedding, b.id, moc.id from brands b
join outlets_raw t on t.brand_name COLLATE utf8mb4_unicode_ci = b.brand_name COLLATE utf8mb4_unicode_ci
join product_hierarchy_raw phr on phr.master_outlet_id = t.id
join master_outlet_categories moc on phr.category COLLATE utf8mb4_unicode_ci = moc.category_name COLLATE utf8mb4_unicode_ci;

-- 4. Master Outlet Call Reasons
CREATE TABLE IF NOT EXISTS master_outlet_call_reasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    master_outlet_id INT NOT NULL,
    outlet_id INT,
    type VARCHAR(50),
    value VARCHAR(255), 
    CONSTRAINT fk_mocr_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_mocr_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

INSERT INTO master_outlet_call_reasons (master_outlet_id, outlet_id, type, value)
SELECT DISTINCT 
    o.master_outlet_id,
    o.id,
    raw.reason_type,
    raw.reason
FROM call_recording_analytics_details_raw raw
JOIN outlets o ON raw.outlet_id = o.outlet_raw_id
WHERE raw.reason IS NOT NULL;

-- 5. Customer Call Recordings
CREATE TABLE IF NOT EXISTS customer_call_recordings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    master_outlet_id INT NOT NULL,
    outlet_id INT NOT NULL,
    call_record_raw_id INT, 
    caller_number VARCHAR(20),
    called_number VARCHAR(20),
    agent_number VARCHAR(20),
    call_date DATE,
    call_time VARCHAR(255),
    call_date_time DATETIME,
    call_start_time DATETIME,
    call_end_time DATETIME,
    call_duration TIME,
    total_durations TIME,
    call_status VARCHAR(50),
    call_uuid VARCHAR(150),
    call_recording_url VARCHAR(250),
    publisher_type VARCHAR(25),
    request_variable MEDIUMTEXT,
    response_variable MEDIUMTEXT,
    Branch VARCHAR(300),
    CustomerType VARCHAR(300),
    answerd_by VARCHAR(300),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    modified DATETIME,
    ivr_type VARCHAR(50),
    waybeo_unique_call_id VARCHAR(50),
    called_client_store_id VARCHAR(50),
    waybeo_callid VARCHAR(50),
    answered_by VARCHAR(50),
    ivr_duration TIME,
    ring_duration TIME,
    lead_send_to_crm TINYINT DEFAULT 0,
    call_type VARCHAR(255),
    transfer_status VARCHAR(45),
    destination_number VARCHAR(45),
    count_of_sale_query TINYINT,
    count_of_service_query TINYINT,
    is_new_customer VARCHAR(45),
    dealer_code VARCHAR(45),
    dealer_type VARCHAR(50),
    virtual_number VARCHAR(45),
    locality VARCHAR(45),
    am VARCHAR(45),
    rsm VARCHAR(45),
    city VARCHAR(45),
    state VARCHAR(45),
    hangup_leg VARCHAR(45),
    key_press VARCHAR(45),
    call_record_language VARCHAR(100),
    call_language_api_response MEDIUMTEXT,
    is_caller_notified TINYINT(1) DEFAULT 0,
    CONSTRAINT fk_ccr_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ccr_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

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
FROM customer_call_record_logs_raw raw
JOIN outlets o ON raw.outlet_id = o.outlet_raw_id;

-- 6. Call Recording Analytics
CREATE TABLE IF NOT EXISTS call_recording_analytics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_recording_id INT NOT NULL,
    master_outlet_id INT NOT NULL,
    outlet_id INT NOT NULL,
    is_webhook TINYINT DEFAULT 0,
    analytic_type TINYINT,
    text_status TINYINT,
    reason VARCHAR(255),
    reason_verbatim TEXT,
    audio_to_text TEXT,
    reason_type VARCHAR(255),
    end_of_call_status VARCHAR(250),
    call_language VARCHAR(50),
    customer_gender VARCHAR(50),
    customer_type VARCHAR(50),
    overall_sentiment VARCHAR(50),
    summary TEXT,
    is_valid_transcript TINYINT(1) DEFAULT 0,
    transcript LONGTEXT,
    emotions VARCHAR(500),
    emotion_verbatims TEXT,
    emotions_json JSON,
    products TEXT,
    product_sentiments TEXT,
    product_verbatims TEXT,
    product_tags TEXT,
    product_categories TEXT,
    products_mentioned_json JSON,
    l0_reason VARCHAR(255),
    l1_reason VARCHAR(255),
    l2_reason VARCHAR(255),
    l3_reason VARCHAR(255),
    brand_sentiment VARCHAR(255),
    created DATETIME,
    modified DATETIME,
    CONSTRAINT fk_cra_call_rec FOREIGN KEY (call_recording_id) REFERENCES customer_call_recordings(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cra_brands FOREIGN KEY (master_outlet_id) REFERENCES brands(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cra_outlets FOREIGN KEY (outlet_id) REFERENCES outlets(id) ON DELETE CASCADE ON UPDATE CASCADE
);

INSERT INTO call_recording_analytics (
    call_recording_id, 
    master_outlet_id, 
    outlet_id, 
    is_webhook, 
    analytic_type,
    text_status, 
    reason, 
    reason_verbatim,
    audio_to_text, 
    reason_type,
    end_of_call_status,
    call_language, 
    customer_gender, 
    customer_type, 
    overall_sentiment,
    summary, 
    is_valid_transcript, 
    transcript, 
    emotions,
    emotion_verbatims,
    emotions_json,
    products, 
    product_sentiments,
    product_verbatims,
    product_tags,
    product_categories,
    products_mentioned_json,
    l0_reason, 
    l1_reason, 
    l2_reason, 
    l3_reason, 
    brand_sentiment,
    created,
    modified
)
SELECT 
    ccr.id,
    ccr.master_outlet_id,
    ccr.outlet_id,
    raw.is_webhook, raw.analytic_type,
    raw.text_status, raw.reason, raw.reason_verbatim,
    raw.audio_to_text, raw.reason_type,
    raw.end_of_call_status,
    raw.call_language, raw.customer_gender, raw.customer_type, raw.overall_sentiment,
    raw.summary, raw.is_valid_transcript, raw.transcript, 
    raw.emotions, raw.emotion_verbatims, raw.emotions_json,
    raw.products, raw.product_sentiments, raw.product_verbatims, raw.product_tags,
    raw.product_categories, raw.products_mentioned_json,
    raw.l0_reason, raw.l1_reason, raw.l2_reason, raw.l3_reason, raw.brand_sentiment,
    raw.created, raw.modified
FROM call_recording_analytics_details_raw raw
JOIN customer_call_recordings ccr ON raw.customer_call_record_id = ccr.call_record_raw_id;

CREATE INDEX idx_ccr_uuid ON customer_call_recordings(call_uuid);
CREATE INDEX idx_ccr_date ON customer_call_recordings(call_date);
CREATE INDEX idx_cra_sentiment ON call_recording_analytics(overall_sentiment);
CREATE INDEX idx_cra_reason ON call_recording_analytics(reason);

-- 7. Call Product Mentions
create table call_product_mentions (
	id INT auto_increment primary key,
	call_recording_analytics_id INT,
	master_outlet_product_id INT,
	product_sentiment VARCHAR(250),
	product_verbatim VARCHAR(250),
	tags VARCHAR(250),
    CONSTRAINT fk_product_mentions_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_product_mentions_outlet_products_id
        FOREIGN KEY (master_outlet_product_id)
        REFERENCES master_outlet_products(id)
        ON DELETE CASCADE
        ON UPDATE cascade
);

INSERT INTO call_product_mentions (
    call_recording_analytics_id,
    master_outlet_product_id,
    product_sentiment,
    product_verbatim,
    tags
)
SELECT 
    cra.id,
    mop.id,
    jt.sentiment,
    jt.verbatim,
    jt.tags
FROM call_recording_analytics cra
CROSS JOIN JSON_TABLE(
    cra.products_mentioned_json,
    '$[*]' COLUMNS (
        p_name VARCHAR(200) PATH '$.product',
        p_category VARCHAR(255) PATH '$.category',
        sentiment VARCHAR(250) PATH '$.product_sentiment',
        verbatim VARCHAR(250) PATH '$.product_verbatim',
        NESTED PATH '$.tags[*]' COLUMNS (
            tags VARCHAR(250) PATH '$'
        )
    )
) AS jt
INNER JOIN master_outlet_categories moc
    ON jt.p_category COLLATE utf8mb4_unicode_ci = moc.category_name COLLATE utf8mb4_unicode_ci
    AND moc.master_outlet_id = cra.master_outlet_id
INNER JOIN master_outlet_products mop 
    ON jt.p_name COLLATE utf8mb4_unicode_ci = mop.name COLLATE utf8mb4_unicode_ci
    AND mop.category_id = moc.id
    AND mop.master_outlet_id = cra.master_outlet_id;

-- 8. Call Reasons
create table call_reasons (
	id INT auto_increment primary key,
	call_recording_analytics_id INT,
	master_outlet_reason_id INT,
	reason_verbatim TEXT,
    CONSTRAINT fk_call_reasons_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE cascade,
    CONSTRAINT fk_call_reasons_call_resp_id
        FOREIGN KEY (master_outlet_reason_id)
        REFERENCES master_outlet_call_reasons(id)
        ON DELETE CASCADE
        ON UPDATE cascade
);

INSERT INTO call_reasons (
    call_recording_analytics_id,
    master_outlet_reason_id,
    reason_verbatim
)
SELECT 
    cra.id,
    mocr.id,
    raw.reason_verbatim
FROM call_recording_analytics cra
JOIN customer_call_recordings ccr ON cra.call_recording_id = ccr.id
JOIN call_recording_analytics_details_raw raw ON ccr.call_record_raw_id = raw.customer_call_record_id
JOIN master_outlet_call_reasons mocr 
    ON raw.reason COLLATE utf8mb4_unicode_ci = mocr.value COLLATE utf8mb4_unicode_ci
    AND mocr.master_outlet_id = cra.master_outlet_id
    AND mocr.outlet_id = cra.outlet_id;

-- 9. Emotions Master
CREATE TABLE IF NOT EXISTS emotions_master (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(50),
    `description` VARCHAR(255)
);

INSERT INTO 
    emotions_master (name) 
VALUES 
    ('Neutral'), 
    ('Frustration'), 
    ('Happiness'), 
    ('Confusion');

-- 10. Call Analytics Emotions
CREATE TABLE IF NOT EXISTS call_analytics_emotions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_recording_analytics_id INT,
    emotion_id INT,
    emotion_verbatim VARCHAR(500),
    CONSTRAINT fk_call_analytics_emotions_rec_analytics_id
        FOREIGN KEY (call_recording_analytics_id)
        REFERENCES call_recording_analytics(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_call_analytics_emotions_emotion_id
        FOREIGN KEY (emotion_id)
        REFERENCES emotions_master(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

INSERT INTO call_analytics_emotions (
    call_recording_analytics_id,
    emotion_id,
    emotion_verbatim
)
SELECT 
    cra.id,
    em.id,
    jt.verbatim
FROM call_recording_analytics cra
CROSS JOIN JSON_TABLE(
    cra.emotions_json,
    '$[*]' COLUMNS (
        emotion_name VARCHAR(50) PATH '$.emotion',
        verbatim VARCHAR(500) PATH '$.emotion_verbatim'
    )
) AS jt
JOIN emotions_master em ON jt.emotion_name COLLATE utf8mb4_unicode_ci = em.name COLLATE utf8mb4_unicode_ci;

-- 11. Decision Nodes
CREATE TABLE IF NOT EXISTS decision_nodes (
	id INT AUTO_INCREMENT PRIMARY KEY,
	master_outlet_id INT,
	parent_id INT DEFAULT NULL,
	node_type ENUM('classification', 'extraction'),
	label VARCHAR(100),
	description TEXT,
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
	decision_node_id INT,
	level VARCHAR(10),
	value VARCHAR(250),
	constraint fk_level_reasons_master_outlet_id
	foreign key (master_outlet_id)
	references brands(id)
	on delete cascade
	on update cascade,
	constraint fk_level_reasons_call_recording_id
	foreign key (call_recording_id)
	references customer_call_recordings(id)
	on delete cascade
	on update cascade,
	constraint fk_level_reasons_decision_node_id
	foreign key (decision_node_id)
	references decision_nodes(id)
	on delete cascade
	on update cascade
);



set foreign_key_checks=0;
truncate table product_hierarchy_raw;
truncate table customer_call_record_logs_raw;
truncate table call_recording_analytics_details_raw;
truncate table call_analytics_emotions;
truncate table call_product_mentions;
truncate table call_reasons;
truncate table call_recording_analytics;
truncate table customer_call_recordings;
truncate table master_outlet_call_reasons;
truncate table master_outlet_categories;
truncate table master_outlet_products;
truncate table outlets;
truncate table outlets_raw;
truncate table brands;