import yaml


config_path = 'config.yaml'

def load_config(path=config_path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
