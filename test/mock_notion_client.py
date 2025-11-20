from unittest.mock import MagicMock


class MockNotionClient:
    def __init__(self, token, database_id):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2021-03-31"
        }
        self.get_page_called = MagicMock()
        self.create_page_called = MagicMock()
        self.update_page_called = MagicMock()
        self.query_by_regcode_called = MagicMock()

    def get_page(self, page_id):
        self.get_page_called(page_id)
        if page_id == 'UC1_main':
            return {"properties": {"Registrikood": {"type": "number", "number": 11043099}}}
        elif page_id == 'UC1_alt1a':
            return {"properties": {"Registrikood": {"type": "number", "number": None}}}
        elif page_id == 'UC1_alt1b':
            return {"properties": {"Registrikood": {"type": "number", "number": 10}}}
        elif page_id == 'UC1_alt2':
            return {"properties": {"Registrikood": {"type": "number", "number": 17281782}}}
        elif page_id == 'UC3_main':
            return {"properties": {"Registrikood": {"type": "number", "number": 11043099}}}
        elif page_id == 'UC3_alt1':
            return {"properties": {"Registrikood": {"type": "number", "number": 99}}}
        elif page_id == 'UC5_main':
            return {"properties": {"Registrikood": {"type": "number", "number": 24}}}
        elif page_id == 'UC6_main':
            return {"properties": {"Registrikood": {"type": "number", "number": 16359677}}}
        elif page_id == 'UC6_alt1':
            return {"properties": {"Registrikood": {"type": "number", "number": 14543684}}}
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