SELECT crad.*
FROM call_recording_analytics_details AS crad
LEFT JOIN customer_call_record_logs AS ccrl
  ON ccrl.id = crad.customer_call_record_id
WHERE ccrl.master_outlet_id = 408116
  AND ccrl.call_duration >= 120
  AND crad.l0_reason IS NOT NULL
LIMIT 10;

