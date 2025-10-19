import os

import streamlit as st
import pandas as pd
import math
import requests
from typing import Tuple, List, Dict, Any

# IMPORDI TEGELIK KONFIGURATSIOONI LOADER
from config_loader import load_config

# --- CONFIGURATION & ENV SETUP EEMALDATUD ---
# Konfiguratsioon laaditakse nüüd load_config() funktsiooni kaudu,
# mis loeb config.yaml faili ja keskkonnamuutujaid.

# --- CSV LOADER UTILITY FUNCTIONS (REAL) ---

import os
import pandas as pd
import streamlit as st

import os
import streamlit as st
import pandas as pd

def load_csv():
    csv_path  = "/mnt/c/Users/prink/Videos/3.aasta/tarkvaraprojekt/Data-Scraper-and-CRM-Updater/data/ettevotja_rekvisiidid__lihtandmed.csv"


    st.write("📁 Kontrollin CSV teed:", csv_path)
    st.write("Kas eksisteerib:", os.path.exists(csv_path))

    if not os.path.exists(csv_path):
        st.error(f"❌ Faili ei leitud: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path, sep=";")
        st.success(f"✅ CSV leitud ja loetud. Ridu: {len(df)}")
        return df
    except Exception as e:
        st.error(f"❌ CSV lugemisel tekkis viga: {e}")
        return None




def find_company_by_regcode(df: pd.DataFrame, regcode: str) -> dict | None:
    """Finds a company from the DataFrame by registry code."""
    # Ensure registry code column is string type for matching
    row = df[df["ariregistri_kood"].astype(str) == str(regcode)]
    if not row.empty:
        return row.iloc[0].to_dict()
    return None


def clean_value(val):
    """
    Converts pandas NaN or empty strings to None and strips strings.
    For the Notion API, it's important that empty values are None, not "".
    """
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, str):
        val = val.strip()
        if val == "":
            return None
    return val


# --- NOTION API CLIENT (REAL) ---

