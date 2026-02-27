from app.core.db import get_connection


class ExcelPushRepository:

    @staticmethod
    def ensure_table():
        """Create excel_push_jobs table if it doesn't exist (auto-migration)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS excel_push_jobs (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                master_outlet_id VARCHAR(500)  NOT NULL,
                outlet_ids      TEXT,
                state           VARCHAR(100),
                city            VARCHAR(100),
                from_date       DATE,
                to_date         DATE,
                num_records     INT            DEFAULT 200000,
                status          VARCHAR(50)    DEFAULT 'pending',
                stage           VARCHAR(255),
                total_records   INT            DEFAULT 0,
                pushed_records  INT            DEFAULT 0,
                error_message   TEXT,
                created_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def create_job(config: dict) -> int:
        """Insert a new push job and return its auto-generated ID."""
        ExcelPushRepository.ensure_table()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO excel_push_jobs
                (master_outlet_id, outlet_ids, state, city, from_date, to_date, num_records, status, stage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', 'Queued')
        """, (
            config.get('master_outlet_id'),
            config.get('outlet_ids') or None,
            config.get('state') or None,
            config.get('city') or None,
            config.get('from_date') or None,
            config.get('to_date') or None,
            int(config.get('num_records') or 200000),
        ))
        conn.commit()
        job_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return job_id

    @staticmethod
    def update_job(job_id: int, **kwargs):
        """Dynamically update any subset of job columns."""
        if not kwargs:
            return
        conn = get_connection()
        cursor = conn.cursor()
        set_clause = ', '.join([f"`{k}` = %s" for k in kwargs])
        values = list(kwargs.values()) + [job_id]
        cursor.execute(f"UPDATE excel_push_jobs SET {set_clause} WHERE id = %s", values)
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def get_all_jobs() -> list:
        """Return all jobs ordered by most recent first."""
        ExcelPushRepository.ensure_table()
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM excel_push_jobs ORDER BY created_at DESC")
        jobs = cursor.fetchall()
        cursor.close()
        conn.close()
        for j in jobs:
            j['created_at'] = str(j['created_at'])
            j['updated_at'] = str(j['updated_at'])
            if j.get('from_date'):
                j['from_date'] = str(j['from_date'])
            if j.get('to_date'):
                j['to_date'] = str(j['to_date'])
        return jobs

    @staticmethod
    def get_job(job_id: int) -> dict:
        """Return a single job by ID."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM excel_push_jobs WHERE id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.close()
        conn.close()
        if job:
            job['created_at'] = str(job['created_at'])
            job['updated_at'] = str(job['updated_at'])
            if job.get('from_date'):
                job['from_date'] = str(job['from_date'])
            if job.get('to_date'):
                job['to_date'] = str(job['to_date'])
        return job
