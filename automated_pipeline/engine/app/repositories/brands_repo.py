from app.core.db import get_connection

class BrandRepository:

    @staticmethod
    def get_brands_not_in_master_outlet_products():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT 
            b.id 
        FROM brands b 
        LEFT JOIN master_outlet_products m ON m.master_outlet_id = b.id 
        WHERE m.master_outlet_id IS NULL;
        """

        cursor.execute(query)
        result = cursor.fetchall()

        cursor.close()
        conn.close()

        return result

    @staticmethod
    def search_brands(query: str):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Search in brands table
        sql = "SELECT id, brand_name FROM brands WHERE brand_name LIKE %s LIMIT 10"
        cursor.execute(sql, (f"%{query}%",))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    @staticmethod
    def get_brands_with_cluster_status():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        # Select all brands and join with clusters to see which ones have it
        query = """
            SELECT 
                b.id, 
                b.brand_name, 
                pc.id as cluster_id,
                pc.created_at as clustered_at
            FROM brands b
            LEFT JOIN product_clusters pc ON b.id = pc.master_outlet_id
            ORDER BY pc.id DESC, b.brand_name ASC
        """
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    @staticmethod
    def get_cluster_details(master_outlet_id: int):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM product_clusters WHERE master_outlet_id = %s", (master_outlet_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
