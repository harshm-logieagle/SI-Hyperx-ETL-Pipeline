import csv
import json

def transform_decision_nodes_csv_to_json(csv_file_path):
    """
    Transforms decision nodes CSV data into a hierarchical JSON format.
    """
    nodes = {}
    roots = []

    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Basic node structure
                node = {
                    "id": int(row["id"]),
                    "outlet_id": int(row.get("master_outlet_id") or row.get("outlet_id", 0)),
                    "parent_id": int(row["parent_id"]) if row["parent_id"] and row["parent_id"].strip() else None,
                    "node_type": row.get("node_type", ""),
                    "label": row.get("label", ""),
                    "description": row.get("description", ""),
                    "is_active": int(row.get("is_active", 0)),
                    "children": []
                }
                nodes[node["id"]] = node

        # Build hierarchy
        for node_id, node in nodes.items():
            parent_id = node["parent_id"]
            if parent_id is None:
                roots.append(node)
            elif parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                # Orphan node treated as root
                roots.append(node)

        # Cleanup: Remove empty 'children' lists to match target format
        def remove_empty_children(node_list):
            for n in node_list:
                if not n["children"]:
                    del n["children"]
                else:
                    remove_empty_children(n["children"])

        remove_empty_children(roots)

        return roots

    except Exception as e:
        print(f"Error transforming CSV: {e}")
        return []

if __name__ == "__main__":
    csv_path = r"d:\Harsh\Projects-Working\SingleInterface - HyperX\call_analytics\decision_nodes.csv"
    hierarchical_data = transform_decision_nodes_csv_to_json(csv_path)
    
    # Print the first root as an example
    if hierarchical_data:
        print(json.dumps(hierarchical_data[0], indent=4))
    else:
        print("No data found or error occurred.")
