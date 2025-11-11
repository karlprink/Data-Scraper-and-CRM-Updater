from flask import Flask, request, render_template_string
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
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="et">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autofill Tulemus</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .success { color: #155724; background-color: #d4edda; border-color: #c3e6cb; padding: 10px; border-radius: 4px; }
        .error { color: #721c24; background-color: #f8d7da; border-color: #f5c6cb; padding: 10px; border-radius: 4px; }
        .warning { color: #856404; background-color: #fff3cd; border-color: #ffeeba; padding: 10px; border-radius: 4px; }
        .button-link { display: inline-block; margin-top: 20px; padding: 10px 15px; background-color: #333; color: white; text-decoration: none; border-radius: 4px; }
        pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Automaattäitmise tulemus</h1>
        <div class="{{ status_class }}">
            <p><strong>Status:</strong> {{ status }}</p>
            <p>{{ message }}</p>
        </div>

        {% if redirect_url %}
            <a href="{{ redirect_url }}" class="button-link">Mine tagasi Notioni lehele</a>
            <p style="margin-top: 10px; font-size: 0.8em;">Võid selle akna nüüd sulgeda.</p>
        {% endif %}

        {% if debug_info %}
        <h2>Debug Info (Ainult vigade korral)</h2>
        <pre>{{ debug_info }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Notion Status Update Utility ---

def update_autofill_status(page_id: str, status_text: str, config: Dict[str, Any]):
    """
    Updates the 'Auto-fill Status' rich text property on a Notion page.

    This provides immediate feedback on the Notion page about the status of the API call.

    Args:
        page_id: The ID of the Notion page to update.
        status_text: The text to write into the status property (e.g., 'Success' or 'Error: ...').
        config: The application configuration dictionary.
    """
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        print("ERROR: Missing Notion API configuration for status update.")
        return

    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)
    try:
        # Assumes a Notion property named "Auto-fill Status" exists and is of type Rich Text
        notion.update_page(page_id, {
            "Auto-fill Status": {
                "rich_text": [{"text": {"content": status_text}}]
            }
        })
    except Exception as e:
        print(f"Error updating Notion status for page {page_id}: {e}")
        traceback.print_exc()

# --- API Endpoints ---

@app.route('/api/autofill', methods=['GET', 'POST'])
def autofill():
    """
    The main endpoint for triggering Notion page autofill.

    It loads configuration, extracts page ID and Notion URL from the request,
    calls the core autofill logic, updates the Notion status, and renders an
    HTML feedback page for the user.
    """
    page_id = None
    notion_url = None

    # Load configuration from environment variables
    config = load_config()

    # Configuration validation (essential for the API to run)
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    ARIREGISTER_JSON_URL = config.get("ariregister", {}).get("json_url")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL]):
        error_msg = "Critical API Error: Missing configuration (NOTION_API_KEY, NOTION_DATABASE_ID, ARIREGISTER_JSON_URL). Check Vercel/Environment settings."
        print(error_msg)
        return render_template_string(
            HTML_TEMPLATE,
            status="Viga",
            status_class="error",
            message=error_msg,
            debug_info=json.dumps(config, indent=2, ensure_ascii=False)
        ), 500

    result: Dict[str, Any] = {"success": False, "message": "API was initiated, but no result was returned.", "step": "initial"}

    try:
        # Extract page_id and notion_url from request arguments (GET or JSON body for POST)
        if request.method == 'GET':
            page_id = request.args.get('pageId')
            notion_url = request.args.get('notionUrl')
        else: # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId') # Allow pageId in query for POST too
            notion_url = data.get('notionUrl') or request.args.get('notionUrl')

        if not page_id:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Critical Error: Required 'pageId' parameter is missing.",
                debug_info="Please check the Notion formula setup."
            ), 400

        # Run the core autofill logic
        result = autofill_page_by_page_id(page_id, config)

        # Update Notion status based on the result
        if result.get("success"):
            update_autofill_status(page_id, "Success", config)
        else:
            error_message = result.get("message") or "Unknown Error"
            # Limit status text to avoid Notion Rich Text property limits (if any)
            update_autofill_status(page_id, f"Error: {error_message[:200]}", config)

        # Prepare response for the user's browser (Estonian status texts)
        status_text = "Edukas" if result.get("success") else "Viga"
        status_class = "success" if result.get("success") else (
            "warning" if result.get("status") == "warning" else "error")
        message = result.get("message")

        # Provide debug info only on failure
        debug_info = json.dumps(result, indent=2, ensure_ascii=False) if not result.get("success") else None

        return render_template_string(
            HTML_TEMPLATE,
            status=status_text,
            status_class=status_class,
            message=message,
            redirect_url=notion_url,
            debug_info=debug_info
        )

    except Exception as e:
        traceback.print_exc()

        # Attempt a critical error update in Notion
        if page_id:
            try:
                update_autofill_status(page_id, f"Critical API Error: {type(e).__name__}", config)
            except:
                pass # Fail silently if status update fails during critical error

        return render_template_string(
            HTML_TEMPLATE,
            status="Kriitiline API viga",
            status_class="error",
            message=f"A general error occurred during API processing: {type(e).__name__}: {e}",
            redirect_url=notion_url
        ), 500


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