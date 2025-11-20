"""
Notion API operations for staff/contact person management.
"""
import requests
from typing import Dict, Any, List, Tuple, Optional
from notion_client import NotionClient


def get_database_properties(notion: NotionClient) -> Optional[Dict[str, Any]]:
    """
    Gets property types from Notion database schema.
    
    Args:
        notion: The NotionClient instance
        
    Returns:
        Dictionary of property types, or None if failed
    """
    try:
        database_data = notion.get_database()
        return database_data.get("properties", {})
    except Exception:
        return None


def find_existing_staff_pages(
    notion: NotionClient,
    role: str,
    company_page_id: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Finds existing staff pages with the same role and company.
    
    Args:
        notion: The NotionClient instance
        role: The role to search for (e.g., "CEO", "HR Manager")
        company_page_id: Optional company page ID to filter by
        
    Returns:
        List of existing page objects
    """
    try:
        # Build filter conditions
        filters = []
        
        # Filter by role (Name field is a title)
        filters.append({
            "property": "Name",
            "title": {"equals": role}
        })
        
        # Filter by company if provided
        if company_page_id:
            filters.append({
                "property": "Ettevõte",
                "relation": {"contains": company_page_id}
            })
        
        # Combine filters with AND
        if len(filters) == 1:
            filter_dict = filters[0]
        else:
            filter_dict = {
                "and": filters
            }
        
        # Query the database
        existing_pages = notion.query_database(filter_dict)
        
        # Filter out archived pages
        active_pages = [page for page in existing_pages if not page.get("archived", False)]
        
        return active_pages
    except Exception:
        # If query fails, return empty list (safer to create new than fail)
        return []


def map_staff_to_properties(staff_member: Dict[str, Any], page_id: Optional[str]) -> Dict[str, Any]:
    """
    Maps Gemini staff data to Notion property format.
    
    Args:
        staff_member: Staff member data from Gemini
        page_id: Optional company page ID for relation
        
    Returns:
        Dictionary of Notion properties
    """
    properties_data = {
        "Nimi": staff_member.get('name'),
        "Name": staff_member.get('role'),  # Role goes in "Name" field
        "Email": staff_member.get('email') if staff_member.get('email') else None,
        "Telefoninumber": staff_member.get('phone') if staff_member.get('phone') else None,
    }
    
    # Add company relation if page_id is available
    if page_id:
        properties_data["Ettevõte"] = [page_id]
    
    return properties_data


def build_notion_properties(properties_data: Dict[str, Any], page_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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


def create_staff_page(
    notion: NotionClient,
    staff_member: Dict[str, Any],
    page_id: Optional[str],
    database_id: str,
    page_properties: Optional[Dict[str, Any]]
) -> Tuple[bool, Optional[str], bool]:
    """
    Creates a single staff member page in Notion.
    If a page with the same role and company already exists, it will be deleted first.
    
    Args:
        notion: The NotionClient instance
        staff_member: Staff member data from Gemini
        page_id: Optional company page ID for relation
        database_id: The Notion database ID
        page_properties: Optional database property types
        
    Returns:
        Tuple of (success, error_message, was_replaced)
        - success: True if page was created successfully
        - error_message: Error message if creation failed, None otherwise
        - was_replaced: True if an existing page was deleted before creating, False if it's a new page
    """
    was_replaced = False
    
    try:
        # Get the role from staff member data
        role = staff_member.get('role')
        
        # Check for existing pages with the same role and company
        # Only do deduplication if we have both role and company page_id
        if role and page_id:
            existing_pages = find_existing_staff_pages(notion, role, page_id)
            
            # Delete existing pages to prevent duplicates
            for existing_page in existing_pages:
                try:
                    page_id_to_delete = existing_page.get('id')
                    if page_id_to_delete:
                        notion.delete_page(page_id_to_delete)
                        was_replaced = True
                except Exception as e:
                    # Log error but continue - we'll still try to create the new page
                    pass
        
        # Map Gemini staff data to Notion properties
        properties_data = map_staff_to_properties(staff_member, page_id)
        
        # Convert properties to Notion API format
        notion_properties = build_notion_properties(properties_data, page_properties)
        
        if not notion_properties:
            return False, f"No valid properties for {staff_member.get('name')}", was_replaced
        
        # Create a new page in the database
        full_payload = {
            "parent": {"database_id": database_id},
            "properties": notion_properties
        }
        
        notion.create_page(full_payload)
        return True, None, was_replaced
        
    except requests.HTTPError as e:
        # Extract detailed error message from Notion API
        error_details = ""
        try:
            error_response = e.response.json()
            error_details = error_response.get("message", str(e.response.text))
        except:
            error_details = e.response.text if hasattr(e, 'response') else str(e)
        
        staff_name = staff_member.get('name', 'Unknown')
        return False, f"{staff_name}: {error_details}", was_replaced
        
    except Exception as e:
        staff_name = staff_member.get('name', 'Unknown')
        error_msg = f"{type(e).__name__}: {str(e)}"
        return False, f"{staff_name}: {error_msg}", was_replaced


def create_staff_pages(
    notion: NotionClient,
    staff_data: List[Dict[str, Any]],
    page_id: Optional[str],
    database_id: str,
    page_properties: Optional[Dict[str, Any]]
) -> Tuple[int, int, int, List[str]]:
    """
    Creates pages for all staff members.
    If pages with the same role and company already exist, they will be replaced.
    
    Args:
        notion: The NotionClient instance
        staff_data: List of staff member data
        page_id: Optional company page ID for relation
        database_id: The Notion database ID
        page_properties: Optional database property types
        
    Returns:
        Tuple of (created_count, replaced_count, failed_count, errors)
        - created_count: Number of successfully created pages
        - replaced_count: Number of pages that replaced existing ones
        - failed_count: Number of failed creations
        - errors: List of error messages
    """
    created_count = 0
    replaced_count = 0
    failed_count = 0
    errors = []
    
    for staff_member in staff_data:
        success, error_msg, was_replaced = create_staff_page(
            notion, staff_member, page_id, database_id, page_properties
        )
        
        if success:
            created_count += 1
            if was_replaced:
                replaced_count += 1
        else:
            failed_count += 1
            if error_msg:
                errors.append(error_msg)
    
    return created_count, replaced_count, failed_count, errors

