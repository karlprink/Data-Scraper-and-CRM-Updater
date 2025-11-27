import logging
import re
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse

import requests

from .config import load_config
from .clients.google_client import GoogleClient

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Assuming these are relative imports in the project structure
from .json_loader import find_company_by_regcode, clean_value
from .clients.notion_client import NotionClient

# --------------------------------------------------------------------
# GOOGLE CUSTOM SEARCH – kodulehe leidmine, kui Äriregistris WWW puudub
# --------------------------------------------------------------------

config = load_config()
GOOGLE_API_KEY = config.get("google", {}).get("api_key")
GOOGLE_CSE_CX = config.get("google", {}).get("cse_cx")

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
    "aripaev.ee",
    ".bdf",
}


def _normalize_host(url: str) -> str:
    """Tagastab URL-i hosti väikeste tähtedega, vea korral tühja stringi."""
    try:
        host = urlparse(url).hostname or ""
        return host.lower()
    except Exception:
        return ""


def _host_blacklisted(host: str) -> bool:
    """Kontrollib, kas host kuulub musta nimekirja (registrid, kataloogid, sotsiaal jne)."""
    return any(b in host for b in BLACKLIST_HOSTS)


def _name_tokens(company_name: str):
    """
    Võtab ettevõtte nimest tokenid:
    - väiketähtedeks
    - jagab mitte-alfanum märgi järgi
    - eemaldab tüüpsufiksid (OÜ, AS, UAB, jne) ja liiga lühikesed tokenid
    """
    tokens = re.split(r"[^a-z0-9]+", company_name.lower())
    stop = {"ou", "oü", "as", "uab", "gmbh", "ltd", "oy", "sp", "z", "uü"}
    return [t for t in tokens if t and t not in stop and len(t) > 2]


def _score_candidate(host: str, company_name: str) -> int:
    """
    Lihtne skoor:
    - +3 kui host lõppeb .ee
    - +2 kui mõni nime-token esineb hostis
    - muidu 0
    Kõrgem skoor = parem kandidaat.
    """
    score = 0
    if host.endswith(".ee"):
        score += 3
    tokens = _name_tokens(company_name)
    if any(t in host for t in tokens):
        score += 2
    return score


def google_find_website(company_name: str) -> Optional[str]:
    """
    Kasutab Google Custom Search JSON API-t, et leida ettevõtte koduleht.

    Loogika:
    - Query: "<firma nimi> official website"
    - Võtab kuni 10 esimest tulemust.
    - Filtreerib välja:
        * mustas nimekirjas oleva hostiga URL-id (registrid, kataloogid, sotsiaal jne)
    - Ülejäänute seast:
        * arvutab skoori (_score_candidate):
            - eelistab .ee domeene
            - eelistab hoste, kus esineb firma nime token
        * valib suurima skooriga kandidaadi (esimese, kui viik)
    - Kui sobivat kandidaati ei leidu, tagastab None.
    """
    if not company_name:
        return None
    if not GOOGLE_API_KEY or not GOOGLE_CSE_CX:
        logging.info("Google API key/cx puudub – jätan veebilehe otsingu vahele.")
        return None

    try:
        google_client = GoogleClient(GOOGLE_API_KEY, GOOGLE_CSE_CX)
        results = google_client.get_search_results(f"{company_name} official website")
        items = results.get("items", []) or []

        candidates = []
        for item in items:
            url = item.get("link")
            if not url:
                continue
            host = _normalize_host(url)
            if not host or _host_blacklisted(host):
                # väldi registri- ja kataloogilehti, sotsmeediat jne
                continue

            score = _score_candidate(host, company_name)
            candidates.append((score, url, host))

        if not candidates:
            logging.info("Google CSE 10 esimese tulemuse seas ei leitud ühtegi sobivat kodulehe kandidaati.")
            return None

        # Sorteerime skoori järgi (kõrgeim enne); sama skoori korral jääb varasem enne.
        candidates.sort(key=lambda t: t[0], reverse=True)
        best_score, best_url, best_host = candidates[0]
        logging.info(f"Google CSE valis sobiva kodulehe (score={best_score}): {best_host} -> {best_url}")
        return best_url

    except Exception as e:
        logging.warning(f"Google CSE päring ebaõnnestus: {e}")
        return None


