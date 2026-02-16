-- 1. Check if brands exist in master_outlet_products or not
SELECT 
    b.id 
FROM brands b 
LEFT JOIN master_outlet_products m ON m.master_outlet_id = b.id 
WHERE m.master_outlet_id IS NULL;

-- 2. Check if there are at least 500 sample calls for a brand
SELECT call_recording_url
FROM customer_call_recordings
WHERE call_status = 'Connected'
AND master_outlet_id IS NOT NULL
LIMIT 500;
