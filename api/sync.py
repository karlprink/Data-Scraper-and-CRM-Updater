import os
import requests
import json
import logging
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse
import re

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Assuming these are relative imports in the project structure
from .json_loader import find_company_by_regcode, clean_value
from .notion_client import NotionClient

# --------------------------------------------------------------------
# GOOGLE CUSTOM SEARCH – KONFIG + ABI (TESTIMISEKS VÕTMED OTSE KOODIS)
# --------------------------------------------------------------------

# ⚠️ TESTIMISEKS: asenda oma päris võtmetega.
# Productionis liigu kindlasti ENV muutuja peale.
GOOGLE_API_KEY = "AIzaSyAzB4rD0pNGizFD9vxKnNRVqXtZ5VKzKUg"
GOOGLE_CSE_CX = "56e45d069871c4ec6"

# Must nimekiri domeenidest, mida EI taha "koduleheks"
BLACKLIST_HOSTS = {
    "ariregister.rik.ee",
    "rik.ee",
    "teatmik.ee",
    "inforegister.ee",
    "mtr.mkm.ee",
    "facebook.com",
    "fb.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "wikipedia.org",
    "google.com",
    "maps.google.",
}

def _normalize_host(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.lower()
    except Exception:
        return ""

def _host_blacklisted(host: str) -> bool:
    return any(b in host for b in BLACKLIST_HOSTS)

def _name_tokens(company_name: str):
    tokens = re.split(r"[^a-z0-9]+", company_name.lower())
    stop = {"ou", "oü", "as", "uab", "gmbh", "ltd", "oy", "sp", "z", "uü"}
    return [t for t in tokens if t and t not in stop and len(t) > 2]

def _name_matches_host(company_name: str, host: str) -> bool:
    tokens = _name_tokens(company_name)
    return any(t in host for t in tokens)

def _pick_homepage(candidates, company_name: str) -> Optional[str]:
    """
    Valib esimese mõistliku URL-i:
    - väldib musta nimekirja domeene
    - eelistab .ee domeeni või nimega sobivat hosti
    """
    primary = None
    for url in candidates:
        host = _normalize_host(url)
        if not host or _host_blacklisted(host):
            continue
        if host.endswith(".ee") or _name_matches_host(company_name, host):
            return url
        if not primary:
            primary = url
    return primary

def google_find_website(company_name: str) -> Optional[str]:
    """
    Kasutab Google Custom Search JSON API-t, et leida ettevõtte koduleht.
    - Query: "<firma nimi> official website"
    - Võtab kuni 5 tulemust ja valib _pick_homepage abil sobiva.
    """
    if not company_name:
        return None
    if not GOOGLE_API_KEY or not GOOGLE_CSE_CX:
        logging.info("Google API key/cx puudub – jätan veebilehe otsingu vahele.")
        return None

    try:
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_CX,
            "q": f"{company_name} official website",
            "num": 5,
            "gl": "ee",
            "lr": "lang_et|lang_en",
        }
        r = requests.get("https://www.googleapis.com/customsearch/v1",
                         params=params, timeout=6)
        r.raise_for_status()
        data = r.json() or {}
        items = data.get("items", []) or []
        candidates = [it.get("link") for it in items if it.get("link")]
        if not candidates:
            logging.info("Google CSE ei tagastanud ühtegi kandidaati.")
            return None
        picked = _pick_homepage(candidates, company_name)
        if picked:
            logging.info(f"Google CSE leidis kodulehe: {picked}")
        else:
            logging.info("Google CSE ei leidnud sobivat kodulehte (kõik kandidaadid olid mustas nimekirjas vms).")
        return picked
    except Exception as e:
        logging.warning(f"Google CSE päring ebaõnnestus: {e}")
        return None

# --------------------------------------------------------------------
# EMTAK (Estonian Classification of Economic Activities) Mapping
# --------------------------------------------------------------------

