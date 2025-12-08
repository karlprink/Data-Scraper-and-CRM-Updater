from unittest.mock import MagicMock


class MockCompanyWebsiteClient:

    def __init__(self):
        self.get_company_called = MagicMock()

    def get_company(self, company_id):
        pass
