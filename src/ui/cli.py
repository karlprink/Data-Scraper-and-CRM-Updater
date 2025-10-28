import argparse
import sys
from src.ui.config_loader import load_config
# EELDAME, ET NEED FUNKTSIOONID ON JUBA ÕIGESTI DEFINEERITUD
from api.sync import load_company_data, process_company_sync, autofill_page_by_page_id


def print_properties(properties: dict):
    """Prints the Notion properties output in a readable format."""
    print("\n--- Leitud andmed ---")

    # Extract all custom fields
    display_data = {}
    for key, value in properties.items():
        if key == "Registrikood":
            display_data[key] = value.get("number")
        elif key == "Nimi":
            display_data[key] = value.get("title", [{}])[0].get("text", {}).get("content", "Missing")
        elif key in ["Aadress", "Tegevusvaldkond", "Põhitegevus"]:
            display_data[key] = value.get("rich_text", [{}])[0].get("text", {}).get("content", "")
        elif key == "Maakond":
            display_data[key] = ", ".join([v["name"] for v in value.get("multi_select", [])])
        elif key in ["E-post", "Tel. nr", "Veebileht", "LinkedIn"]:
            # URL, email, phone_number
            # Use next() to safely retrieve the first key (which holds the value)
            try:
                display_data[key] = value.get(next(iter(value.keys())))
            except StopIteration:
                display_data[key] = None

    for key, value in display_data.items():
        if value:
            print(f"  {key:<20}: {value}")
        else:
            print(f"  {key:<20}: [Tühi]")

    print("--------------------------------\n")


def handle_new_sync_mode(config: dict):
    """Käitleb uue kirje loomist registrikoodi kaudu (interaktiivne ja kinnitusega)."""

    regcode = input("Palun sisesta ettevõtte **registrikood** (vajuta 'Enter' tühistamiseks): ").strip()

    if not regcode:
        print("Tühistatud.")
        sys.exit(0)

    # 2. Load data and check initial errors
    load_result = load_company_data(regcode, config)

    if load_result["status"] == "error":
        print(load_result["message"])
        sys.exit(1)

    data_to_sync = load_result["data"]

    # 3. Print found values and warning
    print(load_result["message"])
    print_properties(data_to_sync["properties"])

    if data_to_sync["empty_fields"]:
        print(
            f"⚠️ HOIATUS: Järgmised väljad jäid tühjaks: {', '.join(data_to_sync['empty_fields'])}. Need jäävad ka Notionis tühjaks.")

    # 4. Ask for user confirmation
    user_input = input("Kas soovite need andmed Notioni laadida (Y/n)? ").lower()

    if user_input != 'y' and user_input != '':
        print("Tühistatud. Andmeid Notioni ei laetud.")
        sys.exit(0)

    # 5. Upload data to Notion
    print("\nAlustan sünkroonimist Notioniga...")
    sync_result = process_company_sync(data_to_sync, config)

    # 6. Print final result
    print(sync_result["message"])

    if sync_result["status"] == "error":
        sys.exit(1)


def handle_autofill_mode(config: dict):
    """Käitleb olemasoleva kirje automaatset täitmist lehe ID kaudu (ilma kinnituseta)."""

    page_id = input("Palun sisesta Notioni **lehe ID** (id()) automaattäitmiseks: ").strip()

    if not page_id:
        print("Tühistatud.")
        sys.exit(0)

    print(f"\nAlustan Notioni lehe ({page_id}) automaatset täitmist...")

    # PARANDUS: Funktsiooni väljakutse on õige, eeldusel, et funktsioon ise on muudetud.
    autofill_page_by_page_id(page_id, config)


def run_cli():

    config = load_config()

    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Sünkrooni Äriregistri andmed Notioni")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--regcode",
                           help="Ettevõtte registrikood (kasutatakse uue kirje loomiseks ilma kinnituseta)")
        group.add_argument("--page-id", help="Notioni lehe ID (id()) automaattäitmiseks")
        args = parser.parse_args()

        if args.page_id:
            # Otsetäitmine lehe ID kaudu (ilma kinnituseta)
            print("Käivitatud režiimis: Automaatne lehe täitmine.")
            autofill_page_by_page_id(args.page_id, config)
        elif args.regcode:
            # Otsetäitmine registrikoodi kaudu (ilma kinnituseta, uus mitteinteraktiivne voog)
            print("Käivitatud režiimis: Automaatne sünkroonimine (ilma kinnituseta).")
            load_result = load_company_data(args.regcode, config)
            if load_result["status"] == "error":
                print(load_result["message"])
                sys.exit(1)

            data_to_sync = load_result["data"]
            sync_result = process_company_sync(data_to_sync, config)
            print(sync_result["message"])
            if sync_result["status"] == "error":
                sys.exit(1)

    else:
        # Interaktiivne režiim (kui argumente pole antud)
        print("Käivitatud režiimis: Interaktiivne menüü.")

        mode = input("Vali režiim: [1] Uus kirje (registrikood) või [2] Täida olemasolev (lehe ID): ").strip()

        if mode == '1':
            handle_new_sync_mode(config)
        elif mode == '2':
            handle_autofill_mode(config)
        else:
            print("Vigane valik. Programmi töö lõpetati.")
            sys.exit(1)
