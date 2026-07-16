import json
from typing import List, Dict, Any

def load_dataset(file_path: str) -> Dict[str, Any]:
    """Loads the JSON dataset containing construction documents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        print(f"Error: Dataset file not found at {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {file_path}")
        return {}