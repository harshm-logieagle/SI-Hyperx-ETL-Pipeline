from app.core.db import get_connection

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Queue table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS automated_processing_queue (
        id INT AUTO_INCREMENT PRIMARY KEY,
        master_outlet_id INT NOT NULL,
        brand_name VARCHAR(255),
        status ENUM('pending', 'processing', 'review_pending', 'completed', 'failed') DEFAULT 'pending',
        stage VARCHAR(100),
        result_json LONGTEXT,
        error_message TEXT,
        sample_size INT DEFAULT 500,
        min_duration INT DEFAULT 0,
        start_date DATE,
        end_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """)
    
    # Final storage table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_clusters (
        id INT AUTO_INCREMENT PRIMARY KEY,
        master_outlet_id INT NOT NULL,
        brand_name VARCHAR(255),
        product_heirarchy_list LONGTEXT,
        complaint_reasons LONGTEXT,
        enquiry_reasons LONGTEXT,
        request_reasons LONGTEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Tables created successfully")

if __name__ == "__main__":
    create_tables()
