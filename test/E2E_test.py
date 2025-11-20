import logging
import os
import sys
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import api.autofill as autofill
import api.sync as sync
from api import json_loader
from api.autofill import AUTO_CLOSE_HTML
from test.mock_notion_client import MockNotionClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_for_autoclose(response):
    assert response.status_code == 200
    assert response.text == AUTO_CLOSE_HTML
    assert response.mimetype == "text/html"



@pytest.fixture()
def mock_cache_dir(monkeypatch):
    monkeypatch.setattr(json_loader, "CACHE_DIR", "test/mock_cache")
    monkeypatch.setattr(json_loader, "CACHE_FILE_PATH", "test/mock_cache/ariregister_data.zip")
    monkeypatch.setattr(json_loader, "CACHE_EXPIRATION", timedelta(hours=24))

@pytest.fixture()
def mock_notion_client(monkeypatch):
    instances = []
    def constructor(token, database_id):
        instance = MockNotionClient(token, database_id)
        instances.append(instance)
        return instance
    constructor.instances = instances
    mock_notion_client = MagicMock(side_effect=constructor)
    monkeypatch.setattr(autofill, 'NotionClient', mock_notion_client)
    monkeypatch.setattr(sync, 'NotionClient', mock_notion_client)
    return mock_notion_client

@pytest.fixture()
def app():
    autofill.app.config.update({"TESTING": True})
    return autofill.app

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv('NOTION_API_KEY', 'test_key')
    monkeypatch.setenv('NOTION_DATABASE_ID', 'test_db')
    monkeypatch.setenv('ARIREGISTER_JSON_URL', 'test_url')
    monkeypatch.setenv('GOOGLE_API_KEY', 'test_key')
    monkeypatch.setenv("GOOGLE_CSE_CX", 'test_cse_cx')

@pytest.fixture()
def google_find_website(monkeypatch):
    def mock_google_find_website(company_name):
        if company_name == "OÜ Ideelabor":
            return 'https://ideelabor.ee'
        if company_name == "2S2B Social Media OÜ":
            logging.warning(f"Google CSE päring ebaõnnestus: Test Error")
        return None
    monkeypatch.setattr(sync, 'google_find_website', mock_google_find_website)



