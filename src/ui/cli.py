import argparse
from ..config import load_config
from ..sync import sync_company, autofill_page_by_page_id

def run_cli():
    parser = argparse.ArgumentParser(description="Sünkrooni Äriregistri andmed Notioni")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--regcode", help="Ettevõtte registrikood")
    group.add_argument("--page-id", help="Notioni lehe ID (id())")
    args = parser.parse_args()

    config = load_config()
    if args.page_id:
        autofill_page_by_page_id(args.page_id, config)
    else:
        sync_company(args.regcode, config)
