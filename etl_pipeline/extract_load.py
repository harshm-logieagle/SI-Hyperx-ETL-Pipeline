from sqlalchemy import text
from config import source_engine, target_engine
import time

BATCH_SIZE = 500

BASE_EXTRACT_SQL = """
SELECT
    id, master_outlet_id, category, product_name, product_embedding
FROM product_hierarchy
WHERE master_outlet_id = :master_outlet_id
ORDER BY id ASC
LIMIT :limit OFFSET :offset
"""

COLUMNS = [
    c.strip() for c in
    BASE_EXTRACT_SQL.split("SELECT")[1].split("FROM")[0].split(",")
]

INSERT_SQL = f"""
INSERT INTO staging.product_hierarchy_raw
({', '.join(f'`{c}`' for c in COLUMNS)})
VALUES ({', '.join(f':{c}' for c in COLUMNS)})
"""


def extract_and_load(moi):
    total = 0
    offset = 0
    start_time = time.time()

    print("Starting ETL pipeline...")

    try:
        with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
            print("Connecting to source and target databases...")

            while True:
                result = src_conn.execute(
                    text(BASE_EXTRACT_SQL),
                    {
                        "master_outlet_id": moi,
                        "limit": BATCH_SIZE,
                        "offset": offset
                    }
                )

                rows = result.fetchall()
                result.close()

                if not rows:
                    break  # No more data — exit gracefully

                batch = [dict(row._mapping) for row in rows]

                with tgt_conn.begin():
                    tgt_conn.execute(text(INSERT_SQL), batch)

                total += len(batch)
                offset += BATCH_SIZE

                elapsed = time.time() - start_time
                avg_speed = total / elapsed if elapsed > 0 else 0

                print(
                    f"Loaded {total} rows "
                    f"({elapsed:.1f}s, {avg_speed:.1f} rows/s)"
                )

        print(f"ETL completed successfully. Total rows: {total}")
        print(f"Total time: {time.time() - start_time:.2f}s")

    except Exception as e:
        print(f"Error during ETL: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    extract_and_load(321091)
