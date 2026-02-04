import openpyxl
import json
import pymysql
from datetime import datetime

# -------------------------------
# CONFIGURATION
# -------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "harsh",
    "password": "Logieagle@123",
    "database": "staging_final",
    "port": 3306,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.Cursor,
}

EXCEL_FILE_PATH = r"C:\Users\kenap\Downloads\crad.xlsx"
BATCH_SIZE = 500

TABLE_NAME = "call_recording_analytics_details_raw_1"

# id INCLUDED — CSV is the source of truth
COLUMNS = [
    "id",
    "is_webhook",
    "customer_call_record_id",
    "analytic_type",
    "created",
    "modified",
    "text_status",
    "reason",
    "reason_verbatim",
    "master_outlet_id",
    "outlet_id",
    "audio_to_text",
    "reason_type",
    "end_of_call_status",
    "call_language",
    "customer_gender",
    "customer_type",
    "overall_sentiment",
    "summary",
    "is_valid_transcript",
    "transcript",
    "emotions",
    "emotion_verbatims",
    "emotions_json",
    "products",
    "product_sentiments",
    "product_verbatims",
    "product_tags",
    "product_categories",
    "products_mentioned_json",
    "l1_reason",
    "l2_reason",
    "l3_reason",
    "brand_sentiment",
    "l0_reason",
]

# -------------------------------
# HELPERS
# -------------------------------
def clean(value):
    if value in ("", "NULL", None):
        return None
    return value

def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value or value in ("", "NULL"):
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S") # Adjust format if needed
    except Exception:
        try:
            return datetime.strptime(str(value), "%d-%m-%Y %H:%M")
        except Exception:
            return None

def parse_json(value):
    """
    Ensures the value is returned as a valid JSON string for MySQL.
    """
    if not value or value in ("", "NULL"):
        return None
    try:
        if isinstance(value, str):
            # Validate it's valid JSON and re-serialize to ensure double quotes/proper format
            return json.dumps(json.loads(value))
        elif isinstance(value, (dict, list)):
            # If already an object, convert to JSON string
            return json.dumps(value)
        return None
    except Exception as e:
        # Optionally logging the error can help debug malformed data in Excel
        # print(f"JSON Parse Error: {e} for value: {value}")
        return None

def parse_int(value):
    if value in ("", "NULL", None):
        return None
    try:
        return int(value)
    except Exception:
        return None

# -------------------------------
# MAIN LOAD LOGIC
# -------------------------------
connection = pymysql.connect(**DB_CONFIG)
cursor = connection.cursor()

placeholders = ",".join(["%s"] * len(COLUMNS))
columns_sql = ",".join(COLUMNS)

insert_sql = f"""
INSERT INTO {TABLE_NAME} ({columns_sql})
VALUES ({placeholders})
"""

batch = []
total_inserted = 0

# Load workbook
wb = openpyxl.load_workbook(EXCEL_FILE_PATH, read_only=True, data_only=True)
sheet = wb.active

# Get headers from the first row
headers = [cell.value for cell in sheet[1]]

for row_cells in sheet.iter_rows(min_row=2, values_only=True):
    row = dict(zip(headers, row_cells))
    record = []

    for col in COLUMNS:
        raw_value = row.get(col)

        # Check if the column exists in Excel headers (case-sensitive)
        if raw_value is None and col not in headers:
            # If the JSON field is missing from headers, it might be named differently in Excel
            pass 

        value = clean(raw_value)

        if col in ("created", "modified"):
            value = parse_datetime(value)

        elif col in (
            "id",
            "is_webhook",
            "text_status",
            "is_valid_transcript",
            "analytic_type",
            "customer_call_record_id",
            "master_outlet_id",
            "outlet_id",
        ):
            value = parse_int(value)

        elif col in ("emotions_json", "products_mentioned_json"):
            value = parse_json(value)

        record.append(value)

    batch.append(tuple(record))

    if len(batch) >= BATCH_SIZE:
        cursor.executemany(insert_sql, batch)
        connection.commit()
        total_inserted += len(batch)
        print(f"Inserted {total_inserted} rows...")
        batch.clear()

# Flush remaining rows
if batch:
    cursor.executemany(insert_sql, batch)
    connection.commit()
    total_inserted += len(batch)

cursor.close()
connection.close()

print(f"Load complete. Total rows inserted: {total_inserted}")
