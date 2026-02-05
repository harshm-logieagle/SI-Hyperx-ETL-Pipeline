import mysql.connector
from mysql.connector import Error
import json
import os

from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

INSERT_SQL = """
INSERT INTO decision_nodes
(master_outlet_id, parent_id, node_type, label, description, is_active)
VALUES (%s, %s, %s, %s, %s, %s)
"""

def insert_node(cursor, node, parent_db_id=None):
    """
    Inserts a node, then recursively inserts its children.
    Returns the DB-generated id of the inserted node.
    """

    data = (
        node["outlet_id"],
        parent_db_id,
        node["node_type"],
        node["label"],
        node.get("description", ""),
        node["is_active"],
    )

    cursor.execute(INSERT_SQL, data)
    current_db_id = cursor.lastrowid

    # Recursively insert children
    for child in node.get("children", []):
        insert_node(cursor, child, current_db_id)

    return current_db_id


def main():
    # Load JSON (inline or from file)
    with open(r"D:\Harsh\Projects-Working\SingleInterface - HyperX\whimsical_json\atomberg.json", "r", encoding="utf-8") as f:
        tree = json.load(f)

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.start_transaction()
        cursor = conn.cursor()

        # Insert root (parent_id = NULL)
        insert_node(cursor, tree, None)

        conn.commit()
        print("Decision tree inserted successfully.")

    except Error as e:
        conn.rollback()
        print("Error occurred. Transaction rolled back.")
        print(e)

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == "__main__":
    main()
