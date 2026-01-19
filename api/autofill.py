import traceback
from typing import Dict, Any

from flask import Flask, request, Response, render_template_string

from .clients.notion_client import NotionClient
from .config import load_config
# Assuming these are relative imports in the project structure
from .sync import autofill_page_by_page_id

# --- Flask App Initialization ---
app = Flask(__name__)

# --- HTML Template for User Feedback (Kept in Estonian as user-facing) ---
RESULT_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Autofill Tulemus</title>
    <style>
        body { font-family: sans-serif; line-height: 1.6; padding: 20px; max-width: 600px; margin: 0 auto; }
        .card { border: 1px solid #ddd; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .success { color: #2ecc71; }
        .warning { color: #f39c12; }
        .error { color: #e74c3c; }
        h2 { margin-top: 0; }
        pre { background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="card">
        <h2 class="{{ 'success' if success else 'error' }}">
            {{ '✅ Valmis!' if success else '❌ Viga!' }}
        </h2>
        <p>{{ message }}</p>
        {% if company_name %}
            <p><strong>Ettevõte:</strong> {{ company_name }}</p>
        {% endif %}
        <hr>
        <p><small>Võid selle akna nüüd sulgeda.</small></p>
    </div>
</body>
</html>
"""


# --- Notion Status Update Utility ---


def update_autofill_status(page_id: str, status_text: str, config: Dict[str, Any]):
    """
    Writes to the 'Auto-fill Status' (Rich text) field of a Notion page.
    On success, you can provide "" (to clear the field).
    """
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    NOTION_API_VERSION = config.get("notion", {}).get("api_version")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        # If config is missing, we cannot write this error to Notion
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID, NOTION_API_VERSION)
    try:
        # Add "type": "text" – Notion's official structure
        notion.update_page(
            page_id,
            {
                "Auto-fill Status": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": (status_text or "")[:1900]},
                        }
                    ]
                }
            },
        )
    except Exception as e:
        # Keep error logging minimal; must not stop the main flow
        traceback.print_exc()


# --- API Endpoints ---


@app.route("/api/autofill", methods=["GET", "POST"])
def autofill():
    """
    Variant A:
    - Triggers the autofill process.
    - Writes 'Auto-fill Status' ("" on success; 'Error: ...' on failure).
    - Returns a minimal HTML page that automatically CLOSES THE TAB (does not keep reports on screen).
    """
    page_id = None
    config = load_config()

    try:
        if request.method == "GET":
            page_id = request.args.get("pageId")
        else:
            data = request.get_json(silent=True) or {}
            page_id = data.get("pageId") or request.args.get("pageId")

        if not page_id:
            return "Viga: pageId puudub", 400

        # Käivitame sünkroonimise
        result = autofill_page_by_page_id(page_id, config)

        # Uuendame staatust Notionis
        status_msg = "Edukalt uuendatud" if result.get("success") else f"Viga: {result.get('message')}"
        update_autofill_status(page_id, status_msg, config)

        return render_template_string(
            RESULT_HTML,
            success=result.get("success"),
            message=result.get("message"),
            company_name=result.get("company_name")
        )

    except Exception as e:
        err_msg = f"Kriitiline viga: {str(e)}"
        if page_id:
            update_autofill_status(page_id, err_msg, config)
        return render_template_string(RESULT_HTML, success=False, message=err_msg), 200



@app.route("/", methods=["GET"])
def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {
        "status": "ok",
        "message": "Notioni automaatse täitmise API töötab",
    }


# --- Local Development Entry Point ---
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