class NotionClient:
    """Class for communicating with the Notion API (REAL)."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        self.base_url = "https://api.notion.com/v1"

    def _make_request(self, method: str, path: str, json: dict = None):
        """Generic request handler."""
        url = f"{self.base_url}/{path}"
        r = requests.request(method, url, headers=self.headers, json=json)
        r.raise_for_status()
        return r.json()

    def get_page(self, page_id: str):
        """Returns specific page data (including properties metadata)."""
        return self._make_request("GET", f"pages/{page_id}")

    def create_page(self, payload: dict):
        """Adds a new page (entry) to the database."""
        return self._make_request("POST", "pages", json=payload)

    def update_page(self, page_id: str, properties: dict):
        """Updates an existing page (entry)."""
        return self._make_request("PATCH", f"pages/{page_id}", json={"properties": properties})

    def query_by_regcode(self, regcode: str):
        """Searches for a page by registry code."""
        # Notioni number-välja puhul peab olema täisarv
        try:
            regcode_num = int(regcode)
        except ValueError:
            raise ValueError("Registrikood peab olema täisarv.")

        path = f"databases/{self.database_id}/query"

        payload = {
            "filter": {
                "property": "Registrikood",
                "number": {"equals": regcode_num}
            }
        }

        res = self._make_request("POST", path, json=payload)

        if res.get("results"):
            return res["results"][0]
        return None


# --- SYNC PREPARATION HELPERS (No Change) ---

def _prepare_notion_properties(company: dict, regcode: str) -> Tuple[Dict[str, Any], List[str], str]:
    """
    Cleans company data and aggregates it into the Notion Properties format,
    tracking fields that remain empty.
    Returns: (properties: dict, empty_fields: list, company_name: str)
    """

    company_name = clean_value(company.get('nimi')) or f"Company ({regcode})"

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


# --- CORE SYNC FUNCTIONS (Updated for real API calls) ---

def load_company_data(regcode: str, config: dict) -> dict:
    """
    Loads company data from the fixed local CSV file and prepares Notion structures.
    Returns a dictionary: {"status": str, "data": dict/None, "message": str}
    """
    if not regcode or not str(regcode).isdigit():
        return {
            "status": "error",
            "message": "Registration code is missing or contains non-numeric characters (must be a number)."
        }

    try:
        df = load_csv()
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ CSV loading error: {type(e).__name__}: {e}"
        }

    company = find_company_by_regcode(df, regcode)

    if not company:
        return {
            "status": "error",
            "message": f"Company with registration code {regcode} not found in the Business Register data (CSV)."
        }

    # Prepares Notion properties (same as before)
    properties, empty_fields, company_name = _prepare_notion_properties(company, regcode)

    flat_data = {
        "Registrikood": str(regcode),
        "Nimi": company_name,
        "Aadress": clean_value(company.get("asukoht_ettevotja_aadressis")) or "",
        "Maakond": properties["Maakond"]["multi_select"][0]["name"] if properties["Maakond"]["multi_select"] else "",
        "E-post": clean_value(company.get("email")) or "",
        "Tel. nr": clean_value(company.get("telefon")) or "",
        "Veebileht": clean_value(company.get("teabesysteemi_link")) or "",
        "LinkedIn": clean_value(company.get("linkedin")) or "",
        "Tegevusvaldkond": clean_value(company.get("tegevusvaldkond")) or "",
        "Põhitegevus": clean_value(company.get("pohitegevus")) or "",
    }

    return {
        "status": "ready",
        "data": {
            "regcode": regcode,
            "flat_data": flat_data,
            "properties_template": properties,
            "empty_fields": empty_fields,
            "company_name": company_name,
        },
        "message": f"Data found: {company_name} ({regcode}). Now modify and sync."
    }

def _reconstruct_notion_properties(flat_data: dict) -> Tuple[Dict[str, Any], List[str]]:
    """
    Converts the flat dictionary edited by the user back into the nested Notion properties
    structure required by the API. (No Change)
    """
    properties = {}
    empty_fields = []

    # 1. Title/Text properties
    name = flat_data.get("Nimi")
    address = flat_data.get("Aadress")
    tegevusvaldkond = flat_data.get("Tegevusvaldkond")
    pohitegevus = flat_data.get("Põhitegevus")

    properties["Nimi"] = {"title": [{"text": {"content": name or ""}}]}

    # 2. Number (Registrikood)
    regcode = flat_data.get("Registrikood")
    try:
        properties["Registrikood"] = {"number": int(regcode)}
    except (ValueError, TypeError):
        properties["Registrikood"] = {"number": None}

    # 3. Rich Text (Aadress, Tegevusvaldkond, Põhitegevus)
    properties["Aadress"] = {"rich_text": [{"text": {"content": address or ""}}]}
    properties["Tegevusvaldkond"] = {"rich_text": [{"text": {"content": tegevusvaldkond or ""}}]}
    properties["Põhitegevus"] = {"rich_text": [{"text": {"content": pohitegevus or ""}}]}

    # 4. Multi-Select (Maakond)
    maakond = flat_data.get("Maakond")
    properties["Maakond"] = {"multi_select": [{"name": maakond}]} if maakond else {"multi_select": []}

    # 5. Email, Phone, URL
    email = flat_data.get("E-post")
    phone = flat_data.get("Tel. nr")
    website = flat_data.get("Veebileht")
    linkedin = flat_data.get("LinkedIn")

    properties["E-post"] = {"email": email} if email else {"email": None}
    properties["Tel. nr"] = {"phone_number": phone} if phone else {"phone_number": None}
    properties["Veebileht"] = {"url": website} if website else {"url": None}
    properties["LinkedIn"] = {"url": linkedin} if linkedin else {"url": None}

    # 6. Check for empty fields for notification
    for key, value in flat_data.items():
        if not value and key not in ["Registrikood", "Nimi"]:
            empty_fields.append(key)

    properties["Kontaktisikud"] = {"people": []}

    return properties, empty_fields


def process_company_sync(data: dict, config: dict) -> dict:
    """
    Performs Notion API synchronization (real API call).
    """

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
            # Uuendamine
            notion.update_page(existing["id"], properties)
            action = "Updated"
        else:
            # Lisamine
            notion.create_page(full_payload)
            action = "Created"

        status = "success"
        message = f"✅ Successfully {action}: {company_name} ({regcode}). Entry processed in Notion."

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
            "message": f"❌ Notion API Error ({e.response.status_code}): {error_details}. Check Notion API Key and Database ID."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ General Synchronization Error: {type(e).__name__}: {e}"
        }


def autofill_page_by_page_id(page_id: str, config: dict):
    """
    Reads the Registrikood property from the given Notion page and fills the remaining fields (REAL).
    """
    st.info(f"Attempting autofill for Notion Page ID: {page_id}")

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"],
    )

    try:
        # 1. Read page properties
        page = notion.get_page(page_id)
        props = page.get("properties", {})

        # 2. Extract regcode
        regcode = None
        reg_prop = props.get("Registrikood")

        if reg_prop and reg_prop.get("type") == "number" and reg_prop.get("number") is not None:
            regcode = str(int(reg_prop["number"]))

        if not regcode:
            st.error(
                "❌ 'Registrikood' is empty or in the wrong format on this Notion page (must be a Number property).")
            return

        # 3. Load company data from CSV
        df = load_csv(config["ariregister"]["csv_url"])
        company = find_company_by_regcode(df, regcode)

        if not company:
            st.warning(f"⚠️ Company with registration code {regcode} not found in CSV data. Cannot autofill.")
            return

        # 4. Prepare Notion properties from CSV data
        properties, empty_fields, company_name = _prepare_notion_properties(company, regcode)

        # 5. Update the same page
        notion.update_page(page_id, properties)

        message = f"✅ Successfully autofilled page: {company_name} ({regcode})"
        if empty_fields:
            message += f". Warning: {', '.join(empty_fields)} were left empty."

        st.success(message)

    except requests.HTTPError as e:
        error_details = ""
        try:
            error_details = e.response.json().get("message", e.response.text)
        except:
            error_details = e.response.text
        st.error(
            f"❌ Notion API Error ({e.response.status_code}): {error_details}. Check Page ID and database connection.")

    except Exception as e:
        st.error(f"❌ General Error during autofill: {type(e).__name__}: {e}")


# -------------------------------------------------------------
# UI Display Logic (No Change)
# -------------------------------------------------------------

def sync_form_to_notion(data_to_sync):
    """Handles the final synchronization after form submission."""
    # Lae konfiguratsioon igal sünkroonimisel, et tagada värsked keskkonnamuutujad
    config = load_config()
    st.markdown("---")

    # 1. Reconstruct nested properties from the flat, edited data
    updated_notion_properties, empty_fields = _reconstruct_notion_properties(data_to_sync["flat_data"])

    # 2. Re-assemble the full data payload needed by process_company_sync
    full_sync_data = {
        "regcode": data_to_sync["flat_data"].get("Registrikood"),
        "properties": updated_notion_properties,
        "empty_fields": empty_fields,
        "company_name": data_to_sync["flat_data"].get("Nimi"),
    }

    with st.spinner('Starting synchronization with Notion...'):
        sync_result = process_company_sync(full_sync_data, config)

    if sync_result["status"] == "success":
        st.balloons()
        st.success(sync_result["message"])
    elif sync_result["status"] == "warning":
        st.warning(sync_result["message"])
    else:
        st.error(sync_result["message"])

    # Clear preview/form data after sync
    st.session_state.data_to_sync = None
    st.session_state.sync_mode = None


def display_editable_form(data):
    """Displays company data in an editable Streamlit form."""
    st.subheader("Edit Company Data Before Sync (Muuda andmeid enne sünkroonimist)")
    st.info(
        "Modify any values below. Empty fields will be marked as empty in Notion. Click 'Fill and Sync' to proceed.")

    flat_data = data["flat_data"]

    with st.form(key='sync_data_form'):

        updated_data = {}

        fields_to_display = [
            ("Registrikood", flat_data.get("Registrikood"), True),
            ("Nimi", flat_data.get("Nimi"), True),
            ("Aadress", flat_data.get("Aadress"), False),
            ("Maakond", flat_data.get("Maakond"), False),
            ("E-post", flat_data.get("E-post"), False),
            ("Tel. nr", flat_data.get("Tel. nr"), False),
            ("Veebileht", flat_data.get("Veebileht"), False),
            ("LinkedIn", flat_data.get("LinkedIn"), False),
            ("Tegevusvaldkond", flat_data.get("Tegevusvaldkond"), False),
            ("Põhitegevus", flat_data.get("Põhitegevus"), False)
        ]

        for key, value, is_mandatory in fields_to_display:
            label = f"{key} *" if is_mandatory else key

            if key == "Maakond":
                available_counties = ["Harjumaa", "Tartumaa", "Pärnumaa", "Ida-Virumaa", "Other", ""]
                # Ensure the default value from loaded data is in the options list
                if value not in available_counties and value:
                    available_counties.insert(0, value)

                default_index = available_counties.index(value) if value in available_counties else (
                    available_counties.index("") if "" in available_counties else 0)

                updated_data[key] = st.selectbox(
                    label,
                    options=available_counties,
                    index=default_index,
                    key=f'form_{key}'
                )
            else:
                updated_data[key] = st.text_input(
                    label,
                    value=value if value is not None else "",
                    key=f'form_{key}'
                )

        st.markdown("---")

        col_sync, col_cancel = st.columns(2)

        sync_submitted = col_sync.form_submit_button(
            label="Fill and Sync (Täida ja Sünkrooni)",
            type="primary"
        )
        cancel_clicked = col_cancel.form_submit_button(
            label="Cancel (Katkesta)"
        )

        if sync_submitted:
            if not updated_data.get("Registrikood") or not updated_data.get("Nimi"):
                st.error("ERROR: Registration Code and Company Name are mandatory fields.")
            else:
                st.session_state.data_to_sync["flat_data"] = updated_data
                st.session_state.sync_triggered = True
                st.rerun()

        if cancel_clicked:
            st.session_state.data_to_sync = None
            st.session_state.sync_mode = None
            st.warning("Synchronization cancelled.")
            st.rerun()


def main():
    """Main part of the Streamlit application."""
    st.set_page_config(page_title="Business Register Synchronizer to Notion", layout="centered")
    st.title("🇪🇪 Business Register Data Synchronization to Notion")
    st.caption("Automated tool for fetching company data and loading it into a Notion database.")

    # Load configuration (one-time operation). This will raise FileNotFoundError
    # if 'config.yaml' is missing, halting the app execution.
    try:
        config = load_config()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop() # Stop further execution if configuration fails

    tab1, tab2 = st.tabs(["New Sync (Registration Code)", "Autofill Existing (Page ID)"])

    if 'sync_triggered' in st.session_state and st.session_state.sync_triggered:
        sync_form_to_notion(st.session_state.data_to_sync)
        st.session_state.sync_triggered = False

    with tab1:
        st.header("1. Create New Entry by Registration Code")

        if 'data_to_sync' not in st.session_state or st.session_state.data_to_sync is None:

            regcode = st.text_input("Enter Company Registration Code (e.g., 10000000):", key='regcode_input')

            if st.button("Load Data for Preview", type="primary", key='load_btn'):
                if not regcode:
                    st.error("Please enter a registration code.")
                    return

                with st.spinner('Searching for data in the Business Register...'):
                    load_result = load_company_data(regcode.strip(), config)

                if load_result["status"] == "error":
                    st.error(load_result["message"])
                else:
                    st.session_state.data_to_sync = load_result["data"]
                    st.session_state.sync_mode = 'new'
                    st.success(load_result["message"])
                    st.rerun()

        if 'data_to_sync' in st.session_state and st.session_state.sync_mode == 'new' and st.session_state.data_to_sync is not None:
            display_editable_form(st.session_state.data_to_sync)

    with tab2:
        st.header("2. Autofill Existing Page")
        st.markdown("This mode supplements an existing Notion page that already has the **Registrikood** field.")
        st.info(
            "The Notion page must exist in the configured database and have a **Number** property named `Registrikood` with a value set.")

        page_id = st.text_input("Enter Notion Page ID (32-character string):", key='page_id_input')

        if st.button("Start Autofill", key='autofill_btn'):
            if not page_id:
                st.error("Please enter a Notion Page ID.")
                return

            with st.spinner('Supplementing Notion page... (Calling Notion API)'):
                autofill_page_by_page_id(page_id.strip(), config)


if __name__ == "__main__":
    main()
