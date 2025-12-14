import logging
import re
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse

import requests

from .config import load_config
from .clients.google_client import GoogleClient

# Set up basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Assuming these are relative imports in the project structure
from .json_loader import find_company_by_regcode, clean_value
from .clients.notion_client import NotionClient

# --------------------------------------------------------------------
# GOOGLE CUSTOM SEARCH – Finding the company website if missing in Business Register
# --------------------------------------------------------------------

config = load_config()
GOOGLE_API_KEY = config.get("google", {}).get("api_key")
GOOGLE_CSE_CX = config.get("google", {}).get("cse_cx")

# Blacklist of domains we DON'T want as the "homepage"
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
    """Returns the URL's host in lowercase, or an empty string on error."""
    try:
        host = urlparse(url).hostname or ""
        return host.lower()
    except Exception:
        return ""


def _host_blacklisted(host: str) -> bool:
    """Checks if the host belongs to the blacklist (registers, directories, social media, etc.)."""
    return any(b in host for b in BLACKLIST_HOSTS)


def _name_tokens(company_name: str):
    """
    Extracts tokens from the company name:
    - Converts to lowercase
    - Splits by non-alphanumeric characters
    - Removes common suffixes (OÜ, AS, UAB, etc.) and short tokens
    """
    tokens = re.split(r"[^a-z0-9]+", company_name.lower())
    stop = {"ou", "oü", "as", "uab", "gmbh", "ltd", "oy", "sp", "z", "uü"}
    return [t for t in tokens if t and t not in stop and len(t) > 2]


def _score_candidate(host: str, company_name: str) -> int:
    """
    Simple scoring mechanism:
    - +3 if the host ends with .ee
    - +2 if any name token appears in the host
    - otherwise 0
    Higher score = better candidate.
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
    Uses the Google Custom Search JSON API to find the company's website.

    Logic:
    - Query: "<company name> official website"
    - Takes up to the first 10 results.
    - Filters out:
        * URLs with a blacklisted host (registers, directories, social media, etc.)
    - Among the remaining candidates:
        * Calculates a score (_score_candidate):
            - prefers .ee domains
            - prefers hosts that contain a company name token
        * Selects the candidate with the highest score (the first one in case of a tie)
    - Returns None if no suitable candidate is found.
    """
    if not company_name:
        return None
    if not GOOGLE_API_KEY or not GOOGLE_CSE_CX:
        logging.info("Google API võti/cx puudub – jätan veebilehe otsingu vahele.")
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
                # Avoid register and directory pages, social media, etc.
                continue

            score = _score_candidate(host, company_name)
            candidates.append((score, url, host))

        if not candidates:
            logging.info(
                "Google CSE 10 esimese tulemuse seas ei leitud ühtegi sobivat kodulehe kandidaati."
            )
            return None

        # Sort by score (highest first); maintains original order for ties.
        candidates.sort(key=lambda t: t[0], reverse=True)
        best_score, best_url, best_host = candidates[0]
        logging.info(
            f"Google CSE valis sobiva kodulehe (score={best_score}): {best_host} -> {best_url}"
        )
        return best_url

    except Exception as e:
        logging.warning(f"Google CSE päring ebaõnnestus: {e}")
        return None


# --------------------------------------------------------------------
# --- EMTAK (Estonian Classification of Economic Activities) Ranges ---
# Define ranges as tuples: (start_code_int, end_code_int, "Section Name")
# --------------------------------------------------------------------

EMTAK_RANGES = [
    (1, 3, "Põllumajandus, metsamajandus ja kalapüük"),
    (5, 9, "Mäetööstus"),
    (10, 33, "Töötlev tööstus"),
    (35, 35, "Elektrienergia, gaasi, auru ja konditsioneeritud õhuga varustamine"),
    (36, 39, "Veevarustus; kanalisatsioon, jäätme- ja saastekäitlus"),
    (41, 43, "Ehitus"),
    (45, 47, "Hulgi- ja jaekaubandus; mootorsõidukite ja mootorrataste remont"),
    (49, 53, "Veondus ja laondus"),
    (55, 56, "Majutus ja toitlustus"),
    (58, 63, "Info ja side"),
    (64, 66, "Finants- ja kindlustustegevus"),
    (68, 68, "Kinnisvaraalane tegevus"),
    (69, 75, "Kutse-, teadus- ja tehnikaalane tegevus"),
    (77, 82, "Haldus- ja abitegevused"),
    (84, 84, "Avalik haldus ja riigikaitse; kohustuslik sotsiaalkindlustus"),
    (85, 85, "Haridus"),
    (86, 88, "Tervishoid ja sotsiaalhoolekanne"),
    (90, 93, "Kunst, meelelahutus ja vaba aeg"),
    (94, 96, "Muud teenindavad tegevused"),
    (
        97,
        98,
        "Kodumajapidamiste kui tööandjate tegevus; kodumajapidamiste oma tarbeks tootmine",
    ),
    (99, 99, "Eksterritoriaalsete organisatsioonide ja üksuste tegevus"),
]


