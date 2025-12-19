import os
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    """
    Loads required configuration settings from environment variables.
    Returns:
        A dictionary containing 'notion','ariregister' and 'google' configuration
    """
    google_ai_model = "gemini-2.0-flash-exp"
    notion_token = os.getenv("NOTION_API_KEY")
    notion_db = os.getenv("NOTION_DATABASE_ID")
    notion_api_version = os.getenv("NOTION_API_VERSION")
    # Accepts either JSON_URL or the older CSV_URL environment variable
    ariregister_url = os.getenv("ARIREGISTER_JSON_URL") or os.getenv(
        "ARIREGISTER_CSV_URL"
    )
    google_api_key = os.getenv("GOOGLE_API_KEY")
    google_cse_cx = os.getenv("GOOGLE_CSE_CX")

    return {
        "notion": {
            "token": notion_token,
            "database_id": notion_db,
            "api_version": notion_api_version,
        },
        "ariregister": {"json_url": ariregister_url},
        "google": {
            "api_key": "dummy_key",
            "cse_cx": "dummy_id",
            "ai_model": google_ai_model,
        },
    }
