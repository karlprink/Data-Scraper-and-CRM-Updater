import requests


class NotionClient:
    """Class for communicating with the Notion API."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def get_page(self, page_id: str):
        """Tagastab konkreetse lehe andmed (koos properties metaandmetega)."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        r = requests.get(url, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def create_page(self, payload: dict):
        """Adds a new page (entry) to the database."""
        url = "https://api.notion.com/v1/pages"
        r = requests.post(url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()

    def update_page(self, page_id: str, properties: dict):
        """Updates an existing page (entry)."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        r = requests.patch(url, headers=self.headers, json={"properties": properties})
        r.raise_for_status()
        return r.json()

    def query_by_regcode(self, regcode: str):
        """Searches for a page by registry code."""
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"

        # Proovi leida numbri järgi
        try:
            payload = {
                "filter": {
                    "property": "Registrikood",
                    "number": {"equals": int(regcode)}
                }
            }
            r = requests.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            res = r.json()
            if res.get("results"):
                return res["results"][0]
        except Exception:
            # Kui number-päring ebaõnnestub (nt väli on tekst), proovi tekstina
            pass

        # Proovi leida teksti järgi (igaks juhuks)
        try:
            payload = {
                "filter": {
                    "property": "Registrikood",
                    "rich_text": {"equals": str(regcode)}
                }
            }
            r = requests.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            res = r.json()
            if res.get("results"):
                return res["results"][0]
        except Exception:
            pass  # Viga tekstitüüpi välja pärimisel

        return None

    def get_company_regcode(self, page_id: str) -> str | None:
        """
        Loeb Notion lehelt registrikoodi property ('Registrikood').
        Tagastab registrikoodi kui stringi või None, kui seda ei leitud.
        """
        # 'import requests' on siit eemaldatud, kuna see on juba faili alguses

        url = f"https://api.notion.com/v1/pages/{page_id}"
        # headers on nüüd self.headers
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()

        # Otsi 'Registrikood' property
        props = data.get("properties", {})
        reg_prop = props.get("Registrikood")

        if not reg_prop:
            print("⚠️ Lehelt ei leitud 'Registrikood' property't.")
            return None

        # Registrikood võib olla Notion number-tüüpi või rich_text-tüüpi väli
        regcode = reg_prop.get("number")
        if regcode is None and "rich_text" in reg_prop:
            texts = reg_prop["rich_text"]
            if texts and "text" in texts[0]:
                regcode = texts[0]["text"]["content"]

        if regcode:
            print(f"✅ Leitud registrikood: {regcode}")
            return str(regcode).strip()  # Eemalda tühikud
        else:
            print("⚠️ Registrikood on tühi või puudub.")
            return None