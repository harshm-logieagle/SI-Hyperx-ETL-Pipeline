from app.core.db import get_connection

class CustomerCallRecordingsRepository:

    @staticmethod
    def check_sample_calls_exist(MIN_SAMPLE_CALLS: int = 500):
        """
        Check if >= MIN_SAMPLE_CALLS exist for a brand in the customer_call_recordings table.
        
        Conditions:
        - If yes, return the list of details required from that table.
        - If No, skip the brand for now.
        """

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT call_recording_url
            FROM customer_call_recordings
            WHERE call_status = 'Connected'
            AND master_outlet_id IS NOT NULL
            LIMIT {MIN_SAMPLE_CALLS};
        """

        cursor.execute(query)
        result = cursor.fetchall()

        cursor.close()
        conn.close()

        # If less than MIN_SAMPLE_CALLS sample calls, skip the brand
        if len(result) < MIN_SAMPLE_CALLS:
            return None

        return result