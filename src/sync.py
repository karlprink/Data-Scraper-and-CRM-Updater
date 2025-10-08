from .csv_loader import load_csv, find_company_by_regcode
from .notion_client import NotionClient

def sync_company(regcode: str, config: dict):
    df = load_csv(config["ariregister"]["csv_url"])
    company = find_company_by_regcode(df, regcode)

    if not company:
        print(f"⚠️ Ettevõtet registrikoodiga {regcode} ei leitud.")
        return

    notion = NotionClient(
        config["notion"]["token"],
        config["notion"]["database_id"]
    )

    # NB! eeldame, et CSV sisaldab vähemalt: nimi, registrikood, aadress, maakond
    # ülejäänud (email, tel, veeb, linkedin jne) võid kas CSV-st või muust allikast täiendada

    properties = {
        "Nimi": {
            "title": [{"text": {"content": company.get("nimi", "-")}}]
        },
        "Registrikood": {
            "number": int(company.get("registrikood", 0))
        },
        "Aadress": {
            "rich_text": [{"text": {"content": company.get("aadress", "-")}}]
        },
        "Maakond": {
            "multi_select": [{"name": company.get("maakond", "-")}]
        },
        "E-post": {
            "email": company.get("email", None)
        },
        "Tel. nr": {
            "phone_number": company.get("telefon", None)
        },
        "Veebileht": {
            "url": company.get("veeb", None)
        },
        "LinkedIn": {
            "url": company.get("linkedin", None)
        },
        "Kontaktisikud": {
            "people": []   
        },
        "Tegevusvaldkond": {
            "rich_text": [{"text": {"content": company.get("tegevusvaldkond", "-")}}]
        },
        "Põhitegevus": {
            "rich_text": [{"text": {"content": company.get("pohitegevus", "-")}}]
        }
    }

    existing = notion.query_by_regcode(regcode)
    if existing:
        page_id = existing["id"]
        notion.update_page(page_id, properties)
        print(f"✅ Uuendatud: {company['nimi']} ({regcode})")
    else:
        notion.create_page(properties)
        print(f"➕ Lisatud: {company['nimi']} ({regcode})")
