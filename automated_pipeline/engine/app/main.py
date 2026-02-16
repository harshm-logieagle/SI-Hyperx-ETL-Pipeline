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
    created_at: str

class UpdateResult(BaseModel):
    result_json: dict

@app.get("/api/queue")
def get_queue():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, master_outlet_id, brand_name, status, stage, created_at FROM automated_processing_queue ORDER BY created_at DESC")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    # Convert datetime to string
    for item in items:
        item['created_at'] = str(item['created_at'])
    return items

@app.get("/api/queue/{item_id}")
def get_queue_item(item_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
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
def approve_result(item_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM automated_processing_queue WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    if not item:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
    
    result = json.loads(item['result_json'])
    
    # Store in final table
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
    return {"message": "Approved and saved"}

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
