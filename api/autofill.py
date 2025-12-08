from flask import Flask, request, Response
import traceback
from typing import Dict, Any

# Assuming these are relative imports in the project structure
from .sync import autofill_page_by_page_id
from .clients.notion_client import NotionClient
from .config import load_config

# --- Flask App Initialization ---
app = Flask(__name__)

# --- HTML Template for User Feedback (Kept in Estonian as user-facing) ---
AUTO_CLOSE_HTML = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Done</title></head>
<body>
<script>
/* Attempt to close the tab; if the browser doesn't allow it, try again with a slight delay. */
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
    Writes to the 'Auto-fill Status' (Rich text) field of a Notion page.
    On success, you can provide "" (to clear the field).
    """
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        # If config is missing, we cannot write this error to Notion
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)
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

    # Load configuration
    config = load_config()
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    ARIREGISTER_JSON_URL = config.get("ariregister", {}).get("json_url")

    # NOTE! If config is missing, we cannot update Notion — but we still close the tab.
    config_ok = all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL])

    try:
        # pageId can come from a GET query, POST body, or POST query
        if request.method == "GET":
            page_id = request.args.get("pageId")
        else:
            data = request.get_json(silent=True) or {}
            page_id = data.get("pageId") or request.args.get("pageId")

        if not page_id:
            # page_id is missing – cannot do anything; close the tab.
            return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)

        if not config_ok:
            # Required config is missing – try to write an error message to Notion at least (if possible at all).
            try:
                update_autofill_status(
                    page_id, "Error: Missing configuration (EST)", config
                )
            except Exception:
                pass
            return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)

        # Execute the main logic (defined in your project)
        result: Dict[str, Any] = autofill_page_by_page_id(page_id, config)

        # Update Status in Notion
        if result.get("success"):
            update_autofill_status(page_id, "Edukalt uuendatud", config)
        else:
            # Keep error message short for Notion
            msg = result.get("message") or "Unknown error (EST)"
            update_autofill_status(page_id, f"Error: {msg[:200]}", config)

        # In any case: auto-close
        return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)

    except Exception as e:
        traceback.print_exc()
        # Try to write critical error to Notion, if page_id is known and config is ok
        if page_id and config_ok:
            try:
                update_autofill_status(
                    page_id, f"Error: {type(e).__name__}: {e}", config
                )
            except Exception:
                pass
        # And close the tab anyway
        return Response(AUTO_CLOSE_HTML, mimetype="text/html", status=200)


@app.route("/", methods=["GET"])
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
    app.run(debug=True, host="0.0.0.0", port=5001)
