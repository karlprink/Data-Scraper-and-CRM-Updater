# Data-Scraper-and-CRM-Updater

## CLI kasutamine

Installi sõltuvused ja käivita CLI:

```bash
pip install -r requirements.txt
python main.py --help
```

Kaks režiimi:

- Registrikoodi järgi sünkroonimine CSV-st Notioni (lisab või uuendab kirjet):

```bash
python main.py --regcode 12345678
```

- Täida olemasoleva Notioni lehe andmed lehe `id()` põhjal (loe "Registrikood" lehelt ja uuenda sama lehte):

```bash
python main.py --page-id a1b2c3d4e5f6g7h8i9j0
```

Veendu, et `config.yaml` sisaldab `notion.token`, `notion.database_id` ja `ariregister.csv_url` seadeid.
