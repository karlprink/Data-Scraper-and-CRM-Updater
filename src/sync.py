import requests
from typing import Tuple, List, Dict, Any

# Eeldab, et load_csv, find_company_by_regcode, clean_value, NotionClient on imporditud
from .csv_loader import load_csv, find_company_by_regcode, clean_value
from .notion_client import NotionClient


# MÄRKUS: NotionClient vajab 'get_page(page_id)' meetodit, et autofill_page_by_page_id töötaks.

# --- Abifunktsioonid Andmete Ettevalmistamiseks ---

def _prepare_notion_properties(company: dict, regcode: str) -> Tuple[Dict[str, Any], List[str], str]:
    """
    Cleans company data and aggregates it into the Notion Properties format,
    tracking fields that remain empty (UC-1 Extension 5b).
    Returns: (properties: dict, empty_fields: list, company_name: str)
    """

    company_name = clean_value(company.get('nimi')) or f"Ettevõte ({regcode})"

    maakond_val_raw = clean_value(company.get("asukoha_ehak_tekstina"))
    email_val = clean_value(company.get("email"))
    tel_val = clean_value(company.get("telefon"))
    veeb_val = clean_value(company.get("teabesysteemi_link"))
    linkedin_val = clean_value(company.get("linkedin"))

    empty_fields = []

    # Extracting Maakond (comma-free requirement)
    maakond_prop = {"multi_select": []}
    if maakond_val_raw:
        parts = maakond_val_raw.split(',')
        maakond_tag = parts[-1].strip()
        if maakond_tag:
            maakond_prop = {"multi_select": [{"name": maakond_tag}]}
        else:
            empty_fields.append("Maakond")
    else:
        empty_fields.append("Maakond")

    # Setting empty values to None (email, tel, url)
    email_prop = {"email": email_val} if email_val else {"email": None}
    tel_prop = {"phone_number": tel_val} if tel_val else {"phone_number": None}
    veeb_prop = {"url": veeb_val} if veeb_val else {"url": None}
    linkedin_prop = {"url": linkedin_val} if linkedin_val else {"url": None}

    # Check for empty fields
    if not email_val: empty_fields.append("E-post")
    if not tel_val: empty_fields.append("Tel. nr")
    if not veeb_val: empty_fields.append("Veebileht")
    if not linkedin_val: empty_fields.append("LinkedIn")
    if not clean_value(company.get("asukoht_ettevotja_aadressis")): empty_fields.append("Aadress")
    if not clean_value(company.get("tegevusvaldkond")): empty_fields.append("Tegevusvaldkond")
    if not clean_value(company.get("pohitegevus")): empty_fields.append("Põhitegevus")

    properties = {
        "Nimi": {"title": [{"text": {"content": company_name}}]},
        "Registrikood": {"number": int(regcode)},
        "Aadress": {
            "rich_text": [{"text": {"content": clean_value(company.get("asukoht_ettevotja_aadressis")) or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": company.get("kontaktisikud_list") or []},
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": clean_value(company.get("tegevusvaldkond")) or ""}}]},
        "Põhitegevus": {"rich_text": [{"text": {"content": clean_value(company.get("pohitegevus")) or ""}}]}
    }

    return properties, empty_fields, company_name


# --- Peamised Sünkroonimisfunktsioonid ---

def load_company_data(regcode: str, config: dict) -> dict:
    """
    Loads company data from CSV and prepares the Notion structures.
    Used before user confirmation in CLI.
    Returns a dictionary: {"status": str, "data": dict/None, "message": str}
    """

    # Invalid/missing registry code check
    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registrikood on puudu või sisaldab mittesoodustavaid sümboleid (peab olema number)."
        }

    try:
        df = load_csv(config["ariregister"]["csv_url"])
    except Exception as e:
        return {
            "status": "error",
            "message": f"CSV laadimise viga: {e}"
        }

    company = find_company_by_regcode(df, regcode)

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


def autofill_page_by_page_id(page_id: str, config: dict):
    """
    Reads the Registrikood property from the given Notion page and fills the remaining fields.
    This function uses the _prepare_notion_properties helper for consistency.
    """
    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"],
    )

    try:
        # Loe lehe properties
        page = notion.get_page(page_id)  # Requires NotionClient.get_page(page_id) method
        props = page.get("properties", {})
    except Exception as e:
        print(f"❌ Viga lehe {page_id} lugemisel Notionis: {e}")
        return

    reg_prop = props.get("Registrikood")
    if not reg_prop:
        print("❌ Lehe 'Registrikood' property puudub.")
        return

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
        print("❌ 'Registrikood' on tühi või vales formaadis sellel Notioni lehel.")
        return

    # Lae CSV ja leia ettevõte
    df = load_csv(config["ariregister"]["csv_url"])
    company = find_company_by_regcode(df, regcode)
    if not company:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud CSV-s.")
        return

    # Kasuta sama helperit Notioni properties loomiseks
    properties, empty_fields, company_name = _prepare_notion_properties(company, regcode)

    # Uuenda sama lehte
    notion.update_page(page_id, properties)

    message = f"✅ Täidetud leht: {company_name} ({regcode})"
    if empty_fields:
        message += f". Hoiatus: {', '.join(empty_fields)} jäid tühjaks."

    print(message)
