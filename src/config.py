import os

def load_config():
    """
    Loads configuration from environment variables if running in Vercel,
    otherwise falls back to a local YAML file.
    """
    # Check for Vercel environment variables first
    # Note: Vercel uses NOTION_API_KEY, not NOTION_TOKEN
    if os.getenv('NOTION_API_KEY') and os.getenv('NOTION_DATABASE_ID'):
        print("Loading configuration from environment variables.")
        return {
            "notion": {
                "token": os.getenv('NOTION_API_KEY'),
                "database_id": os.getenv('NOTION_DATABASE_ID')
            },
            "ariregister": {
                "csv_url": os.getenv('ARIREGISTER_CSV_URL', 'https://avaandmed.ariregister.rik.ee/sites/default/files/avaandmed/ettevotja_rekvisiidid__lihtandmed.csv.zip')
            }
        }
    

