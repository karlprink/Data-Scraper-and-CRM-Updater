from flask import Flask, request, redirect
import os
import traceback

# Use relative imports to find files in the same directory.
from .sync import autofill_page_by_page_id
from .notion_client import NotionClient  # olemasolev NotionClient fail

app = Flask(__name__)

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
    notion_url = None
    try:
        # Get pageId and Notion page URL from query parameters or JSON body
        if request.method == 'GET':
            page_id = request.args.get('pageId')
            notion_url = request.args.get('notionUrl')
        else:  # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId')
            notion_url = data.get('notionUrl') or request.args.get('notionUrl')

        if not page_id or not notion_url:
            return "Missing pageId or notionUrl", 400

        # Run autofill
        result = autofill_page_by_page_id(page_id)

        # Update Notion status property
        if result.get("success"):
            update_autofill_status(page_id, "Success")
        else:
            error_message = result.get("message") or "Unknown error"
            update_autofill_status(page_id, f"Error: {error_message}")

        # Redirect back to Notion page
        return redirect(notion_url, code=302)

    except Exception as e:
        traceback.print_exc()
        # Update Notion status property with exception
        try:
            if page_id:
                update_autofill_status(page_id, f"Error: {type(e).__name__}: {e}")
        except:
            pass
        # Redirect to Notion home if pageId or URL not available
        return redirect(notion_url or "https://www.notion.so", code=302)


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
