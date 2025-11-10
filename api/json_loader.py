import json
import os
from datetime import datetime, timedelta
from .db import get_db_connection



def load_json(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Faili ei leitud: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_company_by_regcode(url: str, regcode: str):
    """Tagastab ettevõtte andmed andmebaasist (andmed eeldatakse alati ajakohased)."""

    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT data_json FROM companies WHERE regcode = %s"
    param = (regcode,)

    # SQLite puhul muuda query vastavalt
    if isinstance(regcode, str) and not hasattr(cur, "mogrify"):
        query = "SELECT data_json FROM companies WHERE regcode = ?"

    cur.execute(query, param)
    row = cur.fetchone()
    conn.close()

    if not row:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud.")
        return None

    data_json = row["data_json"] if isinstance(row, dict) else row[0]
    return json.loads(data_json)


def clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)
