
from etl_pipeline.config import source_engine, target_engine
from sqlalchemy import text

def create_staging_table(table_name):
    with source_engine.connect() as conn:
        columns = conn.execute(text(f"DESCRIBE {table_name}")).fetchall()
    
    col_defs = []
    for col in columns:
        field_name = col[0]
        field_type = col[1]
        col_defs.append(f"`{field_name}` {field_type} NULL")
    
    create_sql = f"CREATE TABLE IF NOT EXISTS staging.{table_name}_raw (\n  " + ",\n  ".join(col_defs) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
    print("Creating table with SQL:")

    with target_engine.connect() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS staging"))
        conn.execute(text(f"DROP TABLE IF EXISTS staging.{table_name}_raw"))
        conn.execute(text(create_sql))
        conn.commit()
    
    print(f"Table staging.{table_name}_raw created successfully.")

if __name__ == "__main__":
    create_staging_table("product_hierarchy")
