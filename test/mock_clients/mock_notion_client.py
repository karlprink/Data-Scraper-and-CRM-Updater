from unittest.mock import MagicMock


class MockNotionClient:
    def __init__(self, token, database_id, api_version):
        self.token = token
        self.database_id = database_id
        self.api_version = api_version
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": self.api_version,
        }
        self.get_page_called = MagicMock()
        self.create_page_called = MagicMock()
        self.update_page_called = MagicMock()
        self.query_by_regcode_called = MagicMock()

    def get_page(self, page_id):
        self.get_page_called(page_id)
        if page_id == "UC1_main":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 11043099}}
            }
        elif page_id == "UC1_alt1_missing":
            return {"properties": {"Registrikood": {"type": "number", "number": None}}}
        elif page_id == "UC1_alt1_invalid":
            return {"properties": {"Registrikood": {"type": "number", "number": 10}}}
        elif page_id == "UC1_alt2":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 17281782}}
            }
        elif page_id == "UC3_main":
            return {
                "properties": {
                    "Aadress": {None},  # This is a missing field that should be updated
                    "E-post": {"email": "info@ideelabor.ee"},
                    "Kontaktisikud": {
                        "people": ["TestPerson"]
                    },  # This value should not be updated
                    "LinkedIn": {
                        "url": "TestSite"
                    },  # This value that should not be updated
                    "Maakond": {"multi_select": [{"name": "Tartu maakond"}]},
                    "Nimi": {"title": [{"text": {"content": "OÜ Ideelabor"}}]},
                    "Põhitegevus": {
                        "rich_text": [{"text": {"content": "Programmeerimine"}}]
                    },
                    "Registrikood": {"type": "number", "number": 11043099},
                    "Tegevusvaldkond": {
                        "rich_text": [{"text": {"content": "Info ja side"}}]
                    },
                    "Tel. nr": {"phone_number": "+372 56208082"},
                    "Veebileht": {"url": "https://ideelabor.ee"},
                }
            }
        elif page_id == "UC3_alt1":
            return {
                "properties": {
                    "Nimi": {"title": [{"text": {"content": "Flowerflake OÜ"}}]},
                    "Registrikood": {"type": "number", "number": 99},
                    "Aadress": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": "Harju maakond, Rae vald, Järveküla, Ida põik 1"
                                }
                            }
                        ]
                    },
                    "Maakond": {"multi_select": [{"name": "Harju maakond"}]},
                    "E-post": {"email": "smaragda.sarana@gmail.com"},
                    "Tel. nr": {"phone_number": None},
                    "Veebileht": {"url": None},
                    "LinkedIn": {"url": None},
                    "Kontaktisikud": {"people": []},
                    "Põhitegevus": {
                        "rich_text": [{"text": {"content": "Programmeerimine"}}]
                    },
                    "Tegevusvaldkond": {
                        "rich_text": [{"text": {"content": "Info ja side"}}]
                    },
                }
            }
        elif page_id == "UC5_main":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 16359677}}
            }
        elif page_id == "UC5_alt1":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 16359677}}
            }
        elif page_id == "UC6_main":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 16359677}}
            }
        elif page_id == "UC6_alt1":
            return {
                "properties": {"Registrikood": {"type": "number", "number": 14543684}}
            }
        return {}

    def create_page(self, payload):
        self.create_page_called(payload)
        return {}

    def update_page(self, page_id, properties):
        self.update_page_called(page_id, properties)
        return {}

    def query_by_regcode(self, regcode):
        self.query_by_regcode_called(regcode)
        return {}
