import os
import time
import json
import zipfile
import requests
import ijson
import math
from datetime import timedelta

CACHE_FILE_PATH = "cache/ariregister_data.zip"
CACHE_EXPIRATION = timedelta(hours=24)
CACHE_DIR = "cache"


def get_result_cache_path(target_code: str) -> str:
    """Loob vahemälu failitee konkreetsele registrikoodile."""
    return os.path.join(CACHE_DIR, f"cache_{target_code}.json")


def load_json(url: str, target_code: str) -> dict | None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    result_cache_file = get_result_cache_path(target_code)

    if os.path.exists(result_cache_file):
        file_mod_time = os.path.getmtime(result_cache_file)
        if (time.time() - file_mod_time) < CACHE_EXPIRATION.total_seconds():
            print(f"CACHE HIT: Leitud vahemällust andmed registrikoodile {target_code}.")
            with open(result_cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    # download zip or used already existing from cache
    if (not os.path.exists(CACHE_FILE_PATH)) or (
            time.time() - os.path.getmtime(CACHE_FILE_PATH)
    ) > CACHE_EXPIRATION.total_seconds():
        print(f"CACHE MISS: Laen alla uue ZIP-faili: {url}")
        headers = {"User-Agent": "Mozilla/5.0"}

        # prevents loading the whole file into memory
        with requests.get(url.strip(), headers=headers, stream=True) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
            with open(CACHE_FILE_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB tükid
                    f.write(chunk)
        print("ZIP file allalaaditud ja cache'i salvestatud.")
    else:
        print("Kasutan olemasolevat ZIP cache faili.")

    with zipfile.ZipFile(CACHE_FILE_PATH) as z:
        json_filename = z.namelist()[0]
        with z.open(json_filename) as f:
            print(f"Edastan JSON-i ZIP-i seest ({json_filename}) ja otsin {target_code} ...")

            try:
                for obj in ijson.items(f, "item"):
                    if str(obj.get("ariregistri_kood")) == str(target_code):
                        print(f"✅ Ettevõte {target_code} leitud, salvestan tulemuse cache'i.")
                        with open(result_cache_file, "w", encoding="utf-8") as out:
                            json.dump(obj, out, ensure_ascii=False, indent=2)
                        return obj
            except ijson.common.IncompleteJSONError:
                print("Hoiatus: JSON-i parsimine lõppes enneaegselt (võib olla ZIP-i viga).")

    print(f"⚠️ Ettevõtet registrikoodiga {target_code} ei leitud andmestikus.")
    return None

def clean_value(val):
    """Puhastab väärtused Notion API jaoks."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, str):
        val = val.strip()
        if val == "":
            return None
    return val


def find_company_by_regcode(url: str, regcode: str) -> dict | None:
    """
    Ühendab JSON ZIP laadimise ja kirje otsingu ühte funktsiooni.
    Tagastab ettevõtte kirje dict-formaadis või None kui ei leitud.
    """
    data = load_json(url, regcode)
    if data:
        return {k: clean_value(v) for k, v in data.items()}
    return None