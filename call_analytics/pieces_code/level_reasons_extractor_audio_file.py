import json
from groq import Groq
import httpx
import os
from dotenv import load_dotenv

load_dotenv()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    http_client=httpx.Client()
)


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


def transcribe_audio(audio_path, brand_name):
    print(f"Transcribing audio: {audio_path}")

    try:
        with open(audio_path, "rb") as file:
            transcription = client.audio.translations.create(
                file=(audio_path, file.read()),
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

        # Remove root if present
        if node_path and node_path[0]["label"] == root_label:
            node_path = node_path[1:]

        # Reassign levels safely
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

        # Remove root if model added it
        cleaned_paths = remove_root_from_paths(
            raw_output.get("reason_paths", []),
            root_label
        )

        # Validate paths
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


with open(r"D:\Harsh\Projects-Working\SingleInterface - HyperX\whimsical_json\tvs.json", "r") as json_file:
    workflow_tree = json.load(json_file)

result = process_call(
    audio_path=r"D:\Harsh\Projects-Working\SingleInterface - HyperX\call_analytics\recordings\tvs_sample_4.mp3",
    brand_name="TVS",
    workflow_tree=workflow_tree
)

print(json.dumps(result, indent=2))
