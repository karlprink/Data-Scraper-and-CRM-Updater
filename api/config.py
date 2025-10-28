import os
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    print("Attempting to load configuration from environment variables.")

    ariregister_url = os.getenv('ARIREGISTER_JSON_URL') or os.getenv('ARIREGISTER_CSV_URL')

    if os.getenv('NOTION_API_KEY') and os.getenv('NOTION_DATABASE_ID') and ariregister_url:
        print("Successfully loaded required configuration from environment variables.")
        return {
            "notion": {
                "token": os.getenv('NOTION_API_KEY'),
                "database_id": os.getenv('NOTION_DATABASE_ID')
            },
            "ariregister": {

                "json_url": ariregister_url
            }
        }

    print("ERROR: One or more required environment variables are missing.")
    return {}