# --------------------------------------------------------------------
# --- EMTAK (Estonian Classification of Economic Activities) Mapping ---
# Maps the 2-digit EMTAK code to its broader section/industry category (Tegevusvaldkond).
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
    "53": "Veondus ja laондus",
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

    Args:
        emtak_code: The detailed EMTAK code (e.g., '73111').

    Returns:
        The corresponding industry section name (e.g., 'Kutse-, teadus...') or None.
    """
    if not emtak_code:
        return None

    # Filter out non-digit characters
    cleaned_code = "".join(filter(str.isdigit, str(emtak_code)))

    if len(cleaned_code) >= 2:
        two_digit_code = cleaned_code[:2]
        return EMTAK_MAP.get(two_digit_code)

    return None

# --- Data Transformation Functions ---


def _prepare_notion_properties(company: Dict[str, Any], regcode: str) -> Tuple[Dict[str, Any], list, str]:
    """
    Cleans company data and aggregates it into the Notion Properties format,
    tracking fields that remain empty.

    Args:
        company: The raw company dictionary fetched from the JSON.
        regcode: The company's registry code.

    Returns:
        A tuple containing:
        - properties (Dict[str, Any]): The Notion properties payload.
        - empty_fields (list): A list of Notion fields that were left empty.
        - company_name (str): The cleaned company name.
    """
    company_name = clean_value(company.get('nimi'))
    # Clean the entire dictionary before building properties
    cleaned_company = {k: clean_value(v) for k, v in company.items()}
    return _build_properties_from_company(cleaned_company, regcode, company_name)


def _build_properties_from_company(company: Dict[str, Any], regcode: str, company_name: str) -> Tuple[Dict[str, Any], list, str]:
    """
    Constructs the Notion properties object based on cleaned JSON data.

    This function extracts, transforms, and formats company data fields:
    - Põhitegevus (Main Activity): Uses the detailed EMTAK text from JSON.
    - Tegevusvaldkond (Industry Section): Uses the 2-digit EMTAK code to map
      to a broader section (EMTAK_MAP).

    Args:
        company: The cleaned company dictionary.
        regcode: The company's registry code.
        company_name: The company's name.

    Returns:
        A tuple containing:
        - properties (Dict[str, Any]): The Notion properties payload.
        - empty_fields (list): A list of Notion fields that were left empty.
        - company_name (str): The company name.
    """

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
            # Prioritize the first phone number found
            if not tel_val:
                tel_val = sisu
        elif liik == "WWW":
            veeb_val = sisu

    # Extract address data
    aadressid = yldandmed.get('aadressid', [])
    aadress_täis_val = clean_value(
        aadressid[0].get('aadress_ads__ads_normaliseeritud_taisaadress')) if aadressid and aadressid[0].get(
        'aadress_ads__ads_normaliseeritud_taisaadress') else None
    aadress_val = aadress_täis_val  # Use full address as the main address field

    # Extract county (Maakond)
    maakond_val_raw = None
    if aadress_täis_val:
        # Assumes county is the first part of the full address string
        parts = aadress_täis_val.split(',')
        maakond_val_raw = parts[0].strip() if parts else None

    # Extract main activity (Põhitegevus)
    tegevusalad = yldandmed.get('teatatud_tegevusalad', [])
    pohitegevusala = next(
        (ta for ta in tegevusalad if ta.get('on_pohitegevusala') is True),
        None
    )

    # 1. Get detailed EMTAK code (e.g., '73111') and text (e.g., 'Reklaamiagentuuride tegevus')
    # FIX APPLIED: Using 'emtak_kood' from JSON, as 'emtak_kood_tekstina' is often None/missing the raw code.
    emtak_kood_val = clean_value(pohitegevusala.get("emtak_kood")) if pohitegevusala else None
    emtak_detailne_tekst_val = clean_value(pohitegevusala.get("emtak_tekstina")) if pohitegevusala else None

    # 2. Use the 2-digit code to find the broader section (Tegevusvaldkond)
    emtak_jaotis_val = get_emtak_section_text(emtak_kood_val)

    # --- Prepare Notion Properties and Track Empty Fields ---
    empty_fields = []

    # Map County to Notion multi_select
    maakond_prop: Dict[str, Any]
    if maakond_val_raw:
        maakond_prop = {"multi_select": [{"name": maakond_val_raw}]}
    else:
        maakond_prop = {"multi_select": []}
        empty_fields.append("Maakond")

    # Prepare simple value Notion properties
    email_prop = {"email": email_val} if email_val else {"email": None}
    tel_prop = {"phone_number": tel_val} if tel_val else {"phone_number": None}
    veeb_prop = {"url": veeb_val} if veeb_val else {"url": None}
    linkedin_prop = {"url": linkedin_val} if linkedin_val else {"url": None}

    # Track simple empty fields
    if not email_val: empty_fields.append("E-post")
    if not tel_val: empty_fields.append("Tel. nr")
    if not veeb_val: empty_fields.append("Veebileht")
    if not linkedin_val: empty_fields.append("LinkedIn")
    if not aadress_val: empty_fields.append("Aadress")

    # Track activity fields
    if not emtak_detailne_tekst_val: empty_fields.append("Põhitegevus")
    if not emtak_jaotis_val: empty_fields.append("Tegevusvaldkond (jaotis)")

    properties = {
        "Nimi": {"title": [{"text": {"content": company_name or ""}}]},
        # Assuming Registrikood property is set as 'Number' in Notion
        "Registrikood": {"number": int(regcode)} if regcode.isdigit() else {"number": None},
        "Aadress": {
            "rich_text": [{"text": {"content": aadress_val or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": yldandmed.get("kontaktisikud_list", [])},

        # Põhitegevus (Main Activity): Detailed text from JSON
        "Põhitegevus": {"rich_text": [{"text": {"content": emtak_detailne_tekst_val or ""}}]},

        # Tegevusvaldkond (Industry Section): Broad category from EMTAK_MAP
        "Tegevusvaldkond": {"rich_text": [{"text": {"content": emtak_jaotis_val or ""}}]}
    }

    return properties, empty_fields, company_name or ""

# --- CLI/Interactive Mode Helper Functions ---


def load_company_data(regcode: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Loads company data from the JSON file and prepares the Notion property
    structures. Used before user confirmation in CLI mode.

    Args:
        regcode: The registry code of the company.
        config: The application configuration dictionary.

    Returns:
        A dictionary containing the status, data payload, and message.
    """

    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registry code is missing or contains non-digit characters (must be a number)."
        }

    try:
        # find_company_by_regcode automatically cleans the data (clean_value)
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
    # Prepare properties using the corrected logic
    properties, empty_fields, company_name = _build_properties_from_company(company, regcode, company_name)

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


