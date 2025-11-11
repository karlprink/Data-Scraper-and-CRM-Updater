import os
import time
import json
import zipfile
import requests
import ijson
import math
from datetime import timedelta
from typing import Optional, Dict, Any

# --- Configuration ---
CACHE_DIR = "/tmp/cache"
CACHE_FILE_PATH = os.path.join(CACHE_DIR, "ariregister_data.zip")
CACHE_EXPIRATION = timedelta(hours=24)

# --- Core Utility Functions ---

def get_result_cache_path(target_code: str) -> str:
    """
    Generates the cache file path for a specific registry code.

    Args:
        target_code: The company's registry code (e.g., '12345678').

    Returns:
        The full path to the result cache file.
    """
    return os.path.join(CACHE_DIR, f"cache_{target_code}.json")


def clean_value(val: Any) -> Optional[Any]:
    """
    Cleans values for Notion API by converting empty strings, None, and NaN
    floats to None.

    Args:
        val: The value to clean.

    Returns:
        The cleaned value or None if it should be treated as empty.
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


def load_json(url: str, target_code: str) -> Optional[Dict[str, Any]]:
    """
    Downloads the Estonian Business Register (Äriregister) data ZIP file,
    caches it, extracts the JSON, and searches for a specific company by its
    registry code using ijson for memory efficiency.

    The function first checks the result cache for the specific company.
    If not found or expired, it checks the ZIP file cache.
    If the ZIP file cache is expired, it downloads a new one.

    Args:
        url: The URL to the ZIP file containing the JSON data.
        target_code: The registry code of the company to search for.

    Returns:
        A dictionary containing the company data if found, otherwise None.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    result_cache_file = get_result_cache_path(target_code)

    # 1. Check result cache for specific company
    if os.path.exists(result_cache_file):
        file_mod_time = os.path.getmtime(result_cache_file)
        if (time.time() - file_mod_time) < CACHE_EXPIRATION.total_seconds():
            print(f"CACHE HIT: Found data for registry code {target_code} in cache.")
            with open(result_cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    # 2. Check/Download main ZIP file
    if (not os.path.exists(CACHE_FILE_PATH)) or (
            time.time() - os.path.getmtime(CACHE_FILE_PATH)
    ) > CACHE_EXPIRATION.total_seconds():
        print(f"CACHE MISS: Downloading new ZIP file: {url}")
        headers = {"User-Agent": "Mozilla/5.0"}

        # Prevents loading the whole file into memory
        with requests.get(url.strip(), headers=headers, stream=True) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
            with open(CACHE_FILE_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
        print("ZIP file downloaded and saved to cache.")
    else:
        print("Using existing ZIP cache file.")

    # 3. Search inside the JSON file using ijson
    with zipfile.ZipFile(CACHE_FILE_PATH) as z:
        # Assuming the JSON file is the first (and only) file in the ZIP
        json_filename = z.namelist()[0]
        with z.open(json_filename) as f:
            print(f"Streaming JSON from ZIP ({json_filename}) and searching for {target_code}...")

            try:
                for obj in ijson.items(f, "item"):
                    # The 'ariregistri_kood' is the registry code in the JSON structure
                    if str(obj.get("ariregistri_kood")) == str(target_code):
                        print(f"✅ Company {target_code} found, saving result to cache.")
                        with open(result_cache_file, "w", encoding="utf-8") as out:
                            json.dump(obj, out, ensure_ascii=False, indent=2)
                        return obj
            except ijson.common.IncompleteJSONError:
                print("Warning: JSON parsing ended prematurely (possible ZIP file error).")

    print(f"⚠️ Company with registry code {target_code} not found in the dataset.")
    return None


def find_company_by_regcode(url: str, regcode: str) -> Optional[Dict[str, Any]]:
    """
    Combines JSON ZIP loading and record lookup into a single function.
    Cleans the resulting data before returning.

    Args:
        url: The URL to the Business Register JSON ZIP file.
        regcode: The company's registry code to search for.

    Returns:
        The company record as a cleaned dictionary, or None if not found.
    """
    data = load_json(url, regcode)
    if data:
        # Clean all values in the dictionary
        return {k: clean_value(v) for k, v in data.items()}
    return None