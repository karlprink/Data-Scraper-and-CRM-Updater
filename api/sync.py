import os
import requests
import json
import logging
from typing import Tuple, Dict, Any
from .config import load_config  # Kasutame otse load_config funktsiooni
from .json_loader import find_company_by_regcode, clean_value  # Eemaldatud load_json
from .notion_client import NotionClient
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')




def sync_company(regcode: str):
    # ... (see funktsioon ei tundu olevat /api/autofill poolt kasutusel)
    # ... (Selle parandamine pole hetkel kriitiline, kui autofill_page_by_page_id töötab)

    # 💡 PARANDUS: Kasuta õiget funktsiooni
    # See funktsioon (sync_company) vajaks samuti parandamist, et see
    # küsiks andmebaasist, mitte ei eeldaks faili URL-i.

    config = load_config()
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        logging.error("Missing Notion configuration.")
        return

    # PARANDATUD: find_company_by_regcode ei vaja enam URL-i
    company = find_company_by_regcode(regcode)

    if not company:
        logging.warning(f"Ettevõtet registrikoodiga {regcode} ei leitud ANDMEBAASIST.")
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)
    # ... (ülejäänud sünkroniseerimise loogika)


def _prepare_notion_properties(company: dict, regcode: str) -> Tuple[Dict[str, Any], list, str]:
    """
    Cleans company data and aggregates it into the Notion Properties format.
    (See funktsioon on korras)
    """
    company_name = clean_value(company.get('nimi'))
    return _build_properties_from_company(company, regcode, company_name)


def _build_properties_from_company(company: dict, regcode: str, company_name: str) -> Tuple[Dict[str, Any], list, str]:
    """Koostab Notioni properties objektid DB andmete põhjal (kasutab nüüd optimeeritud struktuuri)."""

    # Väljade lugemine uuest, optimeeritud struktuurist
    email_val = clean_value(company.get("kontakt", {}).get("email"))
    tel_val = clean_value(company.get("kontakt", {}).get("telefon"))
    veeb_val = clean_value(company.get("kontakt", {}).get("veebileht"))
    linkedin_val = clean_value(company.get("linkedin"))  # Jäi samaks
    aadress_val = clean_value(company.get("aadress"))
    pohitegevus_val = clean_value(company.get("emtak_tekst"))  # UUS: otse laetud tekst

    maakond_val_raw = None
    if aadress_val:
        # Parsi maakond aadressist
        maakond_val_raw = aadress_val.split(',')[0].strip()

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
        # 'Kontaktisikud' property on eemaldatud, kuna seda ei salvestata enam DB-sse.
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": pohitegevus_val or ""}}]},
        "Põhitegevus": {"rich_text": [{"text": {"content": pohitegevus_val or ""}}]}
    }

    return properties, empty_fields, company_name


def load_company_data(regcode: str, config: dict) -> dict:
    """
    Loads company data from DB (mitte CSV/JSON)
    (See funktsioon on parandatud, et see kasutaks DB-d)
    """

    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registrikood on puudu või sisaldab mittesoodustavaid sümboleid (peab olema number)."
        }

    try:
        # PARANDUS: Kasutame andmebaasi, mitte ei lae URL-ist
        company = find_company_by_regcode(regcode)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Andmebaasi päringu viga: {e}"
        }

    if not company:
        return {
            "status": "error",
            "message": f"Ettevõtet registrikoodiga {regcode} ei leitud andmebaasist."
        }

    # Prepares Notion properties
    properties, empty_fields, company_name = _prepare_notion_properties(company, regcode)

    return {
        "status": "ready",
        "data": {
            "regcode": regcode,
            "properties": properties,
            "empty_fields": empty_fields,
            "company_name": company_name,
        },
        "message": f"Data found: {company_name} ({regcode})."
    }


def process_company_sync(data: dict, config: dict) -> dict:
    """
    (See funktsioon tundub olevat korras)
    """
    # ... (kood on korras)
    regcode = data["regcode"]
    properties = data["properties"]
    empty_fields = data["empty_fields"]
    company_name = data["company_name"]

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    try:
        existing = notion.query_by_regcode(regcode)
        action = ""

        if existing:
            notion.update_page(existing["id"], properties)
            action = "Uuendatud"
        else:
            full_payload = {
                "parent": {"database_id": notion.database_id},
                "properties": properties
            }
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


def autofill_page_by_page_id(page_id: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Täidab Notioni lehe andmed Äriregistri andmebaasi põhjal.
    (SEE FUNKTSIOON ON NÜÜD PARANDATUD)
    """
    cfg = load_config() if config is None else config

    NOTION_API_KEY = cfg.get("notion", {}).get("token")
    NOTION_DATABASE_ID = cfg.get("notion", {}).get("database_id")
    # ARIREGISTER_JSON_URL pole siin enam vaja, kuna me ei lae faili

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        return {
            "success": False,
            "status": "error",
            "message": "Puudulik Notion konfiguratsioon (NOTION_API_KEY / DATABASE_ID).",
            "step": "config_check"
        }

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

    # 1. Loe Notionist reg. number
    try:
        regcode = notion.get_company_regcode(page_id)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return {"success": False, "status": "error", "message": "Notion API viga: Lehte (pageId) ei leitud.",
                    "step": "notion_read_404"}
        return {"success": False, "status": "error", "message": f"Viga Notionist regcode lugemisel: {e}",
                "step": "notion_read"}
    except Exception as e:
        return {"success": False, "status": "error", "message": f"Viga Notionist regcode lugemisel: {e}",
                "step": "notion_read"}

    if not regcode:
        return {"success": False, "status": "warning", "message": "Lehelt ei leitud 'Registrikood' väärtust.",
                "step": "missing_regcode"}

    logging.info(f"🔍 Otsin ANDMEBAASIST: {regcode}")

    # 2. Lae andmed ANDMEBAASIST (kasutades load_company_data loogikat)
    try:
        load_result = load_company_data(regcode, cfg)
    except Exception as e:
        return {"success": False, "status": "error", "message": f"Viga andmebaasist andmete laadimisel: {e}",
                "step": "db_load"}

    if load_result["status"] != "ready":
        return {"success": False, "status": "warning", "message": load_result["message"], "step": "not_found_in_db"}

    # 3. Puhasta ja vorminda andmed (tehtud load_company_data sees)
    # 4. Uuenda Notionis väljad (kasutades process_company_sync loogikat)

    sync_data = load_result.get("data")
    if not sync_data:
        return {"success": False, "status": "error", "message": "Sisemine viga: Andmete ettevalmistamine ebaõnnestus.",
                "step": "data_prep_fail"}

    try:
        sync_result = process_company_sync(sync_data, cfg)

        if sync_result["status"] == "success" or sync_result["status"] == "warning":
            return {"success": True, "status": sync_result["status"], "message": sync_result["message"], "step": "done"}
        else:
            return {"success": False, "status": "error", "message": sync_result["message"],
                    "step": "notion_update_fail"}

    except Exception as e:
        return {"success": False, "status": "error", "message": f"Viga Notioni uuendamisel: {e}",
                "step": "notion_update_exception"}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Kasutus: python -m api.sync <PAGE_ID>")
        sys.exit(1)

    page_id = sys.argv[1]
    # Initsialiseeri andmebaas lokaalselt (vajalik testimiseks)
    try:
        init_db()
        print("Lokaalne andmebaas initsialiseeritud.")
        # Lokaalsel testimisel pead võib-olla db_loader'i eraldi käivitama
        # Või lisama siia tingimusliku laadimise
    except Exception as e:
        print(f"DB init viga: {e}")

    result = autofill_page_by_page_id(page_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))