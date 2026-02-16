import os
import json
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from groq import Groq
from app.core.db import get_connection
from app.core.config import settings
from app.repositories.brands_repo import BrandRepository
from app.repositories.customer_call_recordings_repo import CustomerCallRecordingsRepository

class ExecutorService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.download_dir = "downloads"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def update_queue_status(self, queue_id, status=None, stage=None, result_json=None, error_message=None):
        conn = get_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        if status:
            updates.append("status = %s")
            params.append(status)
        if stage:
            updates.append("stage = %s")
            params.append(stage)
        if result_json:
            updates.append("result_json = %s")
            params.append(json.dumps(result_json, ensure_ascii=False))
        if error_message:
            updates.append("error_message = %s")
            params.append(error_message)
        
        if updates:
            query = f"UPDATE automated_processing_queue SET {', '.join(updates)} WHERE id = %s"
            params.append(queue_id)
            cursor.execute(query, tuple(params))
            conn.commit()
        cursor.close()
        conn.close()

    def discover_and_queue(self):
        """Find brands that need processing and add to queue"""
        try:
            brands = BrandRepository.get_brands_not_in_master_outlet_products()
            for brand in brands:
                master_outlet_id = brand['id']
                # Check if already in queue
                conn = get_connection()
                cursor = conn.cursor(dictionary=True, buffered=True)
                cursor.execute("SELECT id FROM automated_processing_queue WHERE master_outlet_id = %s", (master_outlet_id,))
                exists = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if exists:
                    continue
                
                # Check sample calls (default filter for auto-discovery)
                calls = CustomerCallRecordingsRepository.check_sample_calls_exist(master_outlet_id)
                if calls:
                    # Add to queue
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True, buffered=True)
                    # Need brand name first
                    cursor.execute("SELECT brand_name FROM brands WHERE id = %s LIMIT 1", (master_outlet_id,))
                    brand_data = cursor.fetchone()
                    brand_name = brand_data['brand_name'] if brand_data else f"Brand {master_outlet_id}"
                    
                    cursor.execute(
                        "INSERT INTO automated_processing_queue (master_outlet_id, brand_name, status, stage) VALUES (%s, %s, 'pending', 'discovered')",
                        (master_outlet_id, brand_name)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
        except Exception as e:
            print(f"Discovery error: {e}")

    def download_single_mp3(self, url, call_id):
        filename = os.path.join(self.download_dir, f'recording_{call_id}.mp3')
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
            return call_id, filename
        except Exception as e:
            print(f'Failed to download {url}: {e}')
            return call_id, None

    def transcribe_audio(self, audio_path):
        try:
            with open(audio_path, 'rb') as file:
                transcription = self.client.audio.translations.create(
                    file=(audio_path, file.read()),
                    model='whisper-large-v3',
                    response_format='verbose_json'
                )
            return transcription.text
        except Exception as e:
            print(f'Error processing {audio_path}: {e}')
            return ""

    def process_transcript(self, brand_name, transcript):
        if not transcript or len(transcript) < 50:
            return {}
            
        response_format = {
            'reason_type': 'Complaint', # Must be Request, Complaint or Enquiry
            'reason': '',
            'products_mentioned': [] 
        }
        try:
            completion = self.client.chat.completions.create(
                model='llama-3.1-70b-versatile',
                messages=[
                    {'role': 'system', 'content': 'You are a precise call analyst. Extract call details in JSON format only.'},
                    {'role': 'user', 'content': f"""Analyze this call transcript for brand '{brand_name}':
<transcript>{transcript}</transcript>

1. Categorize: Request, Complaint, or Enquiry.
2. Extract the specific reason for the call.
3. List products/services mentioned.

Format as JSON: {json.dumps(response_format)}"""}
                ],
                response_format={'type': 'json_object'}
            )
            data = json.loads(completion.choices[0].message.content)
            # Normalize reason_type
            rt = str(data.get('reason_type', '')).capitalize()
            if rt not in ['Complaint', 'Enquiry', 'Request']:
                data['reason_type'] = 'Enquiry' # Default
            else:
                data['reason_type'] = rt
            return data
        except Exception as e:
            print(f"Analysis error: {e}")
            return {}

    def cluster_reasons(self, reasons_list, brand_name, category):
        if not reasons_list:
            return []
        try:
            prompt = f"""I have a list of raw call reasons for {brand_name} in the category '{category}':
{json.dumps(reasons_list)}

Task: Cluster these into a clean list of 5-10 unique, high-level reason categories.
Return ONLY a JSON array of strings.
Example: ["Product Quality Issue", "Delivery Delay", "Price Inquiry"]"""

            completion = self.client.chat.completions.create(
                model='llama-3.1-70b-versatile',
                messages=[
                    {'role': 'system', 'content': 'You are a data clustering expert. Return JSON arrays only.'},
                    {'role': 'user', 'content': prompt}
                ],
                response_format={'type': 'json_object'}
            )
            content = completion.choices[0].message.content
            # The model might return {"reasons": [...]} or just [...] if we're lucky, 
            # but with json_object it needs a key.
            data = json.loads(content)
            if isinstance(data, dict):
                # Try to find the array in the dict
                for val in data.values():
                    if isinstance(val, list):
                        return val
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Clustering error ({category}): {e}")
            return list(set(reasons_list))[:10] # Fallback to unique items

    def generate_product_hierarchy(self, products_list, brand_name):
        if not products_list:
            return {"General": ["Service"]}
        try:
            prompt = f"""I have a list of raw products/services mentioned in calls for {brand_name}:
{json.dumps(list(set(products_list)))}

Task: Organize these into a hierarchical structure (Category -> Sub-products).
Return ONLY a JSON object where keys are Categories and values are lists of Sub-products.
Example: {{"Electronics": ["Mobile", "Laptop"], "Home": ["AC", "Fan"]}}"""

            completion = self.client.chat.completions.create(
                model='llama-3.1-70b-versatile',
                messages=[
                    {'role': 'system', 'content': 'You are a product taxonomy expert. Return a JSON object mapping categories to lists.'},
                    {'role': 'user', 'content': prompt}
                ],
                response_format={'type': 'json_object'}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"Hierarchy error: {e}")
            return {"Other": list(set(products_list))[:20]}

    def execute_pipeline(self, task):
        queue_id = task['id']
        master_outlet_id = task['master_outlet_id']
        brand_name = task['brand_name']
        
        # Configuration
        sample_size = task.get('sample_size', 500)
        min_duration = task.get('min_duration', 0)
        start_date = task.get('start_date')
        end_date = task.get('end_date')

        try:
            self.update_queue_status(queue_id, status='processing', stage='fetching_calls')
            
            # 1. Fetch Calls
            calls = CustomerCallRecordingsRepository.check_sample_calls_exist(
                master_outlet_id, 
                sample_size=sample_size,
                min_duration=min_duration,
                start_date=start_date,
                end_date=end_date
            )
            
            if not calls:
                self.update_queue_status(queue_id, status='failed', error_message='No sample calls found matching criteria')
                return

            df_calls = pd.DataFrame(calls)
            df_calls['internal_id'] = range(len(df_calls))
            
            # 2. Download
            self.update_queue_status(queue_id, stage='downloading_audio')
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(self.download_single_mp3, row['call_recording_url'], row['internal_id']): row['internal_id'] for _, row in df_calls.iterrows()}
                paths = {}
                for future in as_completed(futures):
                    cid, path = future.result()
                    if path: paths[cid] = path
            
            df_calls['downloaded_path'] = df_calls['internal_id'].map(paths)
            df_calls = df_calls.dropna(subset=['downloaded_path'])

            if df_calls.empty:
                self.update_queue_status(queue_id, status='failed', error_message='Failed to download any recordings')
                return

            # 3. Transcribe
            self.update_queue_status(queue_id, stage='transcribing_audio')
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.transcribe_audio, path): path for path in df_calls['downloaded_path']}
                transcriptions = {futures[f]: f.result() for f in as_completed(futures)}
            
            df_calls['transcript'] = df_calls['downloaded_path'].map(transcriptions)

            # 4. Analyze
            self.update_queue_status(queue_id, stage='analyzing_transcripts')
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(self.process_transcript, brand_name, t) for t in df_calls['transcript']]
                analyses = [f.result() for f in as_completed(futures)]
            
            # Flatten analyses and group data
            complaints = []
            enquiries = []
            requests = []
            all_products = []

            for res in analyses:
                if not res: continue
                rt = res.get('reason_type')
                reason = res.get('reason')
                products = res.get('products_mentioned', [])
                
                if rt == 'Complaint': complaints.append(reason)
                elif rt == 'Enquiry': enquiries.append(reason)
                elif rt == 'Request': requests.append(reason)
                
                if isinstance(products, list):
                    all_products.extend(products)

            # 5. Cluster & Structure
            self.update_queue_status(queue_id, stage='clustering')
            
            final_result = {
                "brand_name": brand_name,
                "product_heirarchy_list": self.generate_product_hierarchy(all_products, brand_name),
                "complaint_reasons": self.cluster_reasons(complaints, brand_name, "Complaint"),
                "enquiry_reasons": self.cluster_reasons(enquiries, brand_name, "Enquiry"),
                "request_reasons": self.cluster_reasons(requests, brand_name, "Request")
            }

            self.update_queue_status(queue_id, status='review_pending', stage='completed', result_json=final_result)
            
            # Cleanup downloads
            for path in df_calls['downloaded_path']:
                try: os.remove(path)
                except: pass

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.update_queue_status(queue_id, status='failed', error_message=str(e))

    def run_worker(self):
        """Worker loop to process queue"""
        print("Worker starting...")
        while True:
            try:
                # First, discover new brands
                self.discover_and_queue()
                
                # Find next pending task
                conn = get_connection()
                cursor = conn.cursor(dictionary=True, buffered=True)
                cursor.execute("SELECT * FROM automated_processing_queue WHERE status = 'pending' ORDER BY created_at LIMIT 1")
                task = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if task:
                    print(f"Processing task {task['id']} for brand {task['brand_name']}")
                    self.execute_pipeline(task)
                else:
                    time.sleep(10) # Wait for new tasks
            except Exception as e:
                print(f"Worker loop error: {e}")
                time.sleep(10) # Wait before retry if loop fails
