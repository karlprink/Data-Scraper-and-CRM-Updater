# csv_loader.py
import pandas as pd
import math

def load_csv(url: str) -> pd.DataFrame:
    """Loads CSV file from URL."""
    # Assumes separator is semicolon (;) as described in the example
    return pd.read_csv(url, sep=";")

def find_company_by_regcode(df: pd.DataFrame, regcode: str) -> dict | None:
    """Finds a company from the DataFrame by registry code."""
    row = df[df["ariregistri_kood"].astype(str) == str(regcode)]
    if not row.empty:
        # The result is converted to a dictionary for accessibility
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