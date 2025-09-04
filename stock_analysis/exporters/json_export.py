import json
import os
from datetime import datetime

def export_to_json(data, filename=None):
    """
    Export stock analysis data to a JSON file keeping the original structure
    :param data: List of dictionaries containing stock data
    :param filename: Optional custom filename
    :return: Path to the generated JSON file
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                              "data", 
                              f"nse_analysis_{timestamp}.json")
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            "stocks": data,
            "metadata": {
                "total_stocks": len(data),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        }, f, indent=4, ensure_ascii=False)
    
    return filename
