import os
import sys
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import api.autofill as autofill
import api.sync as sync
from api import json_loader, gemini, csv_loader
from api.autofill import AUTO_CLOSE_HTML
from test.mock_clients.mock_ariregister_client import MockAriregisterClient
from test.mock_clients.mock_company_website_client import MockCompanyWebsiteClient
from test.mock_clients.mock_google_client import MockGoogleClient
from test.mock_clients.mock_notion_client import MockNotionClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def check_for_autoclose(response):
    assert response.status_code == 200
    assert response.text == AUTO_CLOSE_HTML
    assert response.mimetype == "text/html"


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("NOTION_API_KEY", "test_key")
    monkeypatch.setenv("NOTION_DATABASE_ID", "test_db")
    monkeypatch.setenv("ARIREGISTER_JSON_URL", "test_url")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
    monkeypatch.setenv("GOOGLE_CSE_CX", "test_google_cse_cx")


@pytest.fixture()
def mock_env_ariregister_fail(monkeypatch):
    monkeypatch.setenv("NOTION_API_KEY", "test_key")
    monkeypatch.setenv("NOTION_DATABASE_ID", "test_db")
    monkeypatch.setenv("ARIREGISTER_JSON_URL", "fail_url")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
    monkeypatch.setenv("GOOGLE_CSE_CX", "test_google_cse_cx")


@pytest.fixture()
def mock_cache_env(monkeypatch):
    monkeypatch.setattr(json_loader, "CACHE_DIR", "test/mock_cache")
    monkeypatch.setattr(
        json_loader, "CACHE_FILE_PATH", "test/mock_cache/ariregister_data.zip"
    )
    monkeypatch.setattr(json_loader, "CACHE_EXPIRATION", timedelta(weeks=52 * 1000))


@pytest.fixture()
def mock_cache_env_expired(monkeypatch):
    monkeypatch.setattr(json_loader, "CACHE_DIR", "test/mock_cache/volatile")
    monkeypatch.setattr(
        json_loader, "CACHE_FILE_PATH", "test/mock_cache/volatile/ariregister_data.zip"
    )
    monkeypatch.setattr(json_loader, "CACHE_EXPIRATION", timedelta(hours=0))


@pytest.fixture()
def mock_notion_client(monkeypatch):
    instances = []

    def constructor(token, database_id, api_version):
        instance = MockNotionClient(token, database_id, api_version)
        instances.append(instance)
        return instance

    constructor.instances = instances
    mock_notion_client = MagicMock(side_effect=constructor)
    monkeypatch.setattr(autofill, "NotionClient", mock_notion_client)
    monkeypatch.setattr(sync, "NotionClient", mock_notion_client)
    return mock_notion_client


@pytest.fixture()
def mock_google_client(monkeypatch):
    instances = []

    def constructor(key, cx):
        instance = MockGoogleClient(key, cx)
        instances.append(instance)
        return instance

    constructor.instances = instances
    mock_google_client = MagicMock(side_effect=constructor)
    monkeypatch.setattr(sync, "GoogleClient", mock_google_client)
    return mock_google_client


@pytest.fixture()
def mock_company_website_client(monkeypatch):
    instances = []

    def constructor():
        instance = MockCompanyWebsiteClient()
        instances.append(instance)
        return instance

    constructor.instances = instances
    mock_company_website_client = MagicMock(side_effect=constructor)
    monkeypatch.setattr(gemini, "CompanyWebsiteClient", mock_company_website_client)
    return mock_company_website_client


@pytest.fixture()
def mock_ariregister_client(monkeypatch):
    instances = []

    def constructor():
        instance = MockAriregisterClient()
        instances.append(instance)
        return instance

    constructor.instances = instances
    mock_ariregister_client = MagicMock(side_effect=constructor)
    monkeypatch.setattr(csv_loader, "AriregisterClient", mock_ariregister_client)
    monkeypatch.setattr(json_loader, "AriregisterClient", mock_ariregister_client)
    return mock_ariregister_client


@pytest.fixture()
def mock_clients(
    mock_notion_client,
    mock_google_client,
    mock_company_website_client,
    mock_ariregister_client,
):
    return [
        mock_notion_client,
        mock_google_client,
        mock_company_website_client,
        mock_ariregister_client,
    ]


@pytest.fixture()
def app():
    autofill.app.config.update({"TESTING": True})
    return autofill.app


@pytest.fixture()
def client(app):
    return app.test_client()


