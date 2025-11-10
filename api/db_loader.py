# db_loader.py
import json
import zipfile
import requests
import ijson
from datetime import datetime
from .db import get_db_connection, init_db, IS_POSTGRES


def load_to_db(json_zip_url: str):
    """Laeb Äriregistri ZIP-JSON andmed ja salvestab need andmebaasi."""
    print(f"⬇️  Laen andmed: {json_zip_url}")
    init_db()

    response = requests.get(json_zip_url, stream=True)
    response.raise_for_status()
    zip_path = "/tmp/ariregister.zip"
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    conn = get_db_connection()
    cur = conn.cursor()

    delete_sql = "DELETE FROM companies"
    insert_sql = """
        INSERT INTO companies (regcode, name, data_json, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (regcode) DO UPDATE
        SET name = EXCLUDED.name, data_json = EXCLUDED.data_json, updated_at = EXCLUDED.updated_at
    """ if IS_POSTGRES else """
        INSERT OR REPLACE INTO companies (regcode, name, data_json, updated_at)
        VALUES (?, ?, ?, ?)
    """

    cur.execute(delete_sql)
    conn.commit()

    with zipfile.ZipFile(zip_path) as z:
        json_filename = z.namelist()[0]
        with z.open(json_filename) as f:
            count = 0
            for company in ijson.items(f, "item"):
                regcode = str(company.get("ariregistri_kood"))
                if not regcode:
                    continue
                name = company.get("nimi", "")
                data_json = json.dumps(company, ensure_ascii=False)
                cur.execute(insert_sql, (regcode, name, data_json, datetime.utcnow().isoformat()))
                count += 1
                if count % 10000 == 0:
                    conn.commit()
                    print(f"  ... {count} ettevõtet lisatud")
            conn.commit()
    conn.close()
    print("✅ Andmebaasi laadimine valmis.")