class TestUC1:
    def test_UC1_main(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC1_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_called_once_with("UC1_main", {
            'Aadress': {'rich_text': [{'text': {'content': 'Tartu maakond, Tartu linn, Tartu linn, Allika tn 4'}}]},
            'E-post': {'email': 'info@ideelabor.ee'},
            'Kontaktisikud': {'people': []},
            'LinkedIn': {'url': None},
            'Maakond': {'multi_select': [{'name': 'Tartu maakond'}]},
            'Nimi': {'title': [{'text': {'content': 'OÜ Ideelabor'}}]},
            'Põhitegevus': {'rich_text': [{'text': {'content': 'Programmeerimine'}}]},
            'Registrikood': {'number': 11043099},
            'Tegevusvaldkond': {'rich_text': [{'text': {'content': 'Info ja side'}}]},
            'Tel. nr': {'phone_number': '+372 56208082'},
            'Veebileht': {'url': 'https://ideelabor.ee'}})
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC1_main", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Edukalt uuendatud"[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()


    # Missing registry code
    def test_UC1_alt1a(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC1_alt1a"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC1_alt1a", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": "Viga: 'Registrikood' value is empty or in an invalid format on the Notion page."[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()

    # Incorrect registry code
    def test_UC1_alt1b(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC1_alt1b"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC1_alt1b", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": 'Viga: Company with registry code 10 not found in JSON data.'[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_UC1_alt2(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC1_alt2"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_called_once_with("UC1_alt2", {
            'Nimi': {'title': [{'text': {'content': 'Flowerflake OÜ'}}]},
            'Registrikood': {'number': 17281782},
            'Aadress': {'rich_text': [{'text': {'content': 'Harju maakond, Rae vald, Järveküla, Ida põik 1'}}]},
            'Maakond': {'multi_select': [{'name': 'Harju maakond'}]},
            'E-post': {'email': 'smaragda.sarana@gmail.com'},
            'Tel. nr': {'phone_number': None},
            'Veebileht': {'url': None},
            'LinkedIn': {'url': None},
            'Kontaktisikud': {'people': []},
            'Põhitegevus': {'rich_text': [{'text': {'content': 'Programmeerimine'}}]},
            'Tegevusvaldkond': {'rich_text': [{'text': {'content': 'Info ja side'}}]}
        })
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC1_alt2", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Edukalt uuendatud"[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()

    # E2E tests for alternate flow c are not feasible, as we do not run our tests in vercel.


#class TestUC2:
    #TODO: use case is not yet implemented


class TestUC3:
    #TODO: I cannot complete this until I have access to vercel. Also, this test will fail even when I do.
    def test_UC3_main(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC3_main"})
        check_for_autoclose(response)

        notion_client_instance = mock_notion_client.side_effect.instances[0]
        notion_client_instance.update_page_called.assert_called_with("TODO")

        notion_client_instance = mock_notion_client.side_effect.instances[1]
        notion_client_instance.update_page_called.assert_called_once_with({
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Edukalt uuendatud"[:1900]}
                }]
            }
        })
        assert len(mock_notion_client.side_effect.instances) == 2

    # Missing company on refill (effective duplicate of test_UC1_alt1b, as the system just sees a reg code that is missing in the JSON)
    def test_UC3_alt1(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC3_alt1"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC3_alt1", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": 'Viga: Company with registry code 99 not found in JSON data.'[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()


#class TestUC4:
    # TODO: use case is not yet implemented


class TestUC5:
    # Hey, another effective duplicate. We always test for feedback.
    def test_UC5_main(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC5_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC5_main", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": 'Viga: Company with registry code 24 not found in JSON data.'[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()

    # E2E tests for alternate flow are not feasible, as we do not run our tests in vercel.


class TestUC6:
    def test_UC6_main(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC6_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_called_once_with("UC6_main", {
            'Nimi': {'title': [{'text': {'content': 'Accelerator OÜ'}}]},
            'Registrikood': {'number': 16359677},
            'Aadress': {'rich_text': [{'text': {'content': 'Harju maakond, Harku vald, Tiskre küla, Taverni tee 2/2-23'}}]},
            'Maakond': {'multi_select': [{'name': 'Harju maakond'}]},
            'E-post': {'email': 'konstantin.sadekov@gmail.com'},
            'Tel. nr': {'phone_number': None},
            'Veebileht': {'url': None},
            'LinkedIn': {'url': None},
            'Kontaktisikud': {'people': []},
            'Põhitegevus': {'rich_text': [{'text': {'content': 'Kogu muu mujal liigitamata kutse-, teadus- ja tehnikaalane tegevus'}}]},
            'Tegevusvaldkond': {'rich_text': [{'text': {'content': 'Kutse-, teadus- ja tehnikaalane tegevus'}}]}
        })
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC6_main", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Edukalt uuendatud"[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()

    # Google API failure
    def test_UC6_alt1(self, client, monkeypatch, mock_notion_client, mock_env, mock_cache_dir, google_find_website):
        response = client.get("/api/autofill", query_string={"pageId": "UC6_alt1"})
        check_for_autoclose(response)
        notion_client_instances = mock_notion_client.side_effect.instances
        assert len(notion_client_instances) == 2

        notion_client_instances[0].update_page_called.assert_called_once_with("UC6_alt1", {
            'Nimi': {'title': [{'text': {'content': '2S2B Social Media OÜ'}}]},
            'Registrikood': {'number': 14543684},
            'Aadress': {'rich_text': [{'text': {'content': 'Harju maakond, Tallinn, Kesklinna linnaosa, Ahtri tn 12'}}]},
            'Maakond': {'multi_select': [{'name': 'Harju maakond'}]},
            'E-post': {'email': 'alexandre.werkoff@gmail.com'},
            'Tel. nr': {'phone_number': '+66 21589403'},
            'Veebileht': {'url': None},
            'LinkedIn': {'url': None},
            'Kontaktisikud': {'people': []},
            'Põhitegevus': {'rich_text': [{'text': {'content': 'Äri- ja muu juhtimisalane nõustamine'}}]},
            'Tegevusvaldkond': {'rich_text': [{'text': {'content': 'Kutse-, teadus- ja tehnikaalane tegevus'}}]}
        })
        notion_client_instances[0].create_page_called.assert_not_called()

        notion_client_instances[1].update_page_called.assert_called_once_with("UC6_alt1", {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Edukalt uuendatud"[:1900]}
                }]
            }
        })
        notion_client_instances[1].create_page_called.assert_not_called()


#class TestUC7:
    #TODO: use case is not yet implemented


#class TestUC8:
    #TODO: use case is not yet implemented