EMTAK_MAP = {
    "01": "Põllumajandus, metsamajandus ja kalapüük",
    "02": "Põllumajandus, metsamajandus ja kalapüük",
    "03": "Põllumajandus, metsamajandus ja kalapüük",
    "05": "Mäetööstus",
    "06": "Mäetööstus",
    "07": "Mäetööstus",
    "08": "Mäetööstus",
    "09": "Mäetööstus",
    "10": "Töötlev tööstus",
    "11": "Töötlev tööstus",
    "12": "Töötlev tööstus",
    "13": "Töötlev tööstus",
    "14": "Töötlev tööstus",
    "15": "Töötlev tööstus",
    "16": "Töötlev tööstus",
    "17": "Töötlev tööstus",
    "18": "Töötlev tööstus",
    "19": "Töötlev tööstus",
    "20": "Töötlev tööstus",
    "21": "Töötlev tööstus",
    "22": "Töötlev tööstus",
    "23": "Töötlev tööstus",
    "24": "Töötlev tööstus",
    "25": "Töötlev tööstus",
    "26": "Töötlev tööstus",
    "27": "Töötlev tööstus",
    "28": "Töötlev tööstus",
    "29": "Töötlev tööstus",
    "30": "Töötlev tööstus",
    "31": "Töötlev tööstus",
    "32": "Töötlev tööstus",
    "33": "Töötlev tööstus",
    "35": "Elektrienergia, gaasi, auru ja konditsioneeritud õhuga varustamine",
    "36": "Veevarustus; kanalisatsioon, jäätme- ja saastekäitlus",
    "37": "Veevarustus; kanalisatsioon, jäätme- ja saastekäitlus",
    "38": "Veevarustus; kanalisatsioon, jäätme- ja saastekäitlus",
    "39": "Veevarustus; kanalisatsioon, jäätme- ja saastekäitlus",
    "41": "Ehitus",
    "42": "Ehitus",
    "43": "Ehitus",
    "45": "Hulgi- ja jaekaubandus; mootorsõidukite ja mootorrataste re ...",
    "46": "Hulgi- ja jaekaubandus; mootorsõidukite ja mootorrataste re ...",
    "47": "Hulgi- ja jaekaubandus; mootorsõidukite ja mootorrataste re ...",
    "49": "Veondus ja laondus",
    "50": "Veondus ja laondus",
    "51": "Veondus ja laondus",
    "52": "Veondus ja laondus",
    "53": "Veondus ja laondus",
    "55": "Majutus ja toitlustus",
    "56": "Majutus ja toitlustus",
    "58": "Info ja side",
    "59": "Info ja side",
    "60": "Info ja side",
    "61": "Info ja side",
    "62": "Info ja side",
    "63": "Info ja side",
    "64": "Finants- ja kindlustustegevus",
    "65": "Finants- ja kindlustustegevus",
    "66": "Finants- ja kindlustustegevus",
    "68": "Kinnisvaraalane tegevus",
    "69": "Kutse-, teadus- ja tehnikaalane tegevus",
    "70": "Kutse-, teadus- ja tehnikaalane tegevus",
    "71": "Kutse-, teadus- ja tehnikaalane tegevus",
    "72": "Kutse-, teadus- ja tehnikaalane tegevus",
    "73": "Kutse-, teadus- ja tehnikaalane tegevus",
    "74": "Kutse-, teadus- ja tehnikaalane tegevus",
    "75": "Kutse-, teadus- ja tehnikaalane tegevus",
    "77": "Haldus- ja abitegevused",
    "78": "Haldus- ja abitegevused",
    "79": "Haldus- ja abitegevused",
    "80": "Haldus- ja abitegevused",
    "81": "Haldus- ja abitegevused",
    "82": "Haldus- ja abitegevused",
    "84": "Avalik haldus ja riigikaitse; kohustuslik sotsiaalkindlustus",
    "85": "Haridus",
    "86": "Tervishoid ja sotsiaalhoolekanne",
    "87": "Tervishoid ja sotsiaalhoolekanne",
    "88": "Tervishoid ja sotsiaalhoolekanne",
    "90": "Kunst, meelelahutus ja vaba aeg",
    "91": "Kunst, meelelahutus ja vaba aeg",
    "92": "Kunst, meelelahutus ja vaba aeg",
    "93": "Kunst, meelelahutus ja vaba aeg",
    "94": "Muud teenindavad tegevused",
    "95": "Muud teenindavad tegevused",
    "96": "Muud teenindavad tegevused",
    "97": "Kodumajapidamiste kui tööandjate tegevus; kodumajapidam ...",
    "98": "Kodumajapidamiste kui tööandjate tegevus; kodumajapidam ...",
    "99": "Eksterritoriaalsete organisatsioonide ja üksuste tegevus",
}

# --- EMTAK Code Utilities ---

