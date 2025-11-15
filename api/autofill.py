from flask import Flask, request, render_template_string, Response
import traceback
import json
from typing import Dict, Any

# Assuming these are relative imports in the project structure
from .sync import autofill_page_by_page_id
from .notion_client import NotionClient
from .config import load_config

# --- Flask App Initialization ---
app = Flask(__name__)

# --- HTML Template for User Feedback (Kept in Estonian as user-facing) ---
AUTO_CLOSE_HTML = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Done</title></head>
<body>
<script>
/* Püüame tabu sulgeda; kui brauser ei luba, proovime uuesti väikese viitega. */
(function(){
  try { window.close(); } catch(e) {}
  setTimeout(function(){
    try { window.open('', '_self', ''); window.close(); } catch(e) {}
  }, 30);
})();
</script>
</body></html>
"""

# --- Notion Status Update Utility ---

def update_autofill_status(page_id: str, status_text: str, config: Dict[str, Any]):
    """
    Kirjutab Notioni lehe 'Auto-fill Status' (Rich text) välja.
    Edu korral võid anda "" (tühjenda väli).
    """
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        # kui konfi pole, ei saa seda viga notionisse kirjutada
        return
    
    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)
    try:
        # lisa "type": "text" – Notioni ametlik struktuur
        notion.update_page(page_id, {
            "Auto-fill Status": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": (status_text or "")[:1900]}
                }]
            }
        })
    except Exception as e:
        # jätame vea logi minimaalseks; ei tohi peatada põhivoogu
        traceback.print_exc()


# --- API Endpoints ---

@app.route('/api/autofill', methods=['GET', 'POST'])
def autofill():
    """
    Variant A:
    - Käivitab autofilli
    - Kirjutab 'Auto-fill Status' ("" edu korral; 'Error: ...' vea korral)
    - Tagastab minimaalse HTML-i, mis SULGEB TABI automaatselt (ei hoia raporteid ekraanil)
    """
    page_id = None

    # Konfi laadimine
    config = load_config()
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    ARIREGISTER_JSON_URL = config.get("ariregister", {}).get("json_url")

    # NB! Kui konfi pole, me ei saa Notioni uuendada — aga sulgeme tabu ikkagi
    config_ok = all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL])

    try:
        # pageId võib tulla GET query'st või POST body'st (või POST query'st)
        if request.method == 'GET':
            page_id = request.args.get('pageId')
        else:
            data = request.get_json(silent=True) or {}
            page_id = data.get('pageId') or request.args.get('pageId')

        if not page_id:
            # page_id puudub – midagi teha ei saa; sulgeme tabu.
            return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)

        if not config_ok:
            # Ei ole vajalikku konfi – proovi vähemalt veateade Notioni kirjutada (kui üldse võimalik).
            try:
                update_autofill_status(page_id, "Viga: puuduv konfiguratsioon", config)
            except Exception:
                pass
            return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)


        # Käivita põhiloogika (sinu projektis defineeritud)
        result: Dict[str, Any] = autofill_page_by_page_id(page_id, config)

        # Uuenda Status Notionis (EST)
        if result.get("success"):
            update_autofill_status(page_id, "Edukalt uuendatud", config)
        else:
            msg = result.get("message") or "Tundmatu viga"
            update_autofill_status(page_id, f"Viga: {msg[:200]}", config)


        # Igal juhul: auto-close
        return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)

    except Exception as e:
        traceback.print_exc()
        # Proovi kirjutada krit viga Notioni, kui page_id teada
        if page_id and config_ok:
            try:
                update_autofill_status(page_id, f"Viga: {type(e).__name__}: {e}", config)
            except Exception:
                pass
        # Ja sulgeme tabu niikuinii
        return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)



@app.route('/', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {
        "status": "ok",
        "message": "Notion Autofill API is running",
    }


# --- Local Development Entry Point ---
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)