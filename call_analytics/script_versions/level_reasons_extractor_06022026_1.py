import json
from groq import Groq
import httpx
import os
import urllib.parse
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    http_client=httpx.Client()
)

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

Rules:
- Products may be misspelled due to transcription errors — account for phonetic or spelling variations.
- Only extract products that clearly map to names in the provided list.
- Do NOT extract generic terms (e.g., “bike”, “phone”, “model”).
- If no product from the list is mentioned, return an empty string for the product field.

For EACH extracted product:
- product → Exact product name from the list
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
"reason_type": "Complaint",
"reason_verbatim": "",
"reason": "",
"end_of_call_status": "",
"products_mentioned": [
    {
        "product": "",
        "product_sentiment": "",
        "product_verbatim": "",
        "tags": ["", ""]
    },
    {
        "product": "",
        "product_sentiment": "",
        "product_verbatim": "",
        "tags": ["", ""]
    }
],
"overall_sentiment": "",
"emotions": [
    {
        "emotion": "",
        "emotion_verbatim": ""
    }
],
"customer_type": "",
"customer_gender": "",
"summary": "",
"transcript": [
    "agent: how can i help you today?",
    "customer: i want to give my suit for alteration.",
    "agent:..."
]
</response_format>
"""

USER_PROMPT_TEMPLATE = """
You are given a conversation transcript, pre-computed base analytics, and a hierarchical workflow tree.
Your task is to extract all valid traversal journeys through the workflow tree based on evidence present in the transcript.

TRANSCRIPT
{transcript}

BASE ANALYTICS
{base_analytics}

WORKFLOW TREE
{workflow_tree}

TRAVERSAL RULES
1. Ignore the root node completely.
   - The root node is structural only and must not appear in output.

2. Begin traversal from the children of the root node.
   - Level 0 must always correspond to a child of the root.

3. For each detected journey:
   - Select exactly one valid child node at each level.
   - Each selected node must be a direct child of the previously selected node.
   - Maintain strict parent-child hierarchy.
   - Continue traversal only while transcript evidence supports deeper levels.
   - Stop traversal when no further supported child exists.

4. If multiple independent journeys are present in the transcript:
   - Create a separate traversal path for each journey.
   - Do not merge multiple journeys into a single path.

NODE TYPE HANDLING
Each node in the workflow tree has a `node_type`.
- If `node_type = "Classification"`:
  - The node label must be selected based on interpretation of the transcript.
  - You may use base analytics as supporting context if needed.

- If `node_type = "Extraction"`:
  - The node label represents an entity already extracted from the transcript.
  - Do NOT re-classify it.
  - Include it in the traversal path only if it is explicitly mentioned or supported by the transcript or base analytics.

OUTPUT REQUIREMENTS
- Return ONLY valid JSON.
- Do NOT include explanations or commentary.
- Do NOT include unused levels.
- Levels must start from 0 and be sequential.
- Each path must be internally consistent and hierarchically valid.

OUTPUT FORMAT
{
  "reason_paths": [
    {
      "path_id": 1,
      "node_path": [
        { "level": 0, "label": "" }
      ]
    }
  ]
}
"""

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
            SELECT ccr.call_recording_url, b.brand_name, b.id as master_outlet_id 
            FROM customer_call_recordings AS ccr
            JOIN brands b ON b.id = ccr.master_outlet_id 
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
            (master_outlet_id, call_recording_id, decision_node_id, path_id, level, value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        for path_entry in reason_paths:
            path_id = path_entry.get("path_id", 1)
            node_path = path_entry.get("node_path", [])
            current_layer = workflow_tree.get("children", [])
            
            for step in node_path:
                label = step["label"]
                level = step["level"]
                match = next((c for c in current_layer if c["label"] == label), None)
                if match:
                    data = (
                        master_outlet_id,
                        call_recording_id,
                        match["id"],
                        path_id,
                        str(level),
                        label
                    )
                    cursor.execute(insert_query, data)
                    current_layer = match.get("children", [])
                else:
                    print(f"Warning: Label '{label}' not found at level {level}")
                    break
        
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

def validate_node_path(tree, node_path):
    if not node_path:
        return False
    current_children = tree.get("children", [])
    for step in node_path:
        label = step.get("label")
        match = next((c for c in current_children if c["label"] == label), None)
        if not match:
            return False
        current_children = match.get("children", [])
    return True

def process_transcript_with_tree(transcript, workflow_tree):
    pruned_tree = prune_tree(workflow_tree)
    root_label = pruned_tree["label"]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        transcript=transcript,
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
        cleaned_paths = remove_root_from_paths(
            raw_output.get("reason_paths", []),
            root_label
        )
        valid_paths = []
        for path in cleaned_paths:
            if validate_node_path(pruned_tree, path["node_path"]):
                valid_paths.append(path)
        return {"reason_paths": valid_paths}
    except Exception as e:
        print("LLM Processing Error:", e)
        return {"reason_paths": []}

def process_call(audio_path, brand_name, workflow_tree):
    print("\n=== STEP 1: TRANSCRIPTION ===")
    transcript = transcribe_audio(audio_path, brand_name)
    print("\n=== STEP 2: TREE TRAVERSAL ANALYSIS ===")
    traversal_result = process_transcript_with_tree(
        transcript,
        workflow_tree
    )
    return {
        "transcript": transcript,
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
    print(f"--- Processing Call ID: {call_recording_id} ({brand_name}) ---")
    workflow_tree = fetch_decision_nodes_from_db(master_outlet_id)
    if not workflow_tree:
        print(f"Error: No decision nodes found for brand ID {master_outlet_id}")
        return
    result = process_call(
        audio_path=audio_path,
        brand_name=brand_name,
        workflow_tree=workflow_tree
    )
    if result.get("reason_paths"):
        save_level_reasons(
            master_outlet_id, 
            call_recording_id, 
            result["reason_paths"], 
            workflow_tree
        )
    print("\n--- Final Analysis Result ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    CALL_ID = 148
    main(CALL_ID)