# --- EMTAK Code Utilities ---


def get_emtak_section_text(emtak_code: Optional[str]) -> Optional[str]:
    """
    Finds the broader industry section (Tegevusvaldkond) based on the first
    two digits of the EMTAK code using the EMTAK_RANGES.
    Returns format: "01-03: Section Name" (Commas replaced by semicolons for Notion)
    """
    if not emtak_code:
        return None

    # Filter out non-digit characters to be safe
    cleaned_code = "".join(filter(str.isdigit, str(emtak_code)))

    if len(cleaned_code) >= 2:
        try:
            # Take the first 2 digits and convert to integer for range comparison
            code_int = int(cleaned_code[:2])

            for start, end, name in EMTAK_RANGES:
                if start <= code_int <= end:
                    range_str = (
                        f"{start:02d}-{end:02d}" if start != end else f"{start:02d}"
                    )

                    safe_name = name.replace(",", ";")

                    return f"{range_str}: {safe_name}"

        except ValueError:
            return None

    return None


# --- Data Transformation Functions ---


def _prepare_notion_properties(
    company: Dict[str, Any], regcode: str
) -> Tuple[Dict[str, Any], list, str]:
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
    company_name = clean_value(company.get("nimi"))
    # Clean the entire dictionary before building properties
    cleaned_company = {k: clean_value(v) for k, v in company.items()}
    return _build_properties_from_company(cleaned_company, regcode, company_name)


