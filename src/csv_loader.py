import pandas as pd
import math

def load_csv(url: str) -> pd.DataFrame:
    """Laeb CSV-faili URL-ist."""
    # Eeldab, et eraldaja on semikoolon (;) nagu näites kirjeldatud
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    return pd.read_csv(url, sep=";", storage_options=headers)

def find_company_by_regcode(df: pd.DataFrame, regcode: str) -> dict | None:
    """Leiab ettevõtte DataFrame'ist registrikoodi järgi."""
    row = df[df["ariregistri_kood"].astype(str) == str(regcode)]
    if not row.empty:
        # Tulemus teisendatakse sõnastikuks, et see oleks ligipääsetav
        return row.iloc[0].to_dict()
    return None

def clean_value(val):
    """
    Muudab pandas NaN või tühjad stringid None-ks ja trimib stringid.
    Notioni API jaoks on oluline, et tühjad väärtused oleksid None, mitte "".
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