
from etl_pipeline.config import source_engine, target_engine
from sqlalchemy import text

def test_connections():
    try:
        with source_engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).fetchone()
            print(f"Source connection successful: {res}")
        
        with target_engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).fetchone()
            print(f"Target connection successful: {res}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_connections()
