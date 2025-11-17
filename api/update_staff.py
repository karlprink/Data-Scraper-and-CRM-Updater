from flask import Flask, request, render_template_string
import traceback
import json
import requests
from typing import Dict, Any, List
from gemini import run_full_staff_search
import os

# Assuming these are relative imports in the project structure
from notion_client import NotionClient
from config import load_config

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

    It loads configuration, extracts company page ID and website URL, runs Gemini to get staff information
    from the company website, creates staff member pages, and links them to the company via relation.

    Expected request format:
    - websiteUrl: The company website URL to search for staff information (required)
    - pageId: The company's Notion page ID - used to create the relation between staff members and the company (optional)
    - notionUrl: Optional redirect URL back to Notion page
    """
    page_id = None
    notion_url = None
    website_url = None

    # Load configuration from environment variables
    config = load_config()

    # Configuration validation (essential for the API to run)
    NOTION_API_KEY = os.getenv("NOTION_API_KEY_UPDATE_STAFF")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID_UPDATE_STAFF")

    if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
        error_msg = "Critical API Error: Missing configuration (NOTION_API_KEY, NOTION_DATABASE_ID). Check Vercel/Environment settings."
        return render_template_string(
            HTML_TEMPLATE,
            status="Viga",
            status_class="error",
            message=error_msg,
            debug_info=json.dumps(config, indent=2, ensure_ascii=False)
        ), 500

    try:
        # Extract page_id, notion_url, and website_url from request
        if request.method == 'GET':
            page_id = request.args.get('pageId')
            notion_url = request.args.get('notionUrl')
            website_url = request.args.get('websiteUrl')
        else:  # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId')
            notion_url = data.get('notionUrl') or request.args.get('notionUrl')
            website_url = data.get('websiteUrl') or request.args.get('websiteUrl')

        if not website_url:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Critical Error: Required 'websiteUrl' parameter is missing. Please provide the company website URL.",
                debug_info='Example: {"websiteUrl": "https://example.com"}'
            ), 400

        # Validate website URL format
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url

        # Use Gemini to find staff information
        staff_data = run_full_staff_search(website_url)

        if staff_data is None:
            return render_template_string(
                HTML_TEMPLATE,
                status="Viga",
                status_class="error",
                message="Error: Could not fetch or analyze the website content. Please check the website URL and try again.",
                redirect_url=notion_url,
                debug_info=f"Website URL: {website_url}"
            ), 400

        if not staff_data or len(staff_data) == 0:
            return render_template_string(
                HTML_TEMPLATE,
                status="Hoiatus",
                status_class="warning",
                message="⚠️ No staff information found on the website. The website may not contain contact information for the specified roles (CEO, HR Manager, Head of Marketing, Head of Sales, or General Contact).",
                redirect_url=notion_url,
                debug_info=f"Website URL: {website_url}"
            ), 200

        # Initialize Notion client
        notion = NotionClient(NOTION_API_KEY, NOTION_DATABASE_ID)

        # Get property types from database schema
        page_properties = None
        try:
            database_data = notion.get_database()
            page_properties = database_data.get("properties", {})
        except Exception as e:
            pass

        # Create a page for each staff member found
        created_count = 0
        failed_count = 0
        errors = []

        for staff_member in staff_data:
            try:
                # Map Gemini staff data to Notion properties
                properties_data = {
                    "Nimi": staff_member.get('name'),
                    "Name": staff_member.get('role'),  # Role goes in "Name" field
                    "Email": staff_member.get('email') if staff_member.get('email') else None,
                    "Telefoninumber": staff_member.get('phone') if staff_member.get('phone') else None,
                }
 
                # Add company relation if page_id is available (company page ID from request)
                if page_id:
                    properties_data["Ettevõte"] = [page_id]

                # Convert properties to Notion API format (pass page_properties to check types)
                notion_properties = _build_notion_properties(properties_data, page_properties)
                
                if not notion_properties:
                    failed_count += 1
                    errors.append(f"No valid properties for {staff_member.get('name')}")
                    continue

                # Create a new page in the database
                full_payload = {
                    "parent": {"database_id": NOTION_DATABASE_ID},
                    "properties": notion_properties
                }

                notion.create_page(full_payload)
                created_count += 1

            except requests.HTTPError as e:
                # Extract detailed error message from Notion API
                error_details = ""
                try:
                    error_response = e.response.json()
                    error_details = error_response.get("message", str(e.response.text))
                except:
                    error_details = e.response.text if hasattr(e, 'response') else str(e)
                
                failed_count += 1
                staff_name = staff_member.get('name', 'Unknown')
                errors.append(f"{staff_name}: {error_details}")

            except Exception as e:
                failed_count += 1
                staff_name = staff_member.get('name', 'Unknown')
                error_msg = f"{type(e).__name__}: {str(e)}"
                errors.append(f"{staff_name}: {error_msg}")

        # Prepare result message
        staff_found_count = len(staff_data)
        
        if created_count == 0:
            # All failed
            status_text = "Viga"
            status_class = "error"
            result_message = f"❌ Ei õnnestunud luua ühtegi kontaktisiku lehte. Leitud {staff_found_count} kontaktisikut veebilehelt."
            if errors:
                result_message += f" Vead: {'; '.join(errors[:3])}"  # Show first 3 errors
        elif failed_count > 0:
            # Partial success
            status_text = "Osaline edu"
            status_class = "warning"
            result_message = f"⚠️ Loodud {created_count} kontaktisiku lehte {staff_found_count} leitud kontaktisikust. {failed_count} ebaõnnestus."
            if errors:
                result_message += f" Vead: {'; '.join(errors[:3])}"  # Show first 3 errors
        else:
            # All succeeded
            status_text = "Edukas"
            status_class = "success"
            result_message = f"✅ Edukalt loodud {created_count} kontaktisiku lehte veebilehelt leitud kontaktisikute põhjal."

        # Prepare response for the user's browser (Estonian status texts)
        message = result_message
        debug_info = None
        if errors and len(errors) > 3:
            # Include all errors in debug info if there are many
            debug_info = json.dumps({
                "total_staff_found": staff_found_count,
                "created": created_count,
                "failed": failed_count,
                "all_errors": errors
            }, indent=2, ensure_ascii=False)

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
    app.run(debug=True, host='0.0.0.0', port=5002)

