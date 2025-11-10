import json
import os
from datetime import datetime, timedelta
from .db import get_db_connection, IS_POSTGRES  # Lisatud IS_POSTGRES


def load_json(file_path):
    # See funktsioon on nüüd kasutu autofill loogika jaoks,
    # aga võib alles jääda muudeks otstarveteks.
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Faili ei leitud: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_company_by_regcode(regcode: str):
    """Tagastab ettevõtte andmed andmebaasist."""

    conn = get_db_connection()
    cur = conn.cursor()

    # Parameetrite vorming sõltub DB tüübist
    if IS_POSTGRES:
        query = "SELECT data_json FROM companies WHERE regcode = %s"
        param = (regcode,)
    else:  # SQLite
        query = "SELECT data_json FROM companies WHERE regcode = ?"
        param = (regcode,)

    cur.execute(query, param)
    row = cur.fetchone()
    conn.close()

    if not row:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud.")
        return None

    # row['data_json'] (Postgres RealDictCursor) või row[0] (SQLite)
    data_json = row["data_json"] if isinstance(row, dict) else row[0]
    return json.loads(data_json)


def clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)