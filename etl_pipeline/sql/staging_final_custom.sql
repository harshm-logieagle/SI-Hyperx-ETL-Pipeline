-- master_outlet_categories
INSERT INTO master_outlet_categories (
	master_outlet_id,
	category_name
)
SELECT DISTINCT
	b.id,
	ph.category
FROM product_hierarchy ph
JOIN brands b ON b.si_master_outlet_id = ph.master_outlet_id
WHERE ph.master_outlet_id = 517132;	

-- master_outlet_products
INSERT INTO master_outlet_products (
	name,
	embedding,
	master_outlet_id,
	category_id
)
SELECT DISTINCT ph.product_name, ph.product_embedding, b.id, moc.id FROM product_hierarchy ph 
JOIN brands b ON b.si_master_outlet_id = ph.master_outlet_id 
JOIN master_outlet_categories moc on ph.category = moc.category_name
WHERE ph.master_outlet_id = 517132;

-- master_outlet_call_reasons
INSERT INTO master_outlet_call_reasons (value, master_outlet_id, type)
SELECT raw.reason,
       o.master_outlet_id,
       raw.reason_type
FROM call_recording_analytics_details raw
JOIN outlets o 
    ON raw.outlet_id = o.outlet_raw_id
WHERE raw.reason IS NOT NULL AND raw.master_outlet_id = 517132
AND raw.id = (
    SELECT MAX(r2.id)
    FROM call_recording_analytics_details r2
    WHERE r2.reason = raw.reason
);

-- customer_call_recordings
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
WHERE o.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);

-- call_recording_analytics
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
FROM call_recording_analytics_details raw
JOIN customer_call_recordings ccr ON raw.customer_call_record_id = ccr.call_record_raw_id
WHERE ccr.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);

-- call_product_mentions (Supported with TiDB)
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
WHERE tr.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);

-- call_product_mention_tags
INSERT INTO call_product_mention_tags (
    call_product_mentions_id,
    tags
)
SELECT
    cpm.id,
    TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(cpm.tags, ',', numbers.n), ',', -1)) AS tag
FROM call_product_mentions cpm
JOIN (
    SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL
    SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL
    SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10
) numbers
ON CHAR_LENGTH(cpm.tags) - CHAR_LENGTH(REPLACE(cpm.tags, ',', '')) >= numbers.n - 1
WHERE cpm.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);

-- call_reasons
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
WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);

-- call_analytics_emotions (Supported with TiDB)
INSERT INTO call_analytics_emotions (
    call_recording_analytics_id,
    master_outlet_id,
    outlet_id,
    call_recording_id,
    emotion_id,
    emotion_verbatim
)
SELECT
    cra.id,
    cra.master_outlet_id,
    cra.outlet_id,
    cra.call_recording_id,
    em.id,
    JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json, CONCAT('$[', n.n, '].emotion_verbatim'))) AS verbatim
FROM call_recording_analytics cra
INNER JOIN (
    SELECT (a.n + b.n * 10) AS n
    FROM
        (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
         UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
    CROSS JOIN
        (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
         UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
) n ON n.n < JSON_LENGTH(cra.emotions_json)
INNER JOIN emotions_master em
    ON JSON_UNQUOTE(JSON_EXTRACT(cra.emotions_json, CONCAT('$[', n.n, '].emotion'))) COLLATE utf8mb4_unicode_ci
     = em.name COLLATE utf8mb4_unicode_ci
WHERE cra.master_outlet_id = (SELECT id FROM brands WHERE si_master_outlet_id = 517132);
