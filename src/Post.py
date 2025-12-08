import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")

url = "https://api.notion.com/v1/pages"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

data = {
    "parent": {"database_id": DATABASE_ID},
    "properties": {
        "Nimi": {"title": [{"text": {"content": "Testfirma5 OÜ"}}]},
        "Registrikood": {"number": 123456789},
        "Aadress": {"rich_text": [{"text": {"content": "Tallinn, Eesti"}}]},
        "Maakond": {"multi_select": [{"name": "Harjumaa"}]},
        "E-post": {"email": "firma@example.com"},
        "Tel. nr": {"phone_number": "+3725555555"},
        "Veebileht": {"url": "https://example.com"},
        "LinkedIn": {"url": "https://linkedin.com/company/example"},
        "Kontaktisikud": {"people": []},
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": "IT"}}]},
        "Põhitegevus": {"rich_text": [{"text": {"content": "Tarkvaraarendus"}}]},
    },
}

response = requests.post(url, headers=headers, json=data)
print("Status code:", response.status_code)
print("Response:", response.json())
