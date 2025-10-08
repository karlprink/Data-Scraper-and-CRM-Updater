import argparse
from ..config import load_config
from ..sync import sync_company

def run_cli():
    parser = argparse.ArgumentParser(description="Sünkrooni Äriregistri andmed Notioni")
    parser.add_argument("regcode", help="Ettevõtte registrikood")
    args = parser.parse_args()

    config = load_config()
    sync_company(args.regcode, config)
