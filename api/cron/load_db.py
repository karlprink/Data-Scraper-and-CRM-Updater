import os
import sys
import json
import api
from flask import Flask, request, jsonify


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Impordi vajalikud funktsioonid teistest failidest
try:
    from db_loader import load_to_db  # Andmete laadimise funktsioon (failist db_loader.py)
except ImportError as e:
    # See juhtub sageli Vercelis, kui teek on vale
    print(f"ERROR: Failed to import db_loader. Check sys.path setup. {e}")
    # Näita süsteemi teid silumiseks
    print("Current sys.path:", sys.path)
    # Lõpeta käivitamine, kui põhiosa on puudu
    sys.exit(1)

app = Flask(__name__)


# --- VERCELI FUNKTSIOON (HANDLER) ---
@app.route('/api/cron/load-db', methods=['GET', 'POST'])
def load_db_cron_job():
    """
    Käivitab Äriregistri andmete laadimise andmebaasi.
    See marsruut on kaitstud CRON_SECRET abil.
    """

    # 1. Kontrolli keskkonnamuutujate olemasolu
    CRON_SECRET = os.getenv('CRON_SECRET')
    JSON_URL = os.getenv('ARIREGISTER_JSON_URL')

    if not CRON_SECRET or not JSON_URL:
        # 500: Server Error - Seadistus on puudulik
        return jsonify({
            "error": "Internal Error: CRON_SECRET or ARIREGISTER_JSON_URL not configured."
        }), 500

    # 2. Turvakontroll (401 Unauthorized vältimiseks)

    # A. Kontrollime URL-i parameetrit (käsitsi käivitamisel URL-i kaudu)
    url_secret = request.args.get('secret')

    # B. Kontrollime Authorization päist (Verceli UI/ajastatud käivitus)
    # Vercel saadab turvalise päringu kujul "Bearer [CRON_SECRET]"
    auth_header = request.headers.get('Authorization', '')
    header_secret = None
    if auth_header.startswith('Bearer '):
        header_secret = auth_header.replace('Bearer ', '', 1)

    # Autentimine õnnestub, kui üks saladustest vastab
    if url_secret == CRON_SECRET or header_secret == CRON_SECRET:

        # --- TURVAKONTROLL ÕNNESTUS! ---
        print("✅ Cron job authentication successful. Starting data loading...")

        try:
            # 3. Käivita andmete laadimine (kasutab optimeeritud db_loader.py koodi)
            # See funktsioon peaks olema failis api/db_loader.py
            load_to_db(JSON_URL)

            # Töö on käimas (või lõppenud, kui see toimub sünkroonselt)
            return jsonify({
                "message": "DB loading job finished successfully (or initiated)."
            }), 200

        except Exception as e:
            print(f"🛑 CRITICAL ERROR during DB loading: {e}", file=sys.stderr)
            return jsonify({
                "error": "DB loading failed.",
                "details": str(e)
            }), 500

    else:
        # --- TURVAKONTROLL EBAÕNNESTUS ---
        print("🛑 Cron job authentication failed: Secret mismatch or missing.")
        return jsonify({"error": "Unauthorized"}), 401


# Verceli nõutud handler, kui kasutatakse API kausta
def handler(request):
    """Verceli serverivaba funktsiooni sisendpunkt."""
    return app(request.environ, lambda status, headers: (status, headers))


