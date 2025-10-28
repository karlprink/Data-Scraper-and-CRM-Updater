from flask import Flask, request, redirect, render_template_string
import os
import traceback
import json  # Vajalik, et logid oleksid paremini vormindatud

# Use relative imports to find files in the same directory.
from .sync import autofill_page_by_page_id
from .notion_client import NotionClient
from .config import load_config  # Config laadimiseks API-s

app = Flask(__name__)

# HTML mall, mida kuvada brauseris (sisaldab tulemust ja tagasisuunamise nuppu)
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
        pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; }
        .button-link { display: inline-block; margin-top: 20px; padding: 10px 15px; background-color: #333; color: white; text-decoration: none; border-radius: 4px; }
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
        <h2>Debug Info</h2>
        <pre>{{ debug_info }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""


# Function to update the new "Auto-fill Status" property in Notion
def update_autofill_status(page_id: str, status_text: str):
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        print("Missing Notion API configuration for status update")
        return
    notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)
    notion.update_page(page_id, {
        "Auto-fill Status": {
            "rich_text": [{"text": {"content": status_text}}]
        }
    })


@app.route('/api/autofill', methods=['GET', 'POST'])
def autofill():
    page_id = None
    notion_url = None  # Jätame selle parameetri vastuvõtu, aga see pole enam kohustuslik.

    # Määrame default tulemused, kui midagi läheb valesti
    result = {"success": False, "message": "API käivitati, aga tulemus on puudu.", "step": "initial"}

    try:
        # Get pageId and Notion page URL from query parameters or JSON body
        if request.method == 'GET':
            page_id = request.args.get('pageId')
            notion_url = request.args.get('notionUrl')
        else:  # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId')
            notion_url = data.get('notionUrl') or request.args.get('notionUrl')  # Võtame selle vastu, kui see on olemas

        if not page_id:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Kriitiline viga: Puudub vajalik 'pageId' parameeter.",
                debug_info="Palun kontrolli Notioni valemit."
            ), 400


        config = load_config() or {}
        result = autofill_page_by_page_id(page_id, config)


        if result.get("success"):
            update_autofill_status(page_id, "Success")
        else:
            error_message = result.get("message") or "Tundmatu viga"
            update_autofill_status(page_id, f"Error: {error_message}")




        status = "Edukas" if result.get("success") else "Viga"
        status_class = "success" if result.get("success") else (
            "warning" if result.get("status") == "warning" else "error")
        message = result.get("message")


        debug_info = json.dumps(result, indent=2, ensure_ascii=False) if not result.get("success") else None


        return render_template_string(
            HTML_TEMPLATE,
            status=status,
            status_class=status_class,
            message=message,
            redirect_url=notion_url,
            debug_info=debug_info
        )

    except Exception as e:
        traceback.print_exc()

        if page_id:
            try:
                update_autofill_status(page_id, f"Kriitiline API viga: {type(e).__name__}")
            except:
                pass

        return render_template_string(
            HTML_TEMPLATE,
            status="Kriitiline API viga",
            status_class="error",
            message=f"API töötluses tekkis üldine viga: {type(e).__name__}: {e}",
            redirect_url=notion_url
        ), 500


# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return {
        "status": "ok",
        "message": "Notion Autofill API is running",
    }


# Local development
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)