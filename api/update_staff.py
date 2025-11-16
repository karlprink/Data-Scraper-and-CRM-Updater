from flask import Flask, request, render_template_string
import traceback
import json
import requests
from typing import Dict, Any, List

# Assuming these are relative imports in the project structure
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
    <title>Kontaktisikute uuendamise tulemus</title>
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
        <h1>Kontaktisikute uuendamise tulemus</h1>
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

# --- API Endpoints ---

def _build_notion_properties(properties_data: Dict[str, Any], page_properties: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Converts flat property data into Notion API property format.
    
    Supports:
    - Nimi: Rich text (or title if that's the actual property type)
    - Email: Email property
    - Telefoninumber: Phone number property
    - Ettevõte: Relation property (array of page IDs)
    - Name: Title property (if it's the title field)
    
    Args:
        properties_data: Dictionary with property names and values
        page_properties: Optional dictionary of page properties to check actual types
        
    Returns:
        Dictionary formatted for Notion API
    """
    notion_properties = {}
    
    for prop_name, prop_value in properties_data.items():
        if prop_value is None:
            continue
        
        # Check actual property type from page if available
        prop_type = None
        if page_properties and prop_name in page_properties:
            prop_type = page_properties[prop_name].get("type")
            print(f"Property '{prop_name}' has type: {prop_type}")
        
        # Handle "Name" - this is the role (CEO, HR Manager, etc.) - should be title field
        if prop_name == "Name":
            if isinstance(prop_value, str):
                notion_properties[prop_name] = {
                    "title": [{"text": {"content": prop_value}}]
                }
        
        # Handle "Nimi" - this is the actual person's name - should be rich_text
        elif prop_name == "Nimi":
            if isinstance(prop_value, str):
                notion_properties[prop_name] = {
                    "rich_text": [{"text": {"content": prop_value}}]
                }
        
        # Handle Email
        elif prop_name == "Email" or prop_name == "@ Email":
            notion_properties[prop_name] = {
                "email": prop_value if prop_value else None
            }
        
        # Handle Phone Number
        elif prop_name == "Telefoninumber" or prop_name == "Phone":
            notion_properties[prop_name] = {
                "phone_number": prop_value if prop_value else None
            }
        
        # Handle Relation (Ettevõte)
        elif prop_name == "Ettevõte" or prop_name == "Company":
            # Expect array of page IDs
            if isinstance(prop_value, list):
                relation_list = []
                for item in prop_value:
                    if isinstance(item, dict) and 'id' in item:
                        relation_list.append({"id": item['id']})
                    elif isinstance(item, str):
                        relation_list.append({"id": item})
                notion_properties[prop_name] = {"relation": relation_list}
            elif isinstance(prop_value, str):
                # Single page ID
                notion_properties[prop_name] = {"relation": [{"id": prop_value}]}
        
        # Handle Rich Text (for any other text fields)
        elif isinstance(prop_value, str):
            notion_properties[prop_name] = {
                "rich_text": [{"text": {"content": prop_value}}]
            }
    
    return notion_properties


@app.route('/api/update-staff', methods=['GET', 'POST'])
def update_staff():
    """
    The main endpoint for updating staff/contact persons on a Notion page.

    It loads configuration, extracts page ID and properties data from the request,
    updates the Notion page properties, and renders an HTML feedback page.

    Expected request format:
    - pageId: The Notion page ID (required)
    - properties: Dictionary of property names and values to update (required)
        Example: {
            "Nimi": "John Doe",
            "Email": "john@example.com",
            "Telefoninumber": "+372 12345678",
            "Ettevõte": ["company-page-id-1"]  // Relation property
        }
    - notionUrl: Optional redirect URL back to Notion page
    """
    page_id = None
    notion_url = None
    properties_data = None

    # Load configuration from environment variables
    config = load_config()

    # Configuration validation (essential for the API to run)
    NOTION_API_KEY = config.get("notion", {}).get("token")
    NOTION_DATABASE_ID = config.get("notion", {}).get("database_id")
    print("================================================")
    print(NOTION_API_KEY, NOTION_DATABASE_ID)
    print("================================================")


    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        error_msg = "Critical API Error: Missing configuration (NOTION_API_KEY, NOTION_DATABASE_ID). Check Vercel/Environment settings."
        print(error_msg)
        return render_template_string(
            HTML_TEMPLATE,
            status="Viga",
            status_class="error",
            message=error_msg,
            debug_info=json.dumps(config, indent=2, ensure_ascii=False)
        ), 500

    try:
        # Extract page_id, notion_url, and properties from request
        if request.method == 'GET':
            page_id = request.args.get('pageId')
            notion_url = request.args.get('notionUrl')
            # For GET requests, properties can be passed as JSON string
            properties_json = request.args.get('properties')
            if properties_json:
                try:
                    properties_data = json.loads(properties_json)
                except json.JSONDecodeError:
                    properties_data = None
        else:  # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId')
            notion_url = data.get('notionUrl') or request.args.get('notionUrl')
            properties_data = data.get('properties')

        if not page_id:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Critical Error: Required 'pageId' parameter is missing.",
                debug_info="Please check the Notion formula setup."
            ), 400

        if not properties_data:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Critical Error: Required 'properties' parameter is missing. Expected a dictionary of property names and values.",
                debug_info='Example: {"properties": {"Nimi": "John Doe", "Email": "john@example.com"}}'
            ), 400

        # Validate properties_data format
        if not isinstance(properties_data, dict):
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Error: 'properties' must be a dictionary/object.",
                debug_info=f"Received type: {type(properties_data).__name__}"
            ), 400

        # Initialize Notion client
        notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

        # Fetch page to verify it exists and get property types
        page_properties = None
        try:
            page_data = notion.get_page(page_id)
            page_properties = page_data.get("properties", {})
            available_properties = list(page_properties.keys())
            print(f"Available properties on page: {available_properties}")
        except Exception as e:
            print(f"Warning: Could not fetch page to check properties: {e}")

        # Convert properties to Notion API format (pass page_properties to check types)
        notion_properties = _build_notion_properties(properties_data, page_properties)
        
        print(f"Properties being sent to Notion: {json.dumps(notion_properties, indent=2, ensure_ascii=False)}")

        if not notion_properties:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Error: No valid properties found to update.",
                debug_info="Please check that property names match your Notion database."
            ), 400

        # Update the Notion page
        try:
            notion.update_page(page_id, notion_properties)
        except requests.HTTPError as e:
            # Extract detailed error message from Notion API
            error_details = ""
            try:
                error_response = e.response.json()
                error_details = error_response.get("message", str(e.response.text))
                print(f"Notion API Error Details: {error_details}")
                print(f"Request payload: {json.dumps({'properties': notion_properties}, indent=2, ensure_ascii=False)}")
            except:
                error_details = e.response.text if hasattr(e, 'response') else str(e)
            
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message=f"❌ Notion API Error ({e.response.status_code if hasattr(e, 'response') else 'Unknown'}): {error_details}",
                redirect_url=notion_url,
                debug_info=json.dumps({
                    "error": error_details,
                    "properties_sent": notion_properties,
                    "page_id": page_id
                }, indent=2, ensure_ascii=False)
            ), 400

        # Success result
        updated_count = len(notion_properties)
        updated_fields = ", ".join(notion_properties.keys())
        result = {
            "success": True,
            "message": f"✅ Kontaktisiku andmed edukalt uuendatud. Uuendatud väljad: {updated_fields}.",
            "updated_fields": list(notion_properties.keys()),
            "updated_count": updated_count
        }

        # Prepare response for the user's browser (Estonian status texts)
        status_text = "Edukas"
        status_class = "success"
        message = result.get("message")
        debug_info = None

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

        return render_template_string(
            HTML_TEMPLATE,
            status="Kriitiline API viga",
            status_class="error",
            message=f"A general error occurred during API processing: {type(e).__name__}: {e}",
            redirect_url=notion_url,
            debug_info=traceback.format_exc()
        ), 500


@app.route('/api/update-staff/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {
        "status": "ok",
        "message": "Update Staff API is running",
    }


# --- Local Development Entry Point ---
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5002")
    app.run(debug=True, host='0.0.0.0', port=5002)

