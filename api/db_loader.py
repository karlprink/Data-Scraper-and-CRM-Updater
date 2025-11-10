# api/db_loader.py (PARANDATUD)
import json
import zipfile
import requests
import ijson
from datetime import datetime
from .db import get_db_connection, init_db, IS_POSTGRES
from typing import Dict, Any


def _extract_notion_data(company: Dict[str, Any]) -> Dict[str, Any]:
    """Ekstraheerib Äriregistri andmetest ainult Notioni jaoks vajalikud väljad."""

    yldandmed = company.get('yldandmed', {})

    # Kontaktandmed
    email_val = None
    tel_val = None
    veeb_val = None
    sidevahendid = yldandmed.get('sidevahendid', [])
    for item in sidevahendid:
        sisu = str(item.get('sisu', '')).strip()
        if not sisu: continue
        liik = item.get('liik')
        if liik == "EMAIL":
            email_val = sisu
        elif liik in ("TEL", "MOB"):
            if not tel_val: tel_val = sisu
        elif liik == "WWW":
            veeb_val = sisu

    # Aadress
    aadressid = yldandmed.get('aadressid', [])
    aadress_täis_val = (
        str(aadressid[0].get('aadress_ads__ads_normaliseeritud_taisaadress', '')).strip()
        if aadressid else None
    )

    # Tegevusala (EMTAK kood)
    pohitegevusala = next(
        (ta for ta in yldandmed.get('teatatud_tegevusalad', []) if ta.get('on_pohitegevusala') is True),
        None
    )
    emtak_kood = str(pohitegevusala.get("emtak_kood", '')).strip() if pohitegevusala else None
    emtak_tekst = str(pohitegevusala.get("emtak_tekstina", '')).strip() if pohitegevusala else None

    # Andmed on salvestatud kujul, mida sync.py (täpsemalt _build_properties_from_company) ootab
    return {
        "regcode": str(company.get("ariregistri_kood", '')).strip(),
        "nimi": str(company.get("nimi", '')).strip(),
        "linkedin": str(company.get("linkedin", '')).strip(),
        "emtak_kood": emtak_kood,
        "emtak_tekst": emtak_tekst,
        "kontakt": {
            "email": email_val,
            "telefon": tel_val,
            "veebileht": veeb_val,
        },
        "aadress": aadress_täis_val
    }


def load_to_db(json_zip_url: str):
    """Laeb Äriregistri ZIP-JSON andmed, ekstraheerib vajaliku ja salvestab andmebaasi."""
    print(f"⬇️  Laen andmed: {json_zip_url}")
    init_db()  # Tagab tabeli olemasolu

    # ... (faili allalaadimise loogika on sama)
    response = requests.get(json_zip_url, stream=True)
    response.raise_for_status()
    zip_path = "/tmp/ariregister.zip"
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    conn = get_db_connection()
    cur = conn.cursor()

    # Peame muutma insert-päringut, et see kasutaks uut, väiksemat JSON-objekti
    delete_sql = "DELETE FROM companies"
    insert_sql = """
                 INSERT INTO companies (regcode, name, data_json, updated_at)
                 VALUES (%s, %s, %s, %s) ON CONFLICT (regcode) DO \
                 UPDATE \
                     SET name = EXCLUDED.name, data_json = EXCLUDED.data_json, updated_at = EXCLUDED.updated_at \
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

                # UUS LOOGIKA: Ekstraheeri ainult vajalik
                extracted_data = _extract_notion_data(company)

                name = extracted_data.get("nimi", "")
                data_json = json.dumps(extracted_data, ensure_ascii=False)

                cur.execute(insert_sql, (regcode, name, data_json, datetime.utcnow().isoformat()))
                count += 1
                if count % 10000 == 0:
                    conn.commit()
                    print(f"  ... {count} ettevõtet lisatud (optimeeritud andmed)")
            conn.commit()
    conn.close()
    print("✅ Andmebaasi laadimine valmis (optimeeritud andmed).")