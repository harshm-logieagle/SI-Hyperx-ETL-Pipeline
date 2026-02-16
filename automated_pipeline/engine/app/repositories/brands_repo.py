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
