import json
from groq import Groq
import httpx
import os
import urllib.parse
import mysql.connector
import requests
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    http_client=httpx.Client()
)

def levenshtein_distance(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0:
                dp[i][j] = j
            elif j == 0:
                dp[i][j] = i
            elif s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j],
                                   dp[i][j - 1],
                                   dp[i - 1][j - 1])
    distance = dp[m][n]
    return distance

def closest_match(string_list, input_string):
    print(f"Finding closest match for '{input_string}' in list of {len(string_list)} items")
    if not string_list:
        return input_string
    if input_string in string_list:
        print(f"Exact match found: {input_string}")
        return input_string

    closest_string = min(string_list, key=lambda s: levenshtein_distance(s, input_string))
    print(f"Closest match: '{input_string}' -> '{closest_string}'")
    return closest_string

def detect_language(audio_url, state, timeout=180):
    print(f"Detecting language for audio URL: {audio_url} with state: {state}")
    if state and state != '':
        url = 'https://language1-detection.singleinterface.com/detect-language-with-state'
        payload = {
            "url": audio_url,
            "state": state
        }
    else:
        url = 'https://language1-detection.singleinterface.com/detect-language'
        payload = {
            "url": audio_url
        }

    headers = {
        'Content-Type': 'application/json'
    }
    try:
        print(f"Calling language detection API: {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        print(f"Language detection result: {result}")
        return result.get('language', '')
    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
        print(f"Language detection failed: {str(e)}")
        return ''

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

SYSTEM_PROMPT = """
You are a hierarchical workflow traversal engine designed to analyze interaction transcripts and extract structured traversal paths based strictly on a provided workflow tree.

IMPORTANT ROOT RULE:
- The root node is structural only.
- The root must NEVER appear in output.
- Traversal must begin from children of root.
- Level 0 corresponds to children of root.

You must:
- Detect all conversational journeys
- Traverse hierarchy strictly
- Use ONLY labels present in workflow tree
- Maintain sequential level numbering starting from 0
- Stop traversal when transcript evidence ends
- Return valid JSON only
"""

BA_USER_PROMPT_TEMPLATE = """
You are analyzing a customer call made to the brand "{brand_name}".
The call transcript is provided below. This transcript may contain transcription errors, spelling mistakes, or translation artifacts due to audio-to-text processing.

TRANSCRIPT
<transcript>
{transcript}
</transcript>

OBJECTIVE
Your task is to generate structured base analytics for this call by extracting intent, reasons, products, sentiment, emotions, and conversation metadata.
You must strictly follow the rules below. The output must always be valid JSON and must strictly conform to the provided response format.

CALL INTENT CLASSIFICATION
Classify the primary reason for the call into EXACTLY ONE of the following types:
- Complaint  
- Enquiry  
- Request  

Definitions:
- Complaint → The customer expresses dissatisfaction or reports an issue.
- Request → The customer asks for support, help, or action.
- Enquiry → The customer is seeking information or making a sales-related query.

Rules:
- The reason_type must never be null or empty.
- Choose the single most dominant reason type for the call.
- Provide a verbatim excerpt from the transcript that supports this classification.

REASON SELECTION
You will be provided a single dictionary of valid call reasons with their corresponding type.
- If reason_type = "Complaint":
  - Select the reason ONLY from <complaint_reasons>.
- If reason_type = "Enquiry":
  - Select the reason ONLY from <enquiry_reasons>.
- If reason_type = "Request":
  - Select the reason ONLY from <request_reasons>.

Rules:
- You MUST select the reason strictly from the relevant list.
- Do NOT infer or invent reasons.
- Do NOT pick reasons from product names or unrelated text.

END OF CALL STATUS
Determine how the call was handled or concluded.
- Select the end_of_call_status ONLY from the provided <handled_list>.
- Choose the value that best reflects how the call outcome was addressed.

PRODUCT MENTION EXTRACTION
Extract products mentioned in the call using ONLY the following product list:
{product_list}
...
Note: This list represents a curated subset of the outlet's inventory and does not reflect the complete product portfolio. Leverage contextual intelligence and historical naming conventions to accurately infer the intended product from the transcript.

Rules:
- Products may be misspelled due to transcription errors — account for phonetic or spelling variations.
- Only extract products that clearly map to names in the provided list.
- Do NOT extract generic terms (e.g., "bike", "phone", "model").
- If no product from the list is mentioned, return an empty string for the product field.

For EACH extracted product:
- product → Exact product name from the list
- reason_type → One of: Complaint, Enquiry, Request (based on context of THIS specific product)
- reason → The specific reason from the relevant list (<complaint_reasons>, <enquiry_reasons>, or <request_reasons>) that applies to this product
- end_of_call_status → One of the values from <handled_list> that applies specifically to this product's outcome
- product_sentiment → One of: Positive, Negative, Neutral (must never be empty)
- product_verbatim → Transcript excerpt supporting the sentiment (empty string allowed)
- tags → Keywords describing product context (e.g., "out of stock", "damaged", "price", "availability")

Rules:
- Tags may be positive or negative.
- product_mentions MUST be an array of objects.
- Each object must be properly formatted JSON.

OVERALL CALL SENTIMENT
Determine the overall sentiment of the call:
- Positive
- Negative
- Neutral

Rules:
- Classify as Negative ONLY if sentiment is clearly negative.
- Informational statements (e.g., “out of stock”) alone do NOT imply negative sentiment.
- If the call is informational or neutral in tone, classify as Neutral.

EMOTION DETECTION
Select emotions ONLY from the list below:
(neutral, sadness, anger, frustration, happiness, fear, confusion, satisfaction)

Rules:
- Choose the dominant emotion(s).
- If no strong emotional indicators are present, respond with "neutral".
- Provide verbatim transcript excerpts supporting the detected emotion(s).
- emotions must be an array of objects.

CUSTOMER METADATA
Customer Type:
- One of: New, Existing, Unsure
- Infer only if supported by the conversation.

Customer Gender:
- One of: Male, Female, Unsure
- Infer only if supported by explicit address terms (e.g., "sir", "ma’am").
- Do NOT guess.

CALL SUMMARY
Generate a short, neutral summary of the call.
Rules:
- Refer to the customer as “the customer” unless a name is explicitly stated.
- The brand name must NEVER be treated as the customer name.
- Do NOT mention:
  - customer gender
  - customer type
  - sentiment labels
- Focus only on what happened in the call.

DIARIZATION
Provide a dialogue-style diarization of the call:
- Prefix each line with "agent:" or "customer:"
- Preserve conversational flow.
- Do not fabricate dialogue.

OUTPUT REQUIREMENTS
- Output MUST be valid JSON.
- Output MUST match the provided response format exactly.
- Use empty strings or empty arrays where data is not available.
- Never include explanations or text outside JSON.
- Only use values from the provided lists for restricted fields.

RESPONSE FORMAT
<response_format>
{{
    "reason_type": "Complaint",
    "reason_verbatim": "",
    "reason": "",
    "end_of_call_status": "",
    "products_mentioned": [
        {{
            "product": "",
            "reason_type": "",
            "reason": "",
            "end_of_call_status": "",
            "product_sentiment": "",
            "product_verbatim": "",
            "tags": ["", ""],
            "category": ""
        }},
        {{
            "product": "",
            "reason_type": "",
            "reason": "",
            "end_of_call_status": "",
            "product_sentiment": "",
            "product_verbatim": "",
            "tags": ["", ""],
            "category": ""
        }}
    ],
    "overall_sentiment": "",
    "emotions": [
        {{
            "emotion": "",
            "emotion_verbatim": ""
        }}
    ],
    "customer_type": "",
    "customer_gender": "",
    "summary": "",
    "transcript": [
        "agent: how can i help you today?",
        "customer: i want to give my suit for alteration.",
        "agent:..."
    ]
}}
</response_format>
"""

USER_PROMPT_TEMPLATE = """
You are given a conversation transcript, pre-computed base analytics, and a hierarchical workflow tree.
Your task is to extract all valid traversal journeys through the workflow tree based strictly on evidence present in the transcript and base analytics.

INPUTS
- TRANSCRIPT
  {transcript}

- BASE ANALYTICS
  {base_analytics}

- WORKFLOW TREE
  {workflow_tree}

TRAVERSAL RULES

1. Ignore the root node completely.
   - The root node is structural only and must never appear in the output.

2. Traversal entry point
   - Level 0 must always begin from a direct child of the root node.

3. Journey construction
   - For each detected journey:
     - Select exactly one valid child node at each level.
     - Each selected node must be a direct child of the previously selected node.
     - Maintain strict parent-child hierarchy.
     - Continue traversal only while transcript or base analytics evidence supports deeper levels.
     - Stop traversal immediately when no further supported child exists.

4. Multiple journeys
   - If the transcript supports multiple independent journeys:
     - Create separate traversal paths for each.
     - Do not merge multiple journeys into a single path.

NODE TYPE HANDLING

Each node in the workflow tree has a node_type.

1. Classification Nodes
   - If node_type = "Classification":
     - Select the node label based on interpretation of the transcript.
     - Base analytics may be used as supporting context.

2. Extraction Nodes
   - If node_type = "Extraction":
     - The node label represents an entity already extracted.
     - Do NOT return generic labels such as "product".
     - Replace the node label with the actual extracted value (e.g., the real product name).
     - You MUST include a traversal path for every extracted product present in BASE ANALYTICS if supported by transcript evidence.
     - Do NOT re-classify extracted entities.

END OF CALL STATUS HANDLING

- If the workflow tree includes an end-of-call or call outcome node:
  - Populate it with the actual call ending status (e.g., resolved, dropped, follow-up required, transferred, etc.)
    only if explicitly supported by transcript or base analytics.
  - Do not infer or fabricate call outcomes.

OUTPUT REQUIREMENTS

- Return ONLY valid JSON.
- Do NOT include explanations or commentary.
- Do NOT include unused levels.
- Levels must start from 0 and be sequential.
- Each traversal path must be internally consistent and hierarchically valid.

OUTPUT FORMAT

{{
  "reason_paths": [
    {{
      "path_id": 1,
      "node_path": [
        {{ "level": 0, "label": "" }}
      ]
    }}
  ]
}}
"""

def get_product_list(master_outlet_id):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "SELECT name FROM master_outlet_products WHERE master_outlet_id = %s LIMIT 50"
        cursor.execute(query, (master_outlet_id,))
        results = cursor.fetchall()
        return [r[0] for r in results]
    except Error as e:
        print(f"Error fetching product list: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_reasons_by_type(master_outlet_id, reason_type):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "SELECT value FROM master_outlet_call_reasons WHERE master_outlet_id = %s AND type = %s"
        cursor.execute(query, (master_outlet_id, reason_type))
        results = cursor.fetchall()
        return [r[0] for r in results]
    except Error as e:
        print(f"Error fetching reasons for {reason_type}: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_base_analytics(transcript, brand_name, product_list, complaint_reasons, enquiry_reasons, request_reasons, handled_list):
    user_prompt = BA_USER_PROMPT_TEMPLATE.format(
        brand_name=brand_name,
        transcript=transcript,
        product_list=", ".join(product_list),
        complaint_reasons=", ".join(complaint_reasons),
        enquiry_reasons=", ".join(enquiry_reasons),
        request_reasons=", ".join(request_reasons),
        handled_list=", ".join(handled_list)
    )
    
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that replies with exactly what is asked and in the same exact format every time."},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=30000
        )
        result = json.loads(completion.choices[0].message.content)
        
        if "products_mentioned" in result and isinstance(result["products_mentioned"], list):
            for product_data in result["products_mentioned"]:
                original_name = product_data.get("product")
                if original_name and product_list:
                    matched_name = closest_match(product_list, original_name)
                    product_data["product"] = matched_name
        
        return result
    except Exception as e:
        print(f"Base Analytics LLM Error: {e}")
        return {}

def save_base_analytics(master_outlet_id, outlet_id, call_recording_id, base_analytics, call_language=''):
    print("\n[Base Analytics to be stored in call_recording_analytics]")
    
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Prepare list fields
        transcript_lines = base_analytics.get("transcript", [])
        transcript_text = json.dumps(transcript_lines)
        is_valid_transcript = 1 if transcript_lines else 0
        
        emotions_data = base_analytics.get("emotions", [])
        emotions_json = json.dumps(emotions_data)
        emotions_list = [e.get("emotion", "") for e in emotions_data]
        emotion_verbatims_list = [e.get("emotion_verbatim", "") for e in emotions_data]
        emotions_str = "--||--".join(emotions_list)
        emotion_verbatims_str = "--||--".join(emotion_verbatims_list)
        
        products_data = base_analytics.get("products_mentioned", [])
        products_mentioned_json = json.dumps(products_data)
        
        # Product-related summary strings
        product_names = []
        product_sentiments = []
        product_verbatims = []
        product_tags = []
        product_categories = []
        
        # Validated product context to be stored in call_product_mentions
        valid_product_mentions = []

        for p in products_data:
            name = p.get("product")
            if not name:
                continue
                
            sentiment = (p.get("product_sentiment") or "").lower()
            verbatim = p.get("product_verbatim", "")
            tags = p.get("tags", [])
            tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            
            product_names.append(name)
            product_sentiments.append(sentiment)
            product_verbatims.append(verbatim)
            product_tags.append(tags_str)
            
            # Fetch Category and ID from DB
            cursor.execute("""
                SELECT p.id, c.category_name 
                FROM master_outlet_products p
                LEFT JOIN master_outlet_categories c ON p.category_id = c.id
                WHERE p.master_outlet_id = %s AND p.name = %s
            """, (master_outlet_id, name))
            row = cursor.fetchone()
            
            if row:
                prod_id, cat_name = row
                cat_name = cat_name or ""
                product_categories.append(cat_name)
                valid_product_mentions.append({
                    "prod_id": prod_id,
                    "sentiment": sentiment,
                    "verbatim": verbatim,
                    "tags": tags_str
                })
            else:
                product_categories.append("")

        products_str = "--||--".join(product_names)
        sentiments_str = "--||--".join(product_sentiments)
        p_verbatims_str = "--||--".join(product_verbatims)
        p_tags_str = "--||--".join(product_tags)
        p_categories_str = "--||--".join(product_categories)

        # Mapping to table columns
        query = """
            INSERT INTO call_recording_analytics 
            (call_recording_id, master_outlet_id, outlet_id, reason, reason_verbatim, 
             reason_type, end_of_call_status, overall_sentiment, brand_sentiment, 
             customer_gender, customer_type, summary, transcript, audio_to_text, 
             is_valid_transcript, emotions_json, emotions, emotion_verbatims, 
             products_mentioned_json, products, product_sentiments, product_verbatims, 
             product_tags, product_categories, call_language, created, modified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
            reason=VALUES(reason),
            reason_verbatim=VALUES(reason_verbatim),
            reason_type=VALUES(reason_type),
            end_of_call_status=VALUES(end_of_call_status),
            overall_sentiment=VALUES(overall_sentiment),
            brand_sentiment=VALUES(brand_sentiment),
            customer_gender=VALUES(customer_gender),
            customer_type=VALUES(customer_type),
            summary=VALUES(summary),
            transcript=VALUES(transcript),
            audio_to_text=VALUES(audio_to_text),
            is_valid_transcript=VALUES(is_valid_transcript),
            emotions_json=VALUES(emotions_json),
            emotions=VALUES(emotions),
            emotion_verbatims=VALUES(emotion_verbatims),
            products_mentioned_json=VALUES(products_mentioned_json),
            products=VALUES(products),
            product_sentiments=VALUES(product_sentiments),
            product_verbatims=VALUES(product_verbatims),
            product_tags=VALUES(product_tags),
            product_categories=VALUES(product_categories),
            call_language=VALUES(call_language),
            modified=NOW()
        """
        
        data = (
            call_recording_id, master_outlet_id, outlet_id, 
            base_analytics.get("reason"), base_analytics.get("reason_verbatim"),
            base_analytics.get("reason_type"), base_analytics.get("end_of_call_status"),
            base_analytics.get("overall_sentiment").lower(), base_analytics.get("overall_sentiment").lower(),
            base_analytics.get("customer_gender"), base_analytics.get("customer_type"),
            base_analytics.get("summary"), transcript_text, transcript_text,
            is_valid_transcript, emotions_json, emotions_str, emotion_verbatims_str,
            products_mentioned_json, products_str, sentiments_str, p_verbatims_str,
            p_tags_str, p_categories_str, call_language
        )
        
        cursor.execute(query, data)
        conn.commit()
        
        # Fetch analytics record ID
        cursor.execute("SELECT id FROM call_recording_analytics WHERE call_recording_id = %s", (call_recording_id,))
        analytics_result = cursor.fetchone()
        
        if analytics_result:
            analytics_id = analytics_result[0]
            cursor.execute("DELETE FROM call_product_mentions WHERE call_recording_analytics_id = %s", (analytics_id,))
            
            for m in valid_product_mentions:
                mention_query = """
                    INSERT INTO call_product_mentions 
                    (call_recording_analytics_id, master_outlet_product_id, product_sentiment, product_verbatim, tags)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(mention_query, (
                    analytics_id, m["prod_id"], m["sentiment"], m["verbatim"], m["tags"]
                ))
            conn.commit()
            print("Successfully saved product mentions to call_product_mentions table.")
            
        print("Successfully saved base analytics to call_recording_analytics table.")
    except Error as e:
        if conn: conn.rollback()
        print(f"Error saving base analytics: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def get_brand_id_by_name(brand_name):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "SELECT id FROM brands WHERE brand_name = %s"
        cursor.execute(query, (brand_name,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        print(f"Error fetching brand ID: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_root_node_id(master_outlet_id):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = "SELECT id FROM decision_nodes WHERE master_outlet_id = %s AND parent_id IS NULL LIMIT 1"
        cursor.execute(query, (master_outlet_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        print(f"Error fetching root node ID: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_call_details(call_recording_id):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT ccr.call_recording_url, b.brand_name, b.id as master_outlet_id, ccr.outlet_id, o.state
            FROM customer_call_recordings AS ccr
            JOIN brands b ON b.id = ccr.master_outlet_id 
            LEFT JOIN outlets o ON o.id = ccr.outlet_id
            WHERE ccr.id = %s
        """
        cursor.execute(query, (call_recording_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"Error fetching call details: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def save_level_reasons(master_outlet_id, call_recording_id, reason_paths, workflow_tree):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO level_reasons 
            (master_outlet_id, call_recording_id, path_id, level, value)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        for path_entry in reason_paths:
            path_id = path_entry.get("path_id", 1)
            node_path = path_entry.get("node_path", [])
            
            for step in node_path:
                label = step["label"]
                level = step["level"]
                
                data = (
                    master_outlet_id,
                    call_recording_id,
                    path_id,
                    str(level),
                    label
                )
                cursor.execute(insert_query, data)
                print(f"Saved: Level {level}, Label '{label}' for Path {path_id}")
        
        conn.commit()
        print("Successfully saved analysis results to level_reasons table.")
    except Error as e:
        if conn: conn.rollback()
        print(f"Error saving level reasons: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def fetch_decision_nodes_from_db(master_outlet_id):
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, master_outlet_id, parent_id, node_type, label, description, is_active
            FROM decision_nodes
            WHERE master_outlet_id = %s
        """
        cursor.execute(query, (master_outlet_id,))
        rows = cursor.fetchall()

        if not rows:
            return None

        nodes = {}
        roots = []
        for row in rows:
            node = {
                "id": row["id"],
                "outlet_id": row["master_outlet_id"],
                "parent_id": row["parent_id"],
                "node_type": row["node_type"],
                "label": row["label"],
                "description": row["description"] or "",
                "is_active": int(row["is_active"]),
                "children": []
            }
            nodes[node["id"]] = node

        for node_id, node in nodes.items():
            parent_id = node["parent_id"]
            if parent_id is None:
                roots.append(node)
            elif parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                roots.append(node)

        def cleanup_children(node_list):
            for n in node_list:
                if not n["children"]:
                    del n["children"]
                else:
                    cleanup_children(n["children"])

        cleanup_children(roots)

        if not roots:
            return None
        
        if len(roots) > 1:
            if all(r.get("label") == "root" for r in roots):
                merged_children = []
                seen_ids = set()
                for r in roots:
                    for child in r.get("children", []):
                        if child["id"] not in seen_ids:
                            merged_children.append(child)
                            seen_ids.add(child["id"])
                
                return {
                    "id": 0,
                    "outlet_id": master_outlet_id,
                    "parent_id": None,
                    "node_type": "classification",
                    "label": "root",
                    "description": "Unified Workflow Root",
                    "is_active": 1,
                    "children": merged_children
                }
            
            return {
                "id": 0,
                "outlet_id": master_outlet_id,
                "parent_id": None,
                "node_type": "classification",
                "label": "root",
                "description": "Structural Root",
                "is_active": 1,
                "children": roots
            }

        return roots[0]
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def transcribe_audio(audio_path, brand_name):
    print(f"Transcribing audio: {audio_path}")
    try:
        if audio_path.startswith(("http://", "https://")):
            response = httpx.get(audio_path, follow_redirects=True)
            response.raise_for_status()
            audio_bytes = response.content
            content_type = response.headers.get("Content-Type", "").lower()
            extension_map = {
                "audio/wav": ".wav",
                "audio/x-wav": ".wav",
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/m4a": ".m4a",
                "audio/x-m4a": ".m4a",
                "audio/webm": ".webm",
                "audio/mp4": ".mp4"
            }
            detected_ext = None
            for ct, ext in extension_map.items():
                if ct in content_type:
                    detected_ext = ext
                    break
            parsed_url = urllib.parse.urlparse(audio_path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            filename = "audio"
            if "callid" in query_params:
                filename = query_params["callid"][0]
            elif parsed_url.path and parsed_url.path != "/":
                filename = parsed_url.path.split("/")[-1]
            if detected_ext:
                if not filename.lower().endswith(detected_ext):
                    filename += detected_ext
            else:
                valid_extensions = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
                if not filename.lower().endswith(valid_extensions):
                    filename += ".mp3"
            file_to_send = (filename, audio_bytes)
        else:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            with open(audio_path, "rb") as f:
                filename = os.path.basename(audio_path)
                file_to_send = (filename, f.read())
        transcription = client.audio.translations.create(
            file=file_to_send,
            model="whisper-large-v3",
            response_format="verbose_json",
            prompt=brand_name
        )
        return transcription.text
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise

def prune_tree(node):
    if not node.get("is_active", 1):
        return None
    children = []
    for child in node.get("children", []):
        pruned = prune_tree(child)
        if pruned:
            children.append(pruned)
    new_node = {k: v for k, v in node.items() if k != "children"}
    if children:
        new_node["children"] = children
    return new_node

def remove_root_from_paths(reason_paths, root_label):
    cleaned_paths = []
    for path in reason_paths:
        node_path = path.get("node_path", [])
        if node_path and node_path[0]["label"] == root_label:
            node_path = node_path[1:]
        for idx, node in enumerate(node_path):
            node["level"] = idx
        cleaned_paths.append({
            "path_id": path.get("path_id"),
            "node_path": node_path
        })
    return cleaned_paths

def rectify_and_validate_node_path(tree, node_path, product_list):
    if not node_path:
        return None
    
    current_children = tree.get("children", [])
    rectified_path = []
    
    for step in node_path:
        label = step.get("label")
        level = step.get("level")
        
        match = next((c for c in current_children if c["label"] == label), None)
        
        if not match and current_children:
            all_labels_in_tree = [c["label"] for c in current_children]
            
            is_product_layer = any(c.get("node_type") == "Extraction" for c in current_children) or \
                              any(c["label"] in product_list or c["label"] == "product" for c in current_children)

            if is_product_layer and product_list:
                matched_label = closest_match(product_list, label)
                
                match = next((c for c in current_children if c["label"] == matched_label or c["label"] == "product"), None)
                
                if not match:
                    template_match = next((c for c in current_children if c["label"] in product_list or c["label"] == "product"), None)
                    if template_match:
                        print(f"Using '{template_match['label']}' as template for product '{matched_label}'")
                        label = matched_label
                        match = template_match
                    else:
                        label = matched_label
                        rectified_path.append({"level": level, "label": label})
                        print(f"Product '{label}' accepted as untemplated product (Terminal)")
                        return rectified_path
                else:
                    label = matched_label
            else:
                best_label = closest_match(all_labels_in_tree, label)
                match = next((c for c in current_children if c["label"] == best_label), None)
                if match:
                    label = best_label

        if not match:
            if len(rectified_path) <= level:
                return None
            break

        rectified_path.append({"level": level, "label": label})
        current_children = match.get("children", [])
        
    return rectified_path

def process_transcript_with_tree(transcript, base_analytics, workflow_tree, product_list):
    pruned_tree = prune_tree(workflow_tree)
    root_label = pruned_tree["label"]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        transcript=transcript,
        base_analytics=json.dumps(base_analytics, indent=2),
        workflow_tree=json.dumps(pruned_tree, indent=2)
    )
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=30000
        )
        raw_output = json.loads(completion.choices[0].message.content)
        reason_paths = raw_output.get("reason_paths", [])
        
        cleaned_paths = remove_root_from_paths(reason_paths, root_label)
        valid_paths = []
        
        for path in cleaned_paths:
            rectified_path = rectify_and_validate_node_path(pruned_tree, path["node_path"], product_list)
            if rectified_path:
                path["node_path"] = rectified_path
                valid_paths.append(path)

        products_in_analytics = base_analytics.get("products_mentioned", [])
        for prod_data in products_in_analytics:
            prod_name = prod_data.get("product")
            if not prod_name: continue
            
            p_reason_type = prod_data.get("reason_type")
            p_end_status = prod_data.get("end_of_call_status")
            
            found = False
            for p in valid_paths:
                has_product = any(step.get("label") == prod_name for step in p["node_path"])
                has_reason = any(step.get("label") == p_reason_type for step in p["node_path"]) if p_reason_type else True
                has_status = any(step.get("label") == p_end_status for step in p["node_path"]) if p_end_status else True
                if has_product and has_reason and has_status:
                    found = True
                    break
            
            if not found:
                current_children = pruned_tree.get("children", [])
                for child in current_children:
                    is_product_category = any(c.get("label") in product_list or c.get("label") == "product" for c in child.get("children", []))
                    
                    if child.get("label") == prod_name:
                        new_path = [{"level": 0, "label": prod_name}]
                        if p_reason_type:
                            new_path.append({"level": 1, "label": p_reason_type})
                            # Check if reason_type has end-of-call child
                            reason_node = next((c for c in (child.get("children", []) if "children" in child else []) if c.get("label") == p_reason_type), None)
                            if reason_node and p_end_status:
                                has_status_child = any(c.get("label") == "End of call status" for c in reason_node.get("children", []))
                                if has_status_child:
                                    new_path.append({"level": 2, "label": p_end_status})
                        
                        valid_paths.append({
                            "path_id": len(valid_paths) + 1,
                            "node_path": new_path
                        })
                        print(f"Backfilled path for product: {prod_name}")
                        break
                    elif is_product_category:
                        grand_children = child.get("children", [])
                        product_node = next((gc for gc in grand_children if gc.get("label") == prod_name or gc.get("label") == "product"), None)
                        if product_node:
                            new_path = [{"level": 0, "label": child.get("label")}, {"level": 1, "label": prod_name}]
                            if p_reason_type:
                                new_path.append({"level": 2, "label": p_reason_type})
                                # Check if reason_type has end-of-call child
                                reason_node = next((c for c in product_node.get("children", []) if c.get("label") == p_reason_type), None)
                                if reason_node and p_end_status:
                                    has_status_child = any(c.get("label") == "End of call status" for c in reason_node.get("children", []))
                                    if has_status_child:
                                        new_path.append({"level": 3, "label": p_end_status})
                            
                            valid_paths.append({
                                "path_id": len(valid_paths) + 1,
                                "node_path": new_path
                            })
                            print(f"Backfilled path for product: {prod_name} under {child.get('label')}")
                            break
                        else:
                            template = next((gc for gc in grand_children if gc.get("label") in product_list or gc.get("label") == "product"), None)
                            if template:
                                new_path = [{"level": 0, "label": child.get("label")}, {"level": 1, "label": prod_name}]
                                if p_reason_type:
                                    new_path.append({"level": 2, "label": p_reason_type})
                                    # Use template's children to check for reason type and end status
                                    reason_node = next((c for c in template.get("children", []) if c.get("label") == p_reason_type), None)
                                    if reason_node and p_end_status:
                                        has_status_child = any(c.get("label") == "End of call status" for c in reason_node.get("children", []))
                                        if has_status_child:
                                            new_path.append({"level": 3, "label": p_end_status})
                                
                                valid_paths.append({
                                    "path_id": len(valid_paths) + 1,
                                    "node_path": new_path
                                })
                                print(f"Backfilled templated path for product: {prod_name} under {child.get('label')}")
                                break

        return {"reason_paths": valid_paths}
    except Exception as e:
        print("LLM Processing Error:", e)
        return {"reason_paths": []}

def process_call(audio_path, brand_name, master_outlet_id, workflow_tree, product_list, complaint_reasons, enquiry_reasons, request_reasons, handled_list):
    print("\n=== STEP 1: TRANSCRIPTION ===")
    transcript = transcribe_audio(audio_path, brand_name)
    
    print("\n=== STEP 2: BASE ANALYTICS ANALYSIS ===")
    base_analytics = get_base_analytics(
        transcript, brand_name, product_list, 
        complaint_reasons, enquiry_reasons, 
        request_reasons, handled_list
    )
    
    print("\n=== STEP 3: TREE TRAVERSAL ANALYSIS ===")
    traversal_result = process_transcript_with_tree(
        transcript,
        base_analytics,
        workflow_tree,
        product_list
    )
    return {
        "transcript": transcript,
        "base_analytics": base_analytics,
        "reason_paths": traversal_result["reason_paths"]
    }

def main(call_recording_id):
    details = get_call_details(call_recording_id)
    if not details:
        print(f"Error: Could not fetch details for Call ID {call_recording_id}")
        return
    
    audio_path = details["call_recording_url"]
    brand_name = details["brand_name"]
    master_outlet_id = details["master_outlet_id"]
    outlet_id = details["outlet_id"]
    
    print(f"--- Processing Call ID: {call_recording_id} ({brand_name}) ---")
    
    call_language = detect_language(audio_path, details.get("state", ""))
    
    product_list = get_product_list(master_outlet_id)
    complaint_reasons = get_reasons_by_type(master_outlet_id, "Complaint")
    enquiry_reasons = get_reasons_by_type(master_outlet_id, "Enquiry")
    request_reasons = get_reasons_by_type(master_outlet_id, "Request")
    handled_list = [
        'Info Provided', 'Store Visit Confirmed', 'Issue Resolved',
        'Call Dropped', 'Follow-up Required', 'Complaint Registered', 'Service Activated',
        'Refund Processed', 'Payment Confirmed', 'Technical Assistance Provided',
        'General Inquiry', 'Account Information Updated', 'No Action Needed'
    ]
    
    workflow_tree = fetch_decision_nodes_from_db(master_outlet_id)
    if not workflow_tree:
        print(f"Error: No decision nodes found for brand ID {master_outlet_id}")
        return
        
    result = process_call(
        audio_path=audio_path,
        brand_name=brand_name,
        master_outlet_id=master_outlet_id,
        workflow_tree=workflow_tree,
        product_list=product_list,
        complaint_reasons=complaint_reasons,
        enquiry_reasons=enquiry_reasons,
        request_reasons=request_reasons,
        handled_list=handled_list
    )
    
    if result.get("base_analytics"):
        save_base_analytics(master_outlet_id, outlet_id, call_recording_id, result["base_analytics"], call_language=call_language)
        
    if result.get("reason_paths"):
        save_level_reasons(
            master_outlet_id, 
            call_recording_id, 
            result["reason_paths"], 
            workflow_tree
        )
    
    print("\n--- Final Analysis Result ---")
    summary_result = {
        "call_recording_id": call_recording_id,
        "brand": brand_name,
        "base_analytics": result.get("base_analytics") if result.get("base_analytics") else {},
        "reason_paths": result.get("reason_paths") if result.get("reason_paths") else [],
        "reason_paths_count": len(result.get("reason_paths")) if result.get("reason_paths") else 0
    }
    print(json.dumps(summary_result, indent=2))

if __name__ == "__main__":
    CALL_ID = 280
    main(CALL_ID)