class TestUC1:
    """
    Actor:	                Collaboration manager
    Goal:	                To automatically populate a company's Notion page with the latest official data and a valid website URL.
    Related user stories:	US1-US5, US7
    Trigger:	            Clicks "Auto-fill" link.
    Preconditions:	        1. The collaboration manager is on a company page in Notion.
                            2. The Registrikood (Business Register Code) field on that page is filled.
    """

    def test_uc1_main(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        Flow:   -> 1. Manager clicks "Auto-fill".
                <- 2. System reads the Registrikood.
                <- 3. System finds the company in the Business Register CSV.
                <- 4. System populates the company's Notion fields (Name, Address, Põhitegevus, etc.).
                <- 5. System reads the EMTAK code, looks up the broad category from its internal dictionary, and populates the Tegevusvaldkond field.
                <- 6. System sees the Veebileht field is empty and calls the Google Search API.
                <- 7. System filters search results (skipping registers like teatmik.ee) and populates Veebileht with the first valid URL.
                <- 8. The Notion page reflects the newly populated data.
        Postcondition:	The company's Notion page fields (Name, Address, Põhitegevus, Tegevusvaldkond, Veebileht) are populated with the correct data.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC1_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and updating page contents; one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 1
        )  # One at api.sync for updating 'Veebileht' field.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        # Check calls for all state-modifying functions in mocked client classes.
        notion_client_instances[0].update_page_called.assert_called_once_with(
            "UC1_main",
            {
                "Aadress": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Tartu maakond, Tartu linn, Tartu linn, Allika tn 4"
                            }
                        }
                    ]
                },
                "E-post": {"email": "info@ideelabor.ee"},
                "Kontaktisikud": {"people": []},
                "LinkedIn": {"url": "LinkedIn-i ei leitud."},
                "Maakond": {"multi_select": [{"name": "Tartu maakond"}]},
                "Nimi": {"title": [{"text": {"content": "OÜ Ideelabor"}}]},
                "Põhitegevus": {
                    "rich_text": [{"text": {"content": "Programmeerimine"}}]
                },
                "Registrikood": {"number": 11043099},
                "Tegevusvaldkond": {
                    "multi_select": [{"name": "58-63: Info ja side"}]
                },
                "Tel. nr": {"phone_number": "+372 56208082"},
                "Veebileht": {"url": "https://ideelabor.ee"},
            },
        )
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC1_main",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "Edukalt uuendatud"[:1900]},
                        }
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_uc1_alt1_missing(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        **1a. Invalid or Missing Register Code **
        Flow    -> 1. The Registrikood field is empty or contains a code that does not exist in the CSV.
                <- 2. System searches the CSV and fails to find a match.
                <- 3. The function stops. No fields are populated.
        Postcondition: No fields on the Notion page are changed. The page remains as it was.
        """
        response = client.get(
            "/api/autofill", query_string={"pageId": "UC1_alt1_missing"}
        )
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood', one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 0
        )  # We should not get to searching for a company website.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        # Check calls for all state-modifying functions in mocked client classes.
        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC1_alt1_missing",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Viga: Viga: 'Registrikood' väärtus on Notioni lehel tühi või vales formaadis."[
                                    :1900
                                ]
                            },
                        }
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_uc1_alt1_invalid(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        **1a. Invalid or Missing Register Code **
        Flow    -> 1. The Registrikood field is empty or contains a code that does not exist in the CSV.
                <- 2. System searches the CSV and fails to find a match.
                <- 3. The function stops. No fields are populated.
        Postcondition: No fields on the Notion page are changed. The page remains as it was.
        """
        response = client.get(
            "/api/autofill", query_string={"pageId": "UC1_alt1_invalid"}
        )
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood', one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 0
        )  # We should not get to searching for a company website.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        # Check calls for all state-modifying functions in mocked client classes.
        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC1_alt1_invalid",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Viga: Viga: Ettevõtet registrikoodiga 10 ei leitud JSON andmetest."[
                                    :1900
                                ]
                            },
                        }
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_uc1_alt2(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        **1b. Website Not Found **
        Flow:   -> 1. System successfully populates all data from the CSV (Main Flow steps 1-5).
                <- 2. The Google Search API is called but returns no relevant results (or all are filtered out).
                <- 3. The function completes. All fields except Veebileht are populated.
        Postcondition: The Notion page fields are populated with data from the CSV, but the Veebileht field remains empty.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC1_alt2"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and updating page contents; one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 1
        )  # One at api.sync for updating 'Veebileht' field (which fails).
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        notion_client_instances[0].update_page_called.assert_called_once_with(
            "UC1_alt2",
            {
                "Nimi": {"title": [{"text": {"content": "Flowerflake OÜ"}}]},
                "Registrikood": {"number": 17281782},
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
                "Tel. nr": {"phone_number": "Telefoni numbrit ei leitud."},
                "Veebileht": {"url": "Veebilehte ei leitud."},
                "LinkedIn": {"url": "LinkedIn-i ei leitud."},
                "Kontaktisikud": {"people": []},
                "Põhitegevus": {
                    "rich_text": [{"text": {"content": "Programmeerimine"}}]
                },
                "Tegevusvaldkond": {
                    "multi_select": [{"name": "58-63: Info ja side"}]
                },
            },
        )
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC1_alt2",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "Edukalt uuendatud"[:1900]},
                        }
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    # E2E tests for alternate flow c are not feasible, as we do not run our tests in vercel.