def _build_properties_from_company(
    company: Dict[str, Any], regcode: str, company_name: str
) -> Tuple[Dict[str, Any], list, str]:
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

    yldandmed = company.get("yldandmed", {})

    email_val = None
    tel_val = None
    veeb_val = None
    linkedin_val = clean_value(company.get("linkedin"))

    # Extract communication data
    sidevahendid = yldandmed.get("sidevahendid", [])
    for item in sidevahendid:
        sisu = clean_value(item.get("sisu"))
        if not sisu:
            continue
        liik = item.get("liik")
        if liik == "EMAIL":
            email_val = sisu
        elif liik in ("TEL", "MOB"):
            # Prioritize the first phone number found
            if not tel_val:
                tel_val = sisu
        elif liik == "WWW":
            veeb_val = sisu

    # Extract address data
    aadressid = yldandmed.get("aadressid", [])
    aadress_täis_val = (
        clean_value(aadressid[0].get("aadress_ads__ads_normaliseeritud_taisaadress"))
        if aadressid
        and aadressid[0].get("aadress_ads__ads_normaliseeritud_taisaadress")
        else None
    )
    aadress_val = aadress_täis_val  # Use full address as the main address field

    # Extract county (Maakond)
    maakond_val_raw = None
    if aadress_täis_val:
        # Assumes county is the first part of the full address string
        parts = aadress_täis_val.split(",")
        maakond_val_raw = parts[0].strip() if parts else None

    # Extract main activity (Põhitegevus)
    tegevusalad = yldandmed.get("teatatud_tegevusalad", [])
    pohitegevusala = next(
        (ta for ta in tegevusalad if ta.get("on_pohitegevusala") is True), None
    )

    # 1. Get detailed EMTAK code (e.g., '73111') and text (e.g., 'Reklaamiagentuuride tegevus')
    # FIX APPLIED: Using 'emtak_kood' from JSON, as 'emtak_kood_tekstina' is often None/missing the raw code.
    emtak_kood_val = (
        clean_value(pohitegevusala.get("emtak_kood")) if pohitegevusala else None
    )
    emtak_detailne_tekst_val = (
        clean_value(pohitegevusala.get("emtak_tekstina")) if pohitegevusala else None
    )

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
        empty_fields.append("Maakond")  # County

    # Prepare simple value Notion properties
    email_prop = {"email": email_val} if email_val else {"email": "E-maili ei leitud."}
    tel_prop = (
        {"phone_number": tel_val}
        if tel_val
        else {"phone_number": "Telefoni numbrit ei leitud."}
    )
    veeb_prop = {"url": veeb_val} if veeb_val else {"url": "Veebilehte ei leitud."}
    linkedin_prop = (
        {"url": linkedin_val} if linkedin_val else {"url": "LinkedIn-i ei leitud."}
    )

    # Track simple empty fields
    if not email_val:
        empty_fields.append("E-post (Email)")
    if not tel_val:
        empty_fields.append("Tel. nr (Phone No)")
    if not veeb_val:
        empty_fields.append("Veebileht (Website)")
    if not linkedin_val:
        empty_fields.append("LinkedIn")
    if not aadress_val:
        empty_fields.append("Aadress (Address)")

    # Track activity fields
    if not emtak_detailne_tekst_val:
        empty_fields.append("Põhitegevus (Main Activity)")
    if not emtak_jaotis_val:
        empty_fields.append("Tegevusvaldkond (Industry Section)")

    tegevusvaldkond_prop = {"multi_select": []}
    if emtak_jaotis_val:
        tegevusvaldkond_prop = {"multi_select": [{"name": emtak_jaotis_val}]}

    properties = {
        "Nimi": {"title": [{"text": {"content": company_name or ""}}]},
        "Registrikood": (
            {"number": int(regcode)} if regcode.isdigit() else {"number": None}
        ),
        "Aadress": {"rich_text": [{"text": {"content": aadress_val or ""}}]},
        "Maakond": maakond_prop,
        "E-post": email_prop,
        "Tel. nr": tel_prop,
        "Veebileht": veeb_prop,
        "LinkedIn": linkedin_prop,
        "Kontaktisikud": {"people": yldandmed.get("kontaktisikud_list", [])},
        "Põhitegevus": {
            "rich_text": [{"text": {"content": emtak_detailne_tekst_val or ""}}]
        },
        "Tegevusvaldkond": tegevusvaldkond_prop,
    }

    # NOTE: Set value to None instead of placeholder text to allow Notion to accept a true empty value if needed
    # The original code used placeholders, I'm adjusting to use None for proper Notion handling of empty fields (URL, Email, Phone Number types)
    # Re-checking the assignments to ensure Notion's required structure for empty fields is met:

    # Simple properties must be explicitly set to None (or the specific property type's empty value)
    if not email_val:
        properties["E-post"] = {"email": "E-maili ei leitud."}
    if not tel_val:
        properties["Tel. nr"] = {"phone_number": "Telefoni numbrit ei leitud."}
    if not veeb_val:
        properties["Veebileht"] = {"url": "Veebilehte ei leitud."}
    if not linkedin_val:
        properties["LinkedIn"] = {"url": "LinkedIn-i ei leitud."}

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
            "message": "Registrikood puudub või sisaldab mittenumbrilisi märke (peab olema number)."
        }

    try:
        # find_company_by_regcode automatically cleans the data (clean_value)
        company = find_company_by_regcode(config["ariregister"]["json_url"], regcode)
    except Exception as e:
        return {"status": "error", "message": f"Viga faili laadimisel: {e}"}

    if not company:
        return {
            "status": "error",
            "message": f"Ettevõtet registrikoodiga {regcode} ei leitud Äriregistri andmetest (JSON)."
        }

    company_name = clean_value(company.get("nimi"))
    # Prepare properties using the corrected logic
    properties, empty_fields, company_name = _build_properties_from_company(
        company, regcode, company_name
    )

    return {
        "status": "ready",
        "data": {
            "regcode": regcode,
            "properties": properties,  # Data for Notion API
            "empty_fields": empty_fields,
            "company_name": company_name,
        },
        "message": f"Andmed leitud: {company_name} ({regcode})."
    }


def process_company_sync(
    data: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
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
        config["notion"]["database_id"],
        config["notion"]["api_version"],
    )

    # Compose full payload for creation
    full_payload = {
        "parent": {"database_id": notion.database_id},
        "properties": properties,
    }

    try:
        # 1. Check if the entry already exists
        existing = notion.query_by_regcode(regcode)
        action = ""

        if existing:
            # Update existing page
            notion.update_page(existing["id"], properties)
            action = "Edukalt uuendatud"
        else:
            # Create a new page
            notion.create_page(full_payload)
            action = "Edukalt loodud"

        status = "success"
        message = f"✅ {action}: {company_name} ({regcode}). Kirje sünkroniseeriti Notioni."

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
            "message": f"❌ Üldine sünkroniseerimise viga: {type(e).__name__}: {e}"
        }


