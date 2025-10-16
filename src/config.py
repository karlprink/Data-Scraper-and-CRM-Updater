import yaml
import os


config_path = 'config.yaml'

def load_config(path=config_path):
    # Check if running in Vercel (environment variables available)
    if os.getenv('NOTION_TOKEN') and os.getenv('NOTION_DATABASE_ID'):
        return {
            "notion": {
                "token": os.getenv('NOTION_TOKEN'),
                "database_id": os.getenv('NOTION_DATABASE_ID')
            },
            "ariregister": {
                "csv_url": os.getenv('ARIREGISTER_CSV_URL', 'https://ariregister.rik.ee/api/ettevotja_rekvisiidid__lihtandmed.csv')
            }
        }
    
    # Fallback to config file
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
