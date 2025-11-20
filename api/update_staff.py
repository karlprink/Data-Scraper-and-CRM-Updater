"""
Main Flask endpoint for updating staff/contact persons in Notion.
"""
from flask import Flask
import traceback
import json
from config import load_config
from notion_client import NotionClient

# Import service modules from staff_update_services package
from staff_update_services import (
    validate_config,
    extract_request_params,
    normalize_website_url,
    fetch_staff_data,
    get_database_properties,
    create_staff_pages,
    render_error_response,
    render_warning_response,
    render_success_response,
    prepare_result_message
)

# --- Flask App Initialization ---
app = Flask(__name__)


# --- API Endpoints ---

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
    notion_url = None
    
    try:
        # Validate configuration
        try:
            api_key, database_id = validate_config()
        except ValueError as e:
            config = load_config()
            return render_error_response(
                status="Viga",
                message=f"Critical API Error: {str(e)}. Check Vercel/Environment settings.",
                debug_info=json.dumps(config, indent=2, ensure_ascii=False),
                status_code=500
            )
        
        # Extract request parameters
        page_id, notion_url, website_url = extract_request_params()
        
        # Validate required parameters
        if not website_url:
            return render_error_response(
                status="Viga",
                message="Critical Error: Required 'websiteUrl' parameter is missing. Please provide the company website URL.",
                debug_info='Example: {"websiteUrl": "https://example.com"}',
                status_code=400
            )
        
        # Normalize website URL
        website_url = normalize_website_url(website_url)
        
        # Fetch staff data from website
        staff_data, fetch_error = fetch_staff_data(website_url)
        
        if fetch_error:
            return render_error_response(
                status="Viga",
                message=fetch_error,
                notion_url=notion_url,
                debug_info=f"Website URL: {website_url}",
                status_code=400
            )
        
        if staff_data == []:
            return render_warning_response(
                message="⚠️ No staff information found on the website. The website may not contain contact information for the specified roles (CEO, HR Manager, Head of Marketing, Head of Sales, or General Contact).",
                notion_url=notion_url,
                debug_info=f"Website URL: {website_url}"
            )
        
        # Initialize Notion client
        notion = NotionClient(api_key, database_id)
        
        # Get database properties for type checking
        page_properties = get_database_properties(notion)
        
        # Create pages for all staff members
        created_count, replaced_count, failed_count, errors = create_staff_pages(
            notion, staff_data, page_id, database_id, page_properties
        )
        
        # Prepare result message
        staff_found_count = len(staff_data)
        status_text, status_class, message, debug_info = prepare_result_message(
            created_count, replaced_count, failed_count, staff_found_count, errors
        )
        
        # Render success response
        return render_success_response(
            status=status_text,
            status_class=status_class,
            message=message,
            notion_url=notion_url,
            debug_info=debug_info
        )
        
    except Exception as e:
        traceback.print_exc()
        return render_error_response(
            status="Kriitiline API viga",
            message=f"A general error occurred during API processing: {type(e).__name__}: {e}",
            notion_url=notion_url,
            debug_info=traceback.format_exc(),
            status_code=500
        )


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