def process_company_sync(data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs the final Notion API synchronization: creating a new page or
    updating an existing one based on the registry code.

    Args:
        data: The prepared company data dictionary from load_company_data.
        config: The application configuration dictionary.

    Returns:
        A dictionary containing the status and outcome message of the sync operation.
    """

    regcode = data["regcode"]
    properties = data["properties"]
    empty_fields = data["empty_fields"]
    company_name = data["company_name"]

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    # Compose full payload for creation
    full_payload = {
        "parent": {"database_id": notion.database_id},
        "properties": properties
    }

    try:
        # 1. Check if the entry already exists
        existing = notion.query_by_regcode(regcode)
        action = ""

        if existing:
            # Update existing page
            notion.update_page(existing["id"], properties)
            action = "Successfully Updated"
        else:
            # Create a new page
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
    """
    Fetches the 'Registrikood' from a given Notion page, finds the corresponding
    company data, and updates the Notion page properties.

    Args:
        page_id: The ID of the Notion page to autofill.
        config: The application configuration dictionary.

    Returns:
        A dictionary with the result status and message.
    """
    logging.info(f"--- Starting autofill for page_id: {page_id} ---")

    # Extract configuration variables
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    ARIREGISTER_JSON_URL = config.get("ariregister", {}).get("json_url")

    # Configuration validation
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

        # Logic to extract regcode regardless of property type (Number, Title, Rich Text)
        prop_type = reg_prop.get("type")

        if prop_type == "number":
            val = reg_prop.get("number")
            if val is not None:
                regcode = str(int(val))
        elif prop_type in ("title", "rich_text"):
            texts = reg_prop.get(prop_type) or []
            if texts:
                # Use plain_text or text content and extract only digits
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

    # 3. Prepare Payload and Update Notion
    company_name = clean_value(company.get('nimi'))
    properties, empty_fields, _ = _build_properties_from_company(company, regcode, company_name)
    logging.debug("Built properties payload to send to Notion.")

    # 3.1 Kui Veebileht puudub, proovi leida Google CSE kaudu (kuni 10 esimest, skooriga)
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
            logging.info("Google ei leidnud sobivat kodulehte (10 esimese tulemuse seas), jätame Veebileht tühjaks.")

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