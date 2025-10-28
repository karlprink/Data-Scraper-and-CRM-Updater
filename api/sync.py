import os
import requests
import json
import logging
from typing import Tuple, Dict, Any

# Set up basic logging to output to the console, which Vercel captures.
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# These will now be read directly from environment variables
from .json_loader import load_json, find_company_by_regcode, clean_value
from .notion_client import NotionClient


def sync_company(regcode: str):
    """
    Finds a company by its registration code in the CSV and syncs it to Notion.
    Configuration is read directly from environment variables.
    """
    # Get configuration from environment variables
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    ARIREGISTER_JSON_URL = os.getenv("ARIREGISTER_JSON_URL")

    # Validate that all required environment variables are set
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL]):
        logging.error(
            "Missing one or more required environment variables (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL).")
        return

    # Load csv
    df = load_json(ARIREGISTER_JSON_URL)
    company = find_company_by_regcode(df, regcode)

    if not company:
        logging.warning(f"Ettevõtet registrikoodiga {regcode} ei leitud failis.")
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)


def _prepare_notion_properties(company: dict, regcode: str) -> Tuple[Dict[str, Any], list, str]:
    """
    Cleans company data and aggregates it into the Notion Properties format,
    tracking fields that remain empty (UC-1 Extension 5b).
    Returns: (properties: dict, empty_fields: list, company_name: str)
    """
    company_name = clean_value(company.get('nimi'))
    return _build_properties_from_company(company, regcode, company_name)


