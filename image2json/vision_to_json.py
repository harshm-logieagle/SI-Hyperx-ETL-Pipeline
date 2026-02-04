import requests
import json
import base64
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_vision_description(image_path, api_key):
    url = "https://platform.qubrid.com/api/v1/qubridai/multimodal/chat"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe the image using a tree-structured format. Organize the description into hierarchical steps. Do not treat the top-left name outside the box as Step 1 or as a node. Keep all text exactly as it appears in the image, do not refactor, rename, or modify any string or label. 'All Calls' should retreated with the name 'root' in label. Check the image layer wise to get the best accuracy. Move complete focus on the workflow chart and ignore all the text in the box or outside the box which is not related to the workflow chart."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encode_image(image_path)}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": True,
        "presence_penalty": 0
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)
    full_content = ""
    
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            payload = line.replace("data:", "").strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    content = chunk["choices"][0].get("delta", {}).get("content", "")
                    full_content += content
            except json.JSONDecodeError:
                continue
    return full_content

def transform_to_json(description, api_key):
    print("------Transforming to JSON------")
    url = "https://platform.qubrid.com/api/v1/qubridai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    with open(r"d:\Harsh\Projects-Working\SingleInterface - HyperX\whimsical_json\hdfc_life.json", "r") as f:
        reference_json = f.read()

    print("Checkpoint 1")

    system_prompt = (
        "Convert the tree description into a nested JSON structure. "
        "Each node: 'id' (unique int), 'outlet_id' (4844), 'parent_id' (parent id or null for root), "
        "'node_type' ('extraction' or 'classification'), 'label' (exact text), 'description' (empty string), 'is_active' (1). "
        "Strict hierarchy. If 'children' is empty, omit the 'children' key. "
        "'All Calls' should be treated as label = 'root' node & description should be 'Root'."
        f"Reference JSON Format:\n{reference_json}\n"
        "Return ONLY the valid JSON object."
    )
    
    data = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Description from Vision LLM:\n{description}"}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": True,
        "top_p": 1
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)
    full_content = ""

    print("Checkpoint 2")
    
    for line in response.iter_lines(decode_unicode=True):
        # print("---->", line)
        if not line:
            continue
        if line.startswith("data:"):
            payload = line.replace("data:", "").strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    content = chunk["choices"][0].get("delta", {}).get("content", "")
                    full_content += content
            except json.JSONDecodeError:
                continue

    content = full_content.strip()
    if content.startswith("```json"):
        content = content.split("```json")[1].split("```")[0].strip()
    elif content.startswith("```"):
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        image_path = r"D:\Harsh\Projects-Working\SingleInterface - HyperX\image2json\hdfc_life.png"
    else:
        image_path = sys.argv[1]
    
    api_key = os.getenv("QUBRID_API_KEY")
    
    try:
        desc = get_vision_description(image_path, api_key)
        final_json = transform_to_json(desc, api_key)
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)
        print(json.dumps(final_json, indent=4))
    except Exception as e:
        print(f"Error: {e}")
