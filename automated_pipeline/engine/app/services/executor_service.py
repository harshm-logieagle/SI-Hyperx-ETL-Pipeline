import os
import csv
import json
import shutil
import time
import ast
import requests
import pandas as pd
import mysql.connector
from mysql.connector import Error
from tqdm import tqdm
from groq import Groq
from concurrent.futures import ThreadPoolExecutor, as_completed

client = Groq(api_key=GROQ_API_KEY)

def fetch_brand_name(master_outlet_id, db_config):
    """Fetch brand name from database"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT brand_name FROM outlets WHERE id = %s"
        cursor.execute(query, (master_outlet_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return result['brand_name']
        else:
            print(f'⚠️  No brand found for outlet ID: {master_outlet_id}')
            return None
    except Error as e:
        print(f'❌ Error fetching brand name: {e}')
        return None

def fetch_calls_for_outlet(master_outlet_id, brand_name, db_config, start_date, end_date, limit, min_duration):
    """Fetch calls for a specific outlet"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        query = f"""
            SELECT
                c.id, c.master_outlet_id, c.outlet_id, c.call_recording_url, o.state
            FROM 
                customer_call_record_logs c
            LEFT JOIN
                call_recording_analytics_details a
                ON c.id = a.customer_call_record_id
            JOIN 
                outlets o
                ON c.outlet_id = o.id
            WHERE
                c.master_outlet_id = %s
                AND c.call_date_time BETWEEN %s AND %s
                AND c.call_recording_url != ''
                AND call_status = 'Connected'
                AND call_duration > %s
            ORDER BY c.id DESC
            LIMIT %s
        """
        
        cursor.execute(query, (master_outlet_id, start_date, end_date, min_duration, limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        df = pd.DataFrame(results)
        df['brand_name'] = brand_name
        
        print(f'✅ Fetched {len(df)} calls for {brand_name} (ID: {master_outlet_id})')
        return df
        
    except Error as e:
        print(f'❌ Database error: {e}')
        return pd.DataFrame()


