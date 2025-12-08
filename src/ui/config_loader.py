import yaml
import os

config_path = "config.yaml"


def load_config(path=config_path):
    """
    Loads configuration from YAML file and overrides sensitive values
    using environment variables (if available).
    """

    # Kontrollime konfiguratsioonifaili olemasolu
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at path: {path}.")

    # Lae konfiguratsioon failist
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Kindlustame, et 'notion' ja 'ariregister' võtmed on olemas
    if "notion" not in config:
        config["notion"] = {}
    if "ariregister" not in config:
        config["ariregister"] = {}

    if "csv_path" not in config["ariregister"]:
        config["ariregister"]["csv_path"] = None

    # Keskkonnamuutujate ülekirjutamine (prioriteet)
    if "NOTION_API_KEY" in os.environ:
        config["notion"]["token"] = os.environ["NOTION_API_KEY"]

    if "NOTION_DATABASE_ID" in os.environ:
        config["notion"]["database_id"] = os.environ["NOTION_DATABASE_ID"]

    if "ARZ_CSV_PATH" in os.environ:
        config["ariregister"]["csv_path"] = os.environ["ARZ_CSV_PATH"]

    return config
