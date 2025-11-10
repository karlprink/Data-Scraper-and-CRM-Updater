import os
import yaml
from typing import Dict, Any
from pathlib import Path


def load_config() -> Dict[str, Any]:
    print("Attempting to load configuration from environment variables.")

    notion_token = os.getenv('NOTION_API_KEY')
    notion_db = os.getenv('NOTION_DATABASE_ID')
    ariregister_url = os.getenv('ARIREGISTER_JSON_URL') or os.getenv('ARIREGISTER_CSV_URL')

    # Kui kõik kolm on olemas, kasuta keskkonnamuutujaid (nt Vercel)
    if all([notion_token, notion_db, ariregister_url]):
        print("✅ Successfully loaded configuration from environment variables.")
        return {
            "notion": {
                "token": notion_token,
                "database_id": notion_db
            },
            "ariregister": {
                "json_url": ariregister_url
            }
        }

    # Kui env pole olemas, proovi YAML-failist
    print("⚠️ Environment variables not found. Trying to load from config.yaml...")

    for path in [Path("config.yaml"), Path(__file__).parent.parent / "config.yaml"]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                print(f"✅ Successfully loaded configuration from {path}")
                return cfg
            except Exception as e:
                print(f"⚠️ Failed to load config from {path}: {e}")

    print("❌ ERROR: No configuration found. Please check your environment or config.yaml file.")
    return {}
