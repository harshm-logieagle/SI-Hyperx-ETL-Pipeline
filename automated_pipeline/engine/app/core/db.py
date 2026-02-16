import mysql.connector
from mysql.connector import pooling
from app.core.config import settings

connection_pool = pooling.MySQLConnectionPool(
    pool_name="brand_pool",
    pool_size=10,
    host=settings.DB_HOST,
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
    database=settings.DB_NAME,
)

def get_connection():
    return connection_pool.get_connection()
