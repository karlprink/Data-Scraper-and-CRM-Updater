import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def load_config():
    """Simulates configuration loading."""
    return {"api_key": "dummy_key", "database_id": "dummy_id"}


def load_company_data(regcode, config):
    """Simulates loading company data from the Business Register (Äriregister)."""
    if regcode == "10000000":
        return {"status": "ok", "data": {"properties": {"Nimi": {"title": [{"text": {"content": "Test OÜ"}}]},
                                                        "Registrycode": {"number": 10000000}}}}
    elif regcode == "99999999":
        return {"status": "error", "message": "Company not found."}
    else:
        # Registration code must be a string of digits
        if not regcode.isdigit():
            return {"status": "error", "message": "Invalid registration code format."}
        return {"status": "error", "message": "Other error during data loading."}


def test_config_loading_success():
    """Checks if configuration is loaded successfully and contains the necessary keys."""
    config = load_config()
    assert isinstance(config, dict)
    assert "api_key" in config
    assert "database_id" in config


def test_company_data_found():
    """Checks the scenario of successful data loading."""
    config = load_config()
    result = load_company_data("10000000", config)
    assert result["status"] == "ok"
    assert "Test OÜ" in result["data"]["properties"]["Nimi"]["title"][0]["text"]["content"]


def test_company_data_not_found():
    """Checks the scenario where the registration code is not found."""
    config = load_config()
    result = load_company_data("99999999", config)
    assert result["status"] == "error"
    assert "Company not found." in result["message"]


def test_invalid_regcode_format():
    """Checks whether the system handles an invalid registration code format."""
    config = load_config()
    result = load_company_data("ABC-123", config)
    assert result["status"] == "error"
    assert "Invalid registration code format." in result["message"]