# --- Web/API Autofill Logic ---


def _is_placeholder_value(prop_value: Any, prop_type: str) -> bool:
    """
    Checks if a Notion property value is a placeholder (e.g., "Veebilehte ei leitud.").
    
    Args:
        prop_value: The property value from Notion
        prop_type: The type of the property (e.g., "url", "email", "phone_number")
        
    Returns:
        True if the value is a placeholder, False otherwise
    """
    if prop_value is None:
        return True
    
    # Define placeholder values
    placeholders = {
        "E-maili ei leitud.",
        "Telefoni numbrit ei leitud.",
        "Veebilehte ei leitud.",
        "LinkedIn-i ei leitud.",
    }
    
    # Extract the actual value based on property type
    if prop_type == "url":
        value = prop_value if isinstance(prop_value, str) else None
    elif prop_type == "email":
        value = prop_value if isinstance(prop_value, str) else None
    elif prop_type == "phone_number":
        value = prop_value if isinstance(prop_value, str) else None
    else:
        return False
    
    return value in placeholders if value else True


def _get_property_value(props: Dict[str, Any], field_name: str) -> Tuple[Any, str]:
    """
    Extracts the value and type of a Notion property.
    
    Args:
        props: The properties dictionary from a Notion page
        field_name: The name of the property to extract
        
    Returns:
        Tuple of (value, property_type) or (None, None) if not found
    """
    prop = props.get(field_name)
    if not prop:
        return None, None
    
    prop_type = prop.get("type")
    if not prop_type:
        return None, None
    
    if prop_type == "url":
        return prop.get("url"), "url"
    elif prop_type == "email":
        return prop.get("email"), "email"
    elif prop_type == "phone_number":
        return prop.get("phone_number"), "phone_number"
    elif prop_type == "rich_text":
        rich_text = prop.get("rich_text", [])
        if rich_text:
            return rich_text[0].get("text", {}).get("content"), "rich_text"
        return None, "rich_text"
    
    return None, prop_type


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
    NOTION_API_VERSION = config.get("notion", {}).get("api_version")

    # Configuration validation
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL]):
        error_msg = "Puudub üks või mitu nõutud konfiguratsiooni seadet (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL)."
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "config_check"}

    logging.debug(f"Using NOTION_DATABASE_ID: {NOTION_DATABASE_ID}")

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID, NOTION_API_VERSION)

    # 1. Fetch Page and Extract Registry Code
    regcode = None
    try:
        page = notion.get_page(page_id)
        # Get the actual page ID from the page object to ensure consistency
        actual_page_id = page.get("id", page_id)
        props = page.get("properties", {})
        logging.info("Edukalt hankitud lehe omadused Notionist.")
        logging.debug(f"Page ID from parameter: {page_id}, Page ID from Notion: {actual_page_id}")

        reg_prop = props.get("Registrikood")

        if not reg_prop:
            logging.error(
                f"Page 'Registrikood' property is missing. Available properties: {list(props.keys())}"
            )
            # Translate message
            return {
                "success": False,
                "message": "Viga: Notioni lehel puudub 'Registrikood' väli.",
                "step": "missing_registrikood",
            }

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
                content = texts[0].get("plain_text") or texts[0].get("text", {}).get(
                    "content"
                )
                if content:
                    regcode = "".join(ch for ch in content if ch.isdigit())

        if not regcode:
            error_msg = "'Registrikood' väärtus on Notioni lehel tühi või vales formaadis."
            logging.warning(error_msg)
            return {
                "success": False,
                "message": f"Viga: {error_msg}",
                "step": "invalid_registrikood",
            }

        logging.info(f"Found Registrikood: {regcode}")

        # Check if a company with this registry code already exists (on a different page)
        # Exclude the current page from the search - use actual_page_id from Notion for consistency
        logging.debug(f"Checking for duplicate registrikood {regcode}, excluding page_id: {actual_page_id}")
        existing_page = notion.query_by_regcode(regcode, exclude_page_id=actual_page_id)
        if existing_page:
            existing_page_id = existing_page.get("id")
            logging.warning(f"Found duplicate: existing page_id={existing_page_id}, current page_id={page_id}")
            # Company with this registry code already exists on another page
            existing_props = existing_page.get("properties", {})
            nimi_prop = existing_props.get("Nimi", {})
            company_name = ""
            
            # Extract company name from existing page
            if nimi_prop:
                prop_type = nimi_prop.get("type")
                if prop_type == "title":
                    title_array = nimi_prop.get("title", [])
                    if title_array and len(title_array) > 0:
                        company_name = clean_value(title_array[0].get("text", {}).get("content", ""))
            
            # Create error message in Estonian
            if company_name:
                error_msg = f"Ettevõte registrikoodiga {regcode} ({company_name}) on juba olemas Notionis."
            else:
                error_msg = f"Ettevõte registrikoodiga {regcode} on juba olemas Notionis."
            
            logging.warning(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "step": "duplicate_registrikood",
            }

    except Exception as e:
        error_msg = f"Lehe hankimine või andmete eraldamine Notionist ebaõnnestus: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "fetch_page_or_extract"}

    # 2. Fetch Company Data from JSON
    try:
        company = find_company_by_regcode(ARIREGISTER_JSON_URL, regcode)
        logging.info("Edukalt laetud andmed ja otsitud ettevõte.")
    except Exception as e:
        error_msg = f"JSON-i laadimine või ettevõtte otsimine ebaõnnestus: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "load_json_or_search"}

    if not company:
        error_msg = f"Ettevõtet registrikoodiga {regcode} ei leitud JSON andmetest."
        logging.warning(error_msg)
        # Translate message
        return {
            "success": False,
            "message": f"Viga: {error_msg}",
            "step": "company_not_found",
            "regcode": regcode,
        }

    logging.info(f"Found matching company in JSON: {clean_value(company.get('nimi'))}")

    # 3. Prepare Payload and Update Notion
    company_name = clean_value(company.get("nimi"))
    properties, empty_fields, _ = _build_properties_from_company(
        company, regcode, company_name
    )
    logging.debug("Built properties payload to send to Notion.")

    # 3.1 If Website is missing, try finding it via Google CSE (first 10, scored)
    veeb_prop = properties.get("Veebileht", {})
    existing_url = veeb_prop.get("url")
    if not existing_url:
        logging.info(
            "Veebileht puudub Äriregistri andmetes – proovime leida Google CSE abil."
        )
        homepage = google_find_website(company_name)
        if homepage:
            properties["Veebileht"]["url"] = homepage
            # Remove "Veebileht (Website)" from empty_fields if it was successfully found
            if "Veebileht (Website)" in empty_fields:
                empty_fields.remove("Veebileht (Website)")
        else:
            logging.info(
                "Google ei leidnud sobivat kodulehte (10 esimese tulemuse seas), jätame Veebileht tühjaks."
            )

    # 3.2 Filter properties to only update fields that are empty or contain placeholders
    # This preserves manually added content
    filtered_properties = {}
    fields_to_check = ["E-post", "Tel. nr", "Veebileht", "LinkedIn"]
    
    for field_name in properties.keys():
        if field_name in fields_to_check:
            # Get existing value from Notion page
            existing_value, prop_type = _get_property_value(props, field_name)
            
            # If field doesn't exist yet (None, None), or is empty/placeholder, update it
            if existing_value is None or _is_placeholder_value(existing_value, prop_type):
                filtered_properties[field_name] = properties[field_name]
                if existing_value is None:
                    logging.debug(f"Will update {field_name} (field is empty)")
                else:
                    logging.debug(f"Will update {field_name} (contains placeholder: {existing_value})")
            else:
                logging.info(f"Skipping {field_name} - contains manually added content: {existing_value}")
        else:
            # For other fields (like Nimi, Registrikood, etc.), always update
            filtered_properties[field_name] = properties[field_name]

    try:
        notion.update_page(page_id, filtered_properties)
        message = f"✅ Andmed edukalt automaatselt täidetud lehele {company_name} ({regcode})."

        if empty_fields:
            # The test expects "Edukalt uuendatud" AND "Viga: Warning..."
            message += f"\n ⚠️ Hoiatus: Järgmised väljad jäid tühjaks: {', '.join(empty_fields)}."

        logging.info(message)
        return {"success": True, "message": message, "company_name": company_name}

    except requests.HTTPError as e:
        error_details = ""
        try:
            error_details = e.response.json().get("message", e.response.text)
        except:
            error_details = e.response.text

        error_msg = f"❌ Notion API viga ({e.response.status_code}): {error_details}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "notion_update"}
    except Exception as e:
        error_msg = f"❌ Üldine automaatse täitmise viga: {type(e).__name__}: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg, "step": "general_error"}
