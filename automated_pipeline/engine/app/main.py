from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json

from app.services.executor_service import ExecutorService
from app.core.db import get_connection

app = FastAPI(title="Automated Pipeline Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ExecutorService()

class QueueItem(BaseModel):
    id: int
    master_outlet_id: int
    brand_name: Optional[str]
    status: str
    stage: Optional[str]
    sample_size: Optional[int]
    min_duration: Optional[int]
    start_date: Optional[str]
    end_date: Optional[str]
    created_at: str

class QueueAddRequest(BaseModel):
    master_outlet_id: int
    brand_name: str
    sample_size: int = 500
    min_duration: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class UpdateResult(BaseModel):
    result_json: dict

@app.get("/api/queue")
def get_queue():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM automated_processing_queue ORDER BY created_at DESC")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    # Convert datetime to string
    for item in items:
        item['created_at'] = str(item['created_at'])
        if item.get('start_date'): item['start_date'] = str(item['start_date'])
        if item.get('end_date'): item['end_date'] = str(item['end_date'])
    return items

@app.get("/api/queue/{item_id}")
def get_queue_item(item_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM automated_processing_queue WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    cursor.close()
    conn.close()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item['created_at'] = str(item['created_at'])
    item['updated_at'] = str(item['updated_at'])
    if item['result_json']:
        item['result_json'] = json.loads(item['result_json'])
    return item

@app.post("/api/queue/add")
def add_to_queue(data: QueueAddRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO automated_processing_queue 
        (master_outlet_id, brand_name, sample_size, min_duration, start_date, end_date, status, stage)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'queued_by_user')
    """, (data.master_outlet_id, data.brand_name, data.sample_size, data.min_duration, data.start_date, data.end_date))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Added to queue successfully"}

@app.get("/api/brands/search")
def search_brands(q: str):
    from app.repositories.brands_repo import BrandRepository
    return BrandRepository.search_brands(q)

@app.get("/api/brands/{brand_id}/cluster")
def check_cluster(brand_id: int):
    from app.repositories.brands_repo import BrandRepository
    exists = BrandRepository.check_cluster_exists(brand_id)
    return {"exists": exists}

@app.post("/api/queue/{item_id}/update")
def renovate_result(item_id: int, data: UpdateResult):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE automated_processing_queue SET result_json = %s WHERE id = %s", (json.dumps(data.result_json), item_id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Updated successfully"}

@app.post("/api/queue/{item_id}/approve")
def approve_result(item_id: int, data: Optional[UpdateResult] = None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    # If data is provided, update the queue first
    if data:
        cursor.execute("UPDATE automated_processing_queue SET result_json = %s WHERE id = %s", (json.dumps(data.result_json), item_id))
        conn.commit()

    cursor.execute("SELECT * FROM automated_processing_queue WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    if not item:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
    
    result = json.loads(item['result_json']) if item['result_json'] else {}
    
    # Store in final table (Upsert logic - delete existing first)
    cursor.execute("DELETE FROM product_clusters WHERE master_outlet_id = %s", (item['master_outlet_id'],))
    
    cursor.execute("""
        INSERT INTO product_clusters 
        (master_outlet_id, brand_name, product_heirarchy_list, complaint_reasons, enquiry_reasons, request_reasons)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        item['master_outlet_id'],
        item['brand_name'],
        json.dumps(result.get('product_heirarchy_list', {})),
        json.dumps(result.get('complaint_reasons', [])),
        json.dumps(result.get('enquiry_reasons', [])),
        json.dumps(result.get('request_reasons', []))
    ))
    
    # Update status
    cursor.execute("UPDATE automated_processing_queue SET status = 'completed' WHERE id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Approved and saved successfully"}

@app.get("/api/brands/all")
def get_all_brands():
    from app.repositories.brands_repo import BrandRepository
    brands = BrandRepository.get_brands_with_cluster_status()
    for b in brands:
        if b.get('clustered_at'):
            b['clustered_at'] = str(b['clustered_at'])
    return brands

@app.get("/api/clusters/{brand_id}")
def get_cluster(brand_id: int):
    from app.repositories.brands_repo import BrandRepository
    cluster = BrandRepository.get_cluster_details(brand_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    # Format for editor
    return {
        "master_outlet_id": cluster['master_outlet_id'],
        "brand_name": cluster['brand_name'],
        "result_json": {
            "product_heirarchy_list": json.loads(cluster['product_heirarchy_list']),
            "complaint_reasons": json.loads(cluster['complaint_reasons']),
            "enquiry_reasons": json.loads(cluster['enquiry_reasons']),
            "request_reasons": json.loads(cluster['request_reasons'])
        }
    }

@app.post("/api/clusters/{brand_id}/update")
def update_cluster(brand_id: int, data: UpdateResult):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)
    
    cursor.execute("""
        UPDATE product_clusters 
        SET product_heirarchy_list = %s, 
            complaint_reasons = %s, 
            enquiry_reasons = %s, 
            request_reasons = %s
        WHERE master_outlet_id = %s
    """, (
        json.dumps(data.result_json.get('product_heirarchy_list', {})),
        json.dumps(data.result_json.get('complaint_reasons', [])),
        json.dumps(data.result_json.get('enquiry_reasons', [])),
        json.dumps(data.result_json.get('request_reasons', [])),
        brand_id
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Cluster updated successfully"}

@app.post("/api/discover")
def trigger_discovery(background_tasks: BackgroundTasks):
    background_tasks.add_task(executor.discover_and_queue)
    return {"message": "Discovery started"}

@app.post("/api/worker/start")
def start_worker(background_tasks: BackgroundTasks):
    background_tasks.add_task(executor.run_worker)
    return {"message": "Worker started"}

# Serve frontend
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
