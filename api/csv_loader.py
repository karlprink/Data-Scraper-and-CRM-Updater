import pandas as pd
import math
import os
import time
import requests
import io
from datetime import timedelta

CACHE_FILE_PATH = "/tmp/ariregister_data.csv"
CACHE_EXPIRATION = timedelta(hours=24)


def load_csv(url: str) -> pd.DataFrame:
    """
    Loads a CSV file from a URL, using a local cache to avoid
    re-downloading the data within a 24-hour period.
    """
    # Check if a valid cache file exists
    if os.path.exists(CACHE_FILE_PATH):
        file_mod_time = os.path.getmtime(CACHE_FILE_PATH)
        if (time.time() - file_mod_time) < CACHE_EXPIRATION.total_seconds():
            print("CACHE HIT: Loading data from local cache.")
            return pd.read_csv(CACHE_FILE_PATH, sep=";")

    print("CACHE MISS: Downloading fresh data from the URL.")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Read CSV from the response content
    df = pd.read_csv(io.StringIO(response.text), sep=";")
    
    df.to_csv(CACHE_FILE_PATH, sep=";", index=False)
    print(f"CACHE UPDATED: Saved new data to {CACHE_FILE_PATH}")
    
    return df


def find_company_by_regcode(df: pd.DataFrame, regcode: str) -> dict | None:
    """Leiab ettevõtte DataFrame'ist registrikoodi järgi."""

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
