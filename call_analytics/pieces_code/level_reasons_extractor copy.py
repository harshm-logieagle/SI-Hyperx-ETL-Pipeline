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


USER_PROMPT_TEMPLATE = """
Transcript:
{transcript}

Workflow Tree:
{workflow_tree}

Instructions:

1. Ignore root node completely.
2. Start traversal from children of root.
3. Level 0 must correspond to children of root.
4. For each journey:
   - Select one valid child node per level
   - Maintain parent-child validity
   - Stop traversal when deeper evidence ends
5. Create separate path for each journey.

Output ONLY valid JSON:

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

def get_brand_id_by_name(brand_name):
    """
    Fetches the brand id (master_outlet_id) from the brands table based on brand_name.
    """
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = "SELECT id FROM brands WHERE brand_name = %s"
        cursor.execute(query, (brand_name,))
        result = cursor.fetchone()

        if result:
            return result[0]
        return None

    except Error as e:
        print(f"Error fetching brand ID: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Transforms table records in JSON format
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

        match = next(
            (c for c in current_children if c["label"] == label),
            None
        )

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
        print("=======>>>>", raw_output)

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



TARGET_BRAND = "TVS"
master_outlet_id = get_brand_id_by_name(TARGET_BRAND)

if master_outlet_id:
    workflow_tree = fetch_decision_nodes_from_db(master_outlet_id)
    if workflow_tree:
        result = process_call(
            audio_path=r"https://sr.knowlarity.com/vr/fetchsound/?callid=836f79fb-e298-4534-9ef5-5e2441dca740",
            brand_name=TARGET_BRAND,
            workflow_tree=workflow_tree
        )

        print(json.dumps(result, indent=2))
    else:
        print(f"Error: Could not fetch workflow tree for brand ID: {master_outlet_id}")
else:
    print(f"Error: Brand '{TARGET_BRAND}' not found in 'brands' table.")
