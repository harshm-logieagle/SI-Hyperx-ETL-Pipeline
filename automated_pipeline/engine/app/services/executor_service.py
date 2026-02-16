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
        brands = BrandRepository.get_brands_not_in_master_outlet_products()
        for brand in brands:
            master_outlet_id = brand['id']
            # Check if already in queue
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM automated_processing_queue WHERE master_outlet_id = %s", (master_outlet_id,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                continue
            
            # Check sample calls
            calls = CustomerCallRecordingsRepository.check_sample_calls_exist(master_outlet_id)
            if calls:
                # Add to queue
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
        response_format = {
            'reason_type': 'Complaint',
            'reason': '',
            'products_mentioned': ['', '', '']
        }
        try:
            completion = self.client.chat.completions.create(
                model='openai/gpt-oss-120b', # Using the model from notebook
                messages=[
                    {'role': 'system', 'content': 'You are a helpful assistant that replies with exactly what is asked and in the same exact format every time.'},
                    {'role': 'user', 'content': f"""this is a call to a brand {brand_name}: <transcript>{transcript}</transcript>
I want to understand why they called under 3 headings Request, Complaint or Enquiry. Tag each call as one or the other.
If the reason type is complaint, then pick the reason. If enquiry, then pick the reason. If request, then pick the reason. 
Pull out the products mentioned. Give results as JSON only: {json.dumps(response_format)}"""}
                ],
                response_format={'type': 'json_object'}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"Analysis error: {e}")
            return {}

    def cluster_reason(self, input_list, brand_name):
        # Ported prompts from notebook
        prompt = f"Cluster these reasons for {brand_name}: {input_list}. Return JSON in specific format."
        # ... logic to call LLM for clustering ...
        # (Simplified for now, will implement full version)
        pass

    def execute_pipeline(self, queue_id, master_outlet_id, brand_name):
        try:
            self.update_queue_status(queue_id, status='processing', stage='fetching_calls')
            
            # 1. Fetch Calls
            calls = CustomerCallRecordingsRepository.check_sample_calls_exist(master_outlet_id)
            if not calls:
                self.update_queue_status(queue_id, status='failed', error_message='No sample calls found')
                return

            df_calls = pd.DataFrame(calls)
            df_calls['id'] = range(len(df_calls)) # Local ID for processing
            df_calls['brand_name'] = brand_name

            # 2. Download
            self.update_queue_status(queue_id, stage='downloading_audio')
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self.download_single_mp3, row['call_recording_url'], row['id']): row['id'] for _, row in df_calls.iterrows()}
                results = {}
                for future in as_completed(futures):
                    call_id, path = future.result()
                    results[call_id] = path
            df_calls['downloaded_path'] = df_calls['id'].map(results)
            df_calls = df_calls.dropna(subset='downloaded_path')

            # 3. Transcribe
            self.update_queue_status(queue_id, stage='transcribing_audio')
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.transcribe_audio, path): path for path in df_calls['downloaded_path']}
                transcriptions = {}
                for future in as_completed(futures):
                    path = futures[future]
                    transcriptions[path] = future.result()
            df_calls['audio_to_text'] = df_calls['downloaded_path'].map(transcriptions)

            # 4. Analyze
            self.update_queue_status(queue_id, stage='analyzing_transcripts')
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.process_transcript, brand_name, row['audio_to_text']): i for i, row in df_calls.iterrows()}
                analyses = [future.result() for future in as_completed(futures)]
            
            df_processed = pd.concat([df_calls, pd.DataFrame(analyses)], axis=1)
            # (Cleanup and clustering logic here...)
            
            # 5. Cluster (Placeholder for full clustering logic)
            self.update_queue_status(queue_id, stage='clustering')
            
            # For demonstration, we'll store a mock result JSON
            mock_result = {
                "brand_name": brand_name,
                "product_heirarchy_list": {"Main Category": ["Sub 1", "Sub 2"]},
                "complaint_reasons": ["Reason 1", "Reason 2"],
                "enquiry_reasons": ["Enquiry 1"],
                "request_reasons": ["Request 1"]
            }

            self.update_queue_status(queue_id, status='review_pending', stage='completed', result_json=mock_result)

        except Exception as e:
            self.update_queue_status(queue_id, status='failed', error_message=str(e))

    def run_worker(self):
        """Worker loop to process queue"""
        while True:
            # First, discover new brands
            self.discover_and_queue()
            
            # Find next pending task
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM automated_processing_queue WHERE status = 'pending' ORDER BY created_at LIMIT 1")
            task = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if task:
                self.execute_pipeline(task['id'], task['master_outlet_id'], task['brand_name'])
            else:
                time.sleep(10) # Wait for new tasks
