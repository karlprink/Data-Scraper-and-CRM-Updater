import os
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    print("Attempting to load configuration from environment variables.")

    notion_token = os.getenv('NOTION_API_KEY')
    notion_db = os.getenv('NOTION_DATABASE_ID')

    ariregister_url = os.getenv('ARIREGISTER_JSON_URL') or os.getenv('ARIREGISTER_CSV_URL')

    if all([notion_token, notion_db, ariregister_url]):
        print("Successfully loaded required configuration from environment variables.")
        return {
            "notion": {
                "token": notion_token,
                "database_id": notion_db
            },
            "ariregister": {
                "json_url": ariregister_url
            }
        }

    print(
        f"ERROR: One or more required environment variables are missing. Missing status: NOTION_API_KEY={bool(notion_token)}, NOTION_DATABASE_ID={bool(notion_db)}, ARIREGISTER_JSON_URL={bool(ariregister_url)}")
    return {}