# class TestUC2:
# TODO: implement tests


class TestUC3:
    """
    Actor:	                Collaboration manager
    Goal:	                To refresh a company's official data from the register without losing manually entered custom data.
    Related user stories:	US1-US5, US7
    Trigger:	            Clicks "Auto-fill" link on a previously populated page.
    Preconditions:	        1. The collaboration manager is on a company page that was previously auto-filled.
                            2. The manager may have manually added data to other fields.
                            3. The Registrikood field is still correct.
    """

    def test_uc3_main(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        Flow:   -> 1. Manager clicks "Auto-fill" (for a second time).
                <- 2. System reads the Registrikood.
                <- 3. System finds the company's latest data in the Business Register CSV.
                <- 4. System overwrites all fields it manages (Name, Address, Põhitegevus, etc.) with the new data.
                <- 5. System preserves all data in fields it does not manage.
                <- 6. System re-runs the Tegevusvaldkond mapping (in case the code changed).
                <- 7. System re-runs the Google Search logic only if the Veebileht field is still empty.
        Postcondition:	The company's Notion page fields are updated with the freshest data from the CSV, while all manually-entered data in other fields is preserved.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC3_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and updating page contents; one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 0
        )  # Google search logic should not be rerun as the entry already has a website listed.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        notion_client_instances[0].update_page_called.assert_called_with(
            "UC3_main",
            {
                "Aadress": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Tartu maakond, Tartu linn, Tartu linn, Allika tn 4"
                            }
                        }
                    ]
                },
                "Kontaktisikud": {"people": []},
                "Maakond": {"multi_select": [{"name": "Tartu maakond"}]},
                "Nimi": {"title": [{"text": {"content": "OÜ Ideelabor"}}]},
                "Põhitegevus": {
                    "rich_text": [{"text": {"content": "Programmeerimine"}}]
                },
                "Registrikood": {"number": 11043099},
                "Tegevusvaldkond": {
                    "multi_select": [{"name": "58-63: Info ja side"}]
                }
            }
        )
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC3_main",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "Edukalt uuendatud"[:1900]},
                        }
                    ]
                }
            }
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_uc3_alt1(
        self, monkeypatch, client, mock_env, mock_cache_env, mock_clients
    ):
        """
        3a. Company No Longer in Register
        Flow:   -> 1. Manager clicks "Auto-fill".
                <- 2. System searches the CSV for the Registrikood (e.g., the company went bankrupt and was removed).
                <- 3. System fails to find a match.
                <- 4. The function stops. No fields are overwritten or cleared.
        Postcondition: The page remains in its last known state. No data is changed or deleted.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC3_alt1"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 0
        )  # Google search logic should not be run.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 0
        )  # We are using cached ariregister data, so ariregister should not be contacted.

        notion_client_instances[0].update_page_called.assert_not_called()
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC3_alt1",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Viga: Viga: Ettevõtet registrikoodiga 99 ei leitud JSON andmetest."[
                                    :1900
                                ]
                            },
                        }
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()


# class TestUC4:
# TODO: implement tests


class TestUC5:
    """
    Actor:	                System (triggered by Collaboration Manager)
    Goal:	                To ensure the system uses relatively fresh data (max 24h old) while minimizing slow external downloads.
    Related user stories:	US2
    Trigger:	            User clicks "Auto-fill" or manually requests a data refresh.
    Preconditions:	        The external Estonian Business Register URL is accessible.
    """

    def test_uc5_main(
        self, monkeypatch, client, mock_env, mock_cache_env_expired, mock_clients
    ):
        """
        Flow:   -> 1. System receives a request to access company data.
                <- 2. System checks the local storage/cache for the ariregister_data.csv file.
                <- 3. System checks the "Last Modified" timestamp of the file.
                <- 4. Decision Point:
                * A (Cache Hit, extensively tested): If the file exists AND is younger than 24 hours, the System skips the download and loads the local file.
                * B (Cache Miss, current scenario): If the file is missing OR older than 24 hours, the System downloads the fresh CSV from the external URL.
                <- 5. (If Downloaded): System overwrites the local cache file with the new data.
                <- 6. (If Downloaded): System logs the update event with a timestamp: Cache Miss: Data downloaded at [TIME].
        Postcondition:	The system proceeds with the autofill process using valid data.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC5_main"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 1
        )  # One at api.sync for updating 'Veebileht' field.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 1
        )  # We are NOT using cached ariregister data, so ariregister should be contacted.

        notion_client_instances[0].update_page_called.assert_called_once_with(
            "UC5_main",
            {
                "Nimi": {"title": [{"text": {"content": "Accelerator OÜ"}}]},
                "Registrikood": {"number": 16359677},
                "Aadress": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Harju maakond, Harku vald, Tiskre küla, Taverni tee 2/2-23"
                            }
                        }
                    ]
                },
                "Maakond": {"multi_select": [{"name": "Harju maakond"}]},
                "E-post": {"email": "konstantin.sadekov@gmail.com"},
                "Tel. nr": {"phone_number": "Telefoni numbrit ei leitud."},
                "Veebileht": {"url": "Veebilehte ei leitud."},
                "LinkedIn": {"url": "LinkedIn-i ei leitud."},
                "Kontaktisikud": {"people": []},
                "Põhitegevus": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Kogu muu mujal liigitamata kutse-, teadus- ja tehnikaalane tegevus"
                            }
                        }
                    ]
                },
                "Tegevusvaldkond": {
                    "multi_select": [
                        {"name": "69-75: Kutse-; teadus- ja tehnikaalane tegevus"}
                    ]
                },
            },
        )
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC5_main",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Edukalt uuendatud"}}
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()

    def test_uc5_alt1(
        self,
        monkeypatch,
        client,
        mock_env_ariregister_fail,
        mock_cache_env_expired,
        mock_clients,
    ):
        """
        5a. Download Failed
        Flow:   -> 1. Cache is expired (older than 24h).
                <- 2. System attempts to download fresh data but fails (External API down / Timeout).
                <- 3. System fallback: System uses the existing (older) cache file to prevent a total crash, but logs a warning: Download failed. Using stale data.
        """
        response = client.get("/api/autofill", query_string={"pageId": "UC5_alt1"})
        check_for_autoclose(response)
        notion_client_instances = mock_clients[0].side_effect.instances
        google_client_instances = mock_clients[1].side_effect.instances
        company_website_client_instances = mock_clients[2].side_effect.instances
        ariregister_client_instances = mock_clients[3].side_effect.instances
        assert (
            len(notion_client_instances) == 2
        )  # One at api.sync for reading 'Registrikood' and updating page contents; one at api.sync for updating the status field.
        assert (
            len(google_client_instances) == 1
        )  # One at api.sync for updating 'Veebileht' field.
        assert (
            len(company_website_client_instances) == 0
        )  # We are not looking for contacts, so company website should not be touched.
        assert (
            len(ariregister_client_instances) == 1
        )  # We are NOT using cached ariregister data, so ariregister should be contacted.

        notion_client_instances[0].update_page_called.assert_called_once_with(
            "UC5_alt1",
            {
                "Nimi": {"title": [{"text": {"content": "Accelerator OÜ"}}]},
                "Registrikood": {"number": 16359677},
                "Aadress": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Harju maakond, Harku vald, Tiskre küla, Taverni tee 2/2-23"
                            }
                        }
                    ]
                },
                "Maakond": {"multi_select": [{"name": "Harju maakond"}]},
                "E-post": {"email": "konstantin.sadekov@gmail.com"},
                "Tel. nr": {"phone_number": "Telefoni numbrit ei leitud."},
                "Veebileht": {"url": "Veebilehte ei leitud."},
                "LinkedIn": {"url": "LinkedIn-i ei leitud."},
                "Kontaktisikud": {"people": []},
                "Põhitegevus": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Kogu muu mujal liigitamata kutse-, teadus- ja tehnikaalane tegevus"
                            }
                        }
                    ]
                },
                "Tegevusvaldkond": {
                    "multi_select": [
                        {"name": "69-75: Kutse-; teadus- ja tehnikaalane tegevus"}
                    ]
                },
            },
        )
        notion_client_instances[0].create_page_called.assert_not_called()
        notion_client_instances[1].update_page_called.assert_called_once_with(
            "UC5_alt1",
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Edukalt uuendatud"}}
                    ]
                }
            },
        )
        notion_client_instances[1].create_page_called.assert_not_called()


# TODO: UC6 is yet to be implemented
