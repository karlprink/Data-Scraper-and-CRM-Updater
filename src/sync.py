import os
import requests
import json
import logging

# Set up basic logging to output to the console, which Vercel captures.
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# These will now be read directly from environment variables
from .csv_loader import load_csv, find_company_by_regcode, clean_value
from .notion_client import NotionClient


def sync_company(regcode: str):
    """
    Finds a company by its registration code in the CSV and syncs it to Notion.
    Configuration is read directly from environment variables.
    """
    # Get configuration from environment variables
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    ARIREGISTER_CSV_URL = os.getenv("ARIREGISTER_CSV_URL")

    # Validate that all required environment variables are set
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_CSV_URL]):
        logging.error("Missing one or more required environment variables (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_CSV_URL).")
        return

    # Load csv
    df = load_csv(ARIREGISTER_CSV_URL)
    company = find_company_by_regcode(df, regcode)

    if not company:
        logging.warning(f"Ettevõtet registrikoodiga {regcode} ei leitud CSV-s.")
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

    properties = _build_properties_from_company(company)

    # Compose full payload for Notion db
    data = {
        "parent": {"database_id": notion.database_id},
        "properties": properties
    }

    # Kontrollprint payload
    logging.info("Notion payload:")
    logging.info(json.dumps(data, indent=2, ensure_ascii=False))

    # Check if exists already in notion database
    try:
        existing = notion.query_by_regcode(regcode)

        if existing:
            page_id = existing["id"]
            notion.update_page(page_id, properties)
            logging.info(f"Uuendatud: {clean_value(company.get('nimi'))} ({regcode})")
        else:
            notion.create_page(data)
            logging.info(f"Lisatud: {clean_value(company.get('nimi'))} ({regcode})")

    except requests.HTTPError as e:
        # Catch error details
        error_details = ""
        try:
            error_details = e.response.json()
        except:
            error_details = e.response.text

        logging.error(f"Viga Notion API-s ({e.response.status_code} {e.response.reason}):")
        logging.error(json.dumps(error_details, indent=2, ensure_ascii=False))

    except Exception as e:
        logging.error(f"Üldine viga: {e}")


def _build_properties_from_company(company: dict) -> dict:
    """Koostab Notioni properties objektid CSV andmete põhjal."""
    maakond_val_raw = clean_value(company.get("asukoha_ehak_tekstina"))
    email_val = clean_value(company.get("email"))
    tel_val = clean_value(company.get("telefon"))
    veeb_val = clean_value(company.get("teabesysteemi_link"))
    linkedin_val = clean_value(company.get("linkedin"))

    maakond_prop = {"multi_select": []}
    if maakond_val_raw:
        parts = maakond_val_raw.split(',')
        maakond_tag = parts[-1].strip()
        if maakond_tag:
            maakond_prop = {"multi_select": [{"name": maakond_tag}]}

    email_prop = {"email": email_val} if email_val else {"email": None}
    tel_prop = {"phone_number": tel_val} if tel_val else {"phone_number": None}
    veeb_prop = {"url": veeb_val} if veeb_val else {"url": None}
    linkedin_prop = {"url": linkedin_val} if linkedin_val else {"url": None}

    properties = {
        "Nimi": {"title": [{"text": {"content": clean_value(company.get("nimi")) or ""}}]},
        "Registrikood": {"number": int(clean_value(company.get("ariregistri_kood")) or 0)},
        "Aadress": {"rich_text": [{"text": {"content": clean_value(company.get("asukoht_ettevotja_aadressis")) or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": company.get("kontaktisikud_list") or []},
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": clean_value(company.get("tegevusvaldkond")) or ""}}]},
        "Põhitegevus": {"rich_text": [{"text": {"content": clean_value(company.get("pohitegevus")) or ""}}]},
    }
    return properties


def autofill_page_by_page_id(page_id: str):
    """Loeb Registrikood property antud Notioni lehelt ning täidab ülejäänud väljad."""
    logging.info(f"--- Starting autofill for page_id: {page_id} ---")
    
    # Get configuration from environment variables
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    ARIREGISTER_CSV_URL = os.getenv("ARIREGISTER_CSV_URL")
    
    # Validate that all required environment variables are set
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_CSV_URL]):
        logging.error("Missing one or more required environment variables (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_CSV_URL).")
        return
        
    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

    # Loe lehe properties
    try:
        page = notion.get_page(page_id)
        props = page.get("properties", {})
        logging.info("Successfully fetched page properties from Notion.")
    except Exception as e:
        logging.error(f"Failed to fetch page from Notion: {e}")
        return

    reg_prop = props.get("Registrikood")
    if not reg_prop:
        logging.error("DEBUG: Lehe 'Registrikood' property puudub.")
        logging.info(f"Available properties are: {list(props.keys())}")
        return

    reg_type = reg_prop.get("type")
    regcode = None
    if reg_type == "number":
        val = reg_prop.get("number")
        if val is not None:
            regcode = str(int(val))
    elif reg_type == "rich_text":
        texts = reg_prop.get("rich_text") or []
        if texts:
            content = texts[0].get("plain_text") or texts[0].get("text", {}).get("content")
            if content:
                regcode = ''.join(ch for ch in content if ch.isdigit())

    if not regcode:
        logging.warning("'Registrikood' on tühi või vales formaadis sellel Notioni lehel.")
        return
    
    logging.info(f"Found Registrikood: {regcode}")

    # Lae CSV ja leia ettevõte
    try:
        df = load_csv(ARIREGISTER_CSV_URL)
        logging.info("Successfully loaded CSV file.")
    except Exception as e:
        logging.error(f"Failed to load CSV: {e}")
        return

    company = find_company_by_regcode(df, regcode)
    if not company:
        logging.warning(f"Ettevõtet registrikoodiga {regcode} ei leitud CSV-s.")
        return
    
    logging.info(f"Found matching company in CSV: {clean_value(company.get('nimi'))}")

    properties = _build_properties_from_company(company)
    logging.info("Built properties payload to send to Notion:")
    logging.info(json.dumps(properties, indent=2, ensure_ascii=False))

    # Uuenda sama lehte
    try:
        notion.update_page(page_id, properties)
        logging.info(f"Successfully called Notion update_page API for: {clean_value(company.get('nimi'))} ({regcode})")
        logging.info("--- Autofill process completed successfully. ---")
    except Exception as e:
        logging.error(f"Failed during Notion page update: {e}")

