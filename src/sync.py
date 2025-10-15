import requests

from .csv_loader import load_csv, find_company_by_regcode, clean_value
from .notion_client import NotionClient
import json


def sync_company(regcode: str, config: dict):

    # Load csv
    df = load_csv(config["ariregister"]["csv_url"])
    company = find_company_by_regcode(df, regcode)

    if not company:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud CSV-s.")
        return

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    properties = _build_properties_from_company(company)

    # Compose full payload for notin db
    data = {
        "parent": {"database_id": notion.database_id},
        "properties": properties
    }

    # Kontrollprint payload
    print("Notion payload:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # Check if exists already in notion database
    try:
        existing = notion.query_by_regcode(regcode)

        if existing:
            page_id = existing["id"]
            notion.update_page(page_id, properties)
            print(f"✅ Uuendatud: {clean_value(company.get('nimi'))} ({regcode})")
        else:
            notion.create_page(data)
            print(f"➕ Lisatud: {clean_value(company.get('nimi'))} ({regcode})")

    except requests.HTTPError as e:
        # Catch error detailss
        error_details = ""
        try:
            error_details = e.response.json()
        except:
            error_details = e.response.text

        print(f"❌ Viga Notion API-s ({e.response.status_code} {e.response.reason}):")
        print(json.dumps(error_details, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Üldine viga: {e}")


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


def autofill_page_by_page_id(page_id: str, config: dict):
    """Loeb Registrikood property antud Notioni lehelt ning täidab ülejäänud väljad."""
    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"],
    )

    # Loe lehe properties
    page = notion.get_page(page_id)
    props = page.get("properties", {})

    reg_prop = props.get("Registrikood")
    if not reg_prop:
        print("❌ Lehe 'Registrikood' property puudub.")
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
        print("❌ 'Registrikood' on tühi või vales formaadis sellel Notioni lehel.")
        return

    # Lae CSV ja leia ettevõte
    df = load_csv(config["ariregister"]["csv_url"])
    company = find_company_by_regcode(df, regcode)
    if not company:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud CSV-s.")
        return

    properties = _build_properties_from_company(company)
    # Uuenda sama lehte
    notion.update_page(page_id, properties)
    print(f"✅ Täidetud leht: {clean_value(company.get('nimi'))} ({regcode})")
