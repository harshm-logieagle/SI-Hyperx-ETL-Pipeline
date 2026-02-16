from app.core.db import get_connection

class CustomerCallRecordingsRepository:

    @staticmethod
    def check_sample_calls_exist(
        master_outlet_id: int, 
        sample_size: int = 500,
        min_duration: int = 0,
        start_date: str = None,
        end_date: str = None
    ):
        """
        Check and fetch sample calls for a brand with filters.
        """

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = [
            "call_status = 'Connected'",
            "master_outlet_id = %s",
            "call_recording_url != ''"
        ]
        params = [master_outlet_id]

        if min_duration > 0:
            where_clauses.append("call_duration >= %s")
            params.append(min_duration)
        
        if start_date:
            where_clauses.append("start_time >= %s")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("start_time <= %s")
            params.append(end_date)

        query = f"""
            SELECT call_recording_url
            FROM customer_call_recordings
            WHERE {' AND '.join(where_clauses)}
            LIMIT %s;
        """
        params.append(sample_size)

        cursor.execute(query, tuple(params))
        result = cursor.fetchall()

        cursor.close()
        conn.close()

        # Relaxing the requirement for initial discovery, but keep for pipeline
        return result