def _build_properties_from_company(company: dict, regcode: str, company_name: str) -> Tuple[Dict[str, Any], list, str]:
    """Koostab Notioni properties objektid CSV andmete põhjal, navigeerides alamobjektides.
    Täidab AINULT Põhitegevuse (EMTAK koodi), jättes Tegevusvaldkonna (teksti) täitmata."""

    yldandmed = company.get('yldandmed', {})

    email_val = None
    tel_val = None
    veeb_val = None
    linkedin_val = clean_value(company.get("linkedin"))

    sidevahendid = yldandmed.get('sidevahendid', [])
    for item in sidevahendid:
        sisu = clean_value(item.get('sisu'))
        if not sisu:
            continue

        liik = item.get('liik')
        if liik == "EMAIL":
            email_val = sisu
        elif liik in ("TEL", "MOB"):
            if not tel_val:
                tel_val = sisu
        elif liik == "WWW":
            veeb_val = sisu

    aadressid = yldandmed.get('aadressid', [])
    aadress_täis_val = clean_value(
        aadressid[0].get('aadress_ads__ads_normaliseeritud_taisaadress')) if aadressid else None
    aadress_val = aadress_täis_val

    maakond_val_raw = None
    if aadress_täis_val:
        maakond_val_raw = aadress_täis_val.split(',')[0].strip()

    tegevusalad = yldandmed.get('teatatud_tegevusalad', [])
    pohitegevusala = next(
        (ta for ta in tegevusalad if ta.get('on_pohitegevusala') is True),
        None
    )
    pohitegevus_val = clean_value(pohitegevusala.get("emtak_tekstina")) if pohitegevusala else None

    empty_fields = []

    maakond_prop = {"multi_select": []}
    if maakond_val_raw:
        maakond_prop = {"multi_select": [{"name": maakond_val_raw}]}
    else:
        empty_fields.append("Maakond")

    email_prop = {"email": email_val} if email_val else {"email": None}
    tel_prop = {"phone_number": tel_val} if tel_val else {"phone_number": None}
    veeb_prop = {"url": veeb_val} if veeb_val else {"url": None}
    linkedin_prop = {"url": linkedin_val} if linkedin_val else {"url": None}

    if not email_val: empty_fields.append("E-post")
    if not tel_val: empty_fields.append("Tel. nr")
    if not veeb_val: empty_fields.append("Veebileht")
    if not linkedin_val: empty_fields.append("LinkedIn")
    if not aadress_val: empty_fields.append("Aadress")

    if not pohitegevus_val: empty_fields.append("Põhitegevus")

    properties = {
        "Nimi": {"title": [{"text": {"content": company_name}}]},
        "Registrikood": {"number": int(regcode)},
        "Aadress": {
            "rich_text": [{"text": {"content": aadress_val or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": yldandmed.get("kontaktisikud_list", [])},
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": pohitegevus_val or ""}}]},
        "Põhitegevus": {"rich_text": [{"text": {"content": pohitegevus_val or ""}}]}
    }

    return properties, empty_fields, company_name


def load_company_data(regcode: str, config: dict) -> dict:
    """
    Loads company data from CSV and prepares the Notion structures.
    Used before user confirmation in CLI.
    Returns a dictionary: {"status": str, "data": dict/None, "message": str}
    """

    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registrikood on puudu või sisaldab mittesoodustavaid sümboleid (peab olema number)."
        }

    try:
        print(["csv_url"])
        company_data = load_json(config["ariregister"]["json_url"], regcode)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Faili laadimise viga: {e}"
        }

    company = company_data

    if not company:
        return {
            "status": "error",
            "message": f"Ettevõtet registrikoodiga {regcode} ei leitud Äriregistri andmetest (CSV)."
        }

    # Prepares Notion properties
    properties, empty_fields, company_name = _prepare_notion_properties(company, regcode)

    return {
        "status": "ready",
        "data": {
            "regcode": regcode,
            "properties": properties,  # Data for Notion API
            "empty_fields": empty_fields,
            "company_name": company_name,
        },
        "message": f"Data found: {company_name} ({regcode})."
    }


def process_company_sync(data: dict, config: dict) -> dict:
    """
    Performs Notion API synchronization (after user confirmation) or updates
    an existing entry (old sync_company logic).
    """

    regcode = data["regcode"]
    properties = data["properties"]
    empty_fields = data["empty_fields"]
    company_name = data["company_name"]

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    # Compose full payload
    full_payload = {
        "parent": {"database_id": notion.database_id},
        "properties": properties
    }

    # Synchronization logic (combines checking existence and creation/update)
    try:
        existing = notion.query_by_regcode(regcode)
        action = ""

        if existing:
            # Uuendamine
            notion.update_page(existing["id"], properties)
            action = "Uuendatud"
        else:
            # Lisamine
            notion.create_page(full_payload)
            action = "Lisatud"

        status = "success"
        message = f"✅ Edukalt {action}: {company_name} ({regcode}). Kirje loodi Notionis."

        if empty_fields:
            status = "warning"
            message += f"\n ⚠️ Hoiatus: Järgmised väljad jäid tühjaks: {', '.join(empty_fields)}."

        return {"status": status, "message": message, "company_name": company_name}

    except requests.HTTPError as e:
        error_details = ""
        try:
            error_details = e.response.json().get("message", e.response.text)
        except:
            error_details = e.response.text

        return {
            "status": "error",
            "message": f"❌ Notion API viga ({e.response.status_code}): {error_details}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Üldine sünkroonimisviga: {type(e).__name__}: {e}"
        }


def autofill_page_by_page_id(page_id: str):
    """Loeb Registrikood property antud Notioni lehelt ning täidab ülejäänud väljad."""
    logging.info(f"--- Starting autofill for page_id: {page_id} ---")

    # Get configuration from environment variables
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    ARIREGISTER_JSON_URL = os.getenv("ARIREGISTER_JSON_URL")

    # Validate that all required environment variables are set
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL]):
        error_msg = "Missing one or more required environment variables (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL)."
        logging.error(error_msg)
        return {"error": error_msg, "step": "env_check"}

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

    # Loe lehe properties
    try:
        page = notion.get_page(page_id)
        props = page.get("properties", {})
        logging.info("Successfully fetched page properties from Notion.")
    except Exception as e:
        error_msg = f"Failed to fetch page from Notion: {e}"
        logging.error(error_msg)
        return {"error": error_msg, "step": "fetch_page"}

    reg_prop = props.get("Registrikood")
    if not reg_prop:
        error_msg = f"DEBUG: Lehe 'Registrikood' property puudub. Available properties: {list(props.keys())}"
        logging.error(error_msg)
        return {"error": error_msg, "step": "missing_registrikood", "available_props": list(props.keys())}

    # Extract regcode (handling number and rich_text formats)
    regcode = None
    if reg_prop.get("type") == "number":
        val = reg_prop.get("number")
        if val is not None:
            regcode = str(int(val))
    elif reg_prop.get("type") == "title":
        # Title field often used for primary identifier if number field isn't
        texts = reg_prop.get("title") or []
        if texts:
            content = texts[0].get("plain_text") or texts[0].get("text", {}).get("content")
            if content:
                regcode = ''.join(ch for ch in content if ch.isdigit())
    elif reg_prop.get("type") == "rich_text":
        texts = reg_prop.get("rich_text") or []
        if texts:
            content = texts[0].get("plain_text") or texts[0].get("text", {}).get("content")
            if content:
                regcode = ''.join(ch for ch in content if ch.isdigit())

    if not regcode:
        error_msg = "'Registrikood' on tühi või vales formaadis sellel Notioni lehel."
        logging.warning(error_msg)
        return {"error": error_msg, "step": "invalid_registrikood"}

    logging.info(f"Found Registrikood: {regcode}")

    # Lae CSV ja leia ettevõte
    try:
        df = load_json(ARIREGISTER_JSON_URL)
        logging.info("Successfully loaded CSV file.")
    except Exception as e:
        error_msg = f"Failed to load CSV: {e}"
        logging.error(error_msg)
        return {"error": error_msg, "step": "load_csv"}

    company = find_company_by_regcode(df, regcode)
    if not company:
        error_msg = f"Ettevõtet registrikoodiga {regcode} ei leitud CSV-s."
        logging.warning(error_msg)
        return {"error": error_msg, "step": "company_not_found", "regcode": regcode}

    logging.info(f"Found matching company in CSV: {clean_value(company.get('nimi'))}")

    company_name = clean_value(company.get('nimi'))
    properties, empty_fields, _ = _build_properties_from_company(company, regcode, company_name)
    logging.info("Built properties payload to send to Notion:")
    logging.info(json.dumps(properties, indent=2, ensure_ascii=False))

    # Uuenda sama lehte
    try:
        notion.update_page(page_id, properties)
        success_msg = f"Successfully called Notion update_page API for: {clean_value(company.get('nimi'))} ({regcode})"
        logging.info(success_msg)
        logging.info("--- Autofill process completed successfully. ---")
        return {"success": True, "message": success_msg, "company_name": company_name, "regcode": regcode}
    except Exception as e:
        error_msg = f"Failed during Notion page update: {e}"
        logging.error(error_msg)
        return {"error": error_msg, "step": "notion_update", "details": str(e)}