def get_emtak_section_text(emtak_code: Optional[str]) -> Optional[str]:
    """
    Finds the broader industry section (Tegevusvaldkond) based on the first
    two digits of the EMTAK code using the internal EMTAK_MAP.
    """
    if not emtak_code:
        return None

    cleaned_code = "".join(filter(str.isdigit, str(emtak_code)))
    if len(cleaned_code) >= 2:
        two_digit_code = cleaned_code[:2]
        return EMTAK_MAP.get(two_digit_code)

    return None

# --- Data Transformation Functions ---

def _prepare_notion_properties(company: Dict[str, Any], regcode: str) -> Tuple[Dict[str, Any], list, str]:
    company_name = clean_value(company.get('nimi'))
    cleaned_company = {k: clean_value(v) for k, v in company.items()}
    return _build_properties_from_company(cleaned_company, regcode, company_name)

def _build_properties_from_company(company: Dict[str, Any], regcode: str, company_name: str) -> Tuple[Dict[str, Any], list, str]:
    yldandmed = company.get('yldandmed', {})

    email_val = None
    tel_val = None
    veeb_val = None
    linkedin_val = clean_value(company.get("linkedin"))

    # Extract communication data
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

    # Extract address data
    aadressid = yldandmed.get('aadressid', [])
    aadress_täis_val = clean_value(
        aadressid[0].get('aadress_ads__ads_normaliseeritud_taisaadress')) if aadressid and aadressid[0].get(
        'aadress_ads__ads_normaliseeritud_taisaadress') else None
    aadress_val = aadress_täis_val

    # Extract county (Maakond)
    maakond_val_raw = None
    if aadress_täis_val:
        parts = aadress_täis_val.split(',')
        maakond_val_raw = parts[0].strip() if parts else None

    # Extract main activity (Põhitegevus)
    tegevusalad = yldandmed.get('teatatud_tegevusalad', [])
    pohitegevusala = next(
        (ta for ta in tegevusalad if ta.get('on_pohitegevusala') is True),
        None
    )

    emtak_kood_val = clean_value(pohitegevusala.get("emtak_kood")) if pohitegevusala else None
    emtak_detailne_tekst_val = clean_value(pohitegevusala.get("emtak_tekstina")) if pohitegevusala else None
    emtak_jaotis_val = get_emtak_section_text(emtak_kood_val)

    empty_fields = []

    # Maakond
    if maakond_val_raw:
        maakond_prop: Dict[str, Any] = {"multi_select": [{"name": maakond_val_raw}]}
    else:
        maakond_prop = {"multi_select": []}
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
    if not emtak_detailne_tekst_val: empty_fields.append("Põhitegevus")
    if not emtak_jaotis_val: empty_fields.append("Tegevusvaldkond (jaotis)")

    properties = {
        "Nimi": {"title": [{"text": {"content": company_name or ""}}]},
        "Registrikood": {"number": int(regcode)} if regcode.isdigit() else {"number": None},
        "Aadress": {"rich_text": [{"text": {"content": aadress_val or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": yldandmed.get("kontaktisikud_list", [])},
        "Põhitegevus": {"rich_text": [{"text": {"content": emtak_detailne_tekst_val or ""}}]},
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": emtak_jaotis_val or ""}}]},
    }

    return properties, empty_fields, company_name or ""

# --- CLI/Interactive Mode Helper Functions ---

def load_company_data(regcode: str, config: Dict[str, Any]) -> Dict[str, Any]:
    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registry code is missing or contains non-digit characters (must be a number)."
        }

    try:
        company = find_company_by_regcode(config["ariregister"]["json_url"], regcode)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading file: {e}"
        }

    if not company:
        return {
            "status": "error",
            "message": f"Company with registry code {regcode} not found in the Business Register data (JSON)."
        }

    company_name = clean_value(company.get('nimi'))
    properties, empty_fields, company_name = _build_properties_from_company(company, regcode, company_name)

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

def process_company_sync(data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    regcode = data["regcode"]
    properties = data["properties"]
    empty_fields = data["empty_fields"]
    company_name = data["company_name"]

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    full_payload = {
        "parent": {"database_id": notion.database_id},
        "properties": properties
    }

    try:
        existing = notion.query_by_regcode(regcode)
        action = ""

        if existing:
            notion.update_page(existing["id"], properties)
            action = "Successfully Updated"
        else:
            notion.create_page(full_payload)
            action = "Successfully Created"

        status = "success"
        message = f"✅ {action}: {company_name} ({regcode}). Record was synchronized to Notion."

        if empty_fields:
            status = "warning"
            message += f"\n ⚠️ Warning: The following fields were left empty: {', '.join(empty_fields)}."

        return {"status": status, "message": message, "company_name": company_name}

    except requests.HTTPError as e:
        error_details = ""
        try:
            error_details = e.response.json().get("message", e.response.text)
        except:
            error_details = e.response.text

        return {
            "status": "error",
            "message": f"❌ Notion API Error ({e.response.status_code}): {error_details}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ General Synchronization Error: {type(e).__name__}: {e}"
        }

# --- Web/API Autofill Logic ---

def autofill_page_by_page_id(page_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    logging.info(f"--- Starting autofill for page_id: {page_id} ---")

    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    ARIREGISTER_JSON_URL = config.get("ariregister", {}).get("json_url")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL]):
        error_msg = "Missing one or more required configuration (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL)."
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "config_check"}

    logging.debug(f"Using NOTION_DATABASE_ID: {NOTION_DATABASE_ID}")

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

    # 1. Fetch Page and Extract Registry Code
    regcode = None
    try:
        page = notion.get_page(page_id)
        props = page.get("properties", {})
        logging.info("Successfully fetched page properties from Notion.")

        reg_prop = props.get("Registrikood")

        if not reg_prop:
            logging.error(f"Page 'Registrikood' property is missing. Available properties: {list(props.keys())}")
            return {"success": False, "message": "The 'Registrikood' property is missing on the Notion page.", "step": "missing_registrikood"}

        prop_type = reg_prop.get("type")

        if prop_type == "number":
            val = reg_prop.get("number")
            if val is not None:
                regcode = str(int(val))
        elif prop_type in ("title", "rich_text"):
            texts = reg_prop.get(prop_type) or []
            if texts:
                content = texts[0].get("plain_text") or texts[0].get("text", {}).get("content")
                if content:
                    regcode = ''.join(ch for ch in content if ch.isdigit())

        if not regcode:
            error_msg = "'Registrikood' value is empty or in an invalid format on the Notion page."
            logging.warning(error_msg)
            return {"success": False, "message": error_msg, "step": "invalid_registrikood"}

        logging.info(f"Found Registrikood: {regcode}")

    except Exception as e:
        error_msg = f"Failed to fetch page or extract data from Notion: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "fetch_page_or_extract"}

    # 2. Fetch Company Data from JSON
    try:
        company = find_company_by_regcode(ARIREGISTER_JSON_URL, regcode)
        logging.info("Successfully loaded data and searched company.")
    except Exception as e:
        error_msg = f"Failed to load JSON or search company: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "load_json_or_search"}

    if not company:
        error_msg = f"Company with registry code {regcode} not found in JSON data."
        logging.warning(error_msg)
        return {"success": False, "message": error_msg, "step": "company_not_found", "regcode": regcode}

    logging.info(f"Found matching company in JSON: {clean_value(company.get('nimi'))}")

    # 3. Prepare Payload
    company_name = clean_value(company.get('nimi'))
    properties, empty_fields, _ = _build_properties_from_company(company, regcode, company_name)
    logging.debug("Built properties payload to send to Notion.")

    # 3.1 Kui Veebileht puudub, proovi leida Google CSE kaudu
    veeb_prop = properties.get("Veebileht", {})
    existing_url = veeb_prop.get("url")
    if not existing_url:
        logging.info("Veebileht puudub Äriregistri andmetes – proovime leida Google CSE abil.")
        homepage = google_find_website(company_name)
        if homepage:
            properties["Veebileht"]["url"] = homepage
            if "Veebileht" in empty_fields:
                empty_fields.remove("Veebileht")
        else:
            logging.info("Google ei leidnud sobivat kodulehte, jätame Veebileht tühjaks.")

    # 4. Update Notion
    try:
        notion.update_page(page_id, properties)
        message = f"✅ Data successfully autofilled for page {company_name} ({regcode})."

        if empty_fields:
            message += f"\n ⚠️ Warning: The following fields were left empty: {', '.join(empty_fields)}."

        logging.info(message)
        return {"success": True, "message": message, "company_name": company_name}

    except requests.HTTPError as e:
        error_details = ""
        try:
            error_details = e.response.json().get("message", e.response.text)
        except:
            error_details = e.response.text

        error_msg = f"❌ Notion API Error ({e.response.status_code}): {error_details}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "notion_update"}
    except Exception as e:
        error_msg = f"❌ General Autofill Error: {type(e).__name__}: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "general_error"}