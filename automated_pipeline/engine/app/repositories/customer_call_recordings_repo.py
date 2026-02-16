from app.core.db import get_connection

class CustomerCallRecordingsRepository:

    @staticmethod
    def check_sample_calls_exist(master_outlet_id: int, MIN_SAMPLE_CALLS: int = 500):
        """
        Check if >= MIN_SAMPLE_CALLS exist for a brand in the customer_call_recordings table.
        """

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT call_recording_url
            FROM customer_call_recordings
            WHERE call_status = 'Connected'
            AND master_outlet_id = %s
            AND call_recording_url != ''
            LIMIT {MIN_SAMPLE_CALLS};
        """

        cursor.execute(query, (master_outlet_id,))
        result = cursor.fetchall()

        cursor.close()
        conn.close()

        if len(result) < MIN_SAMPLE_CALLS:
            return None

        return result