"""
Notion API operations for staff/contact person management.
"""

import requests
from typing import Dict, Any, List, Tuple, Optional
from ..clients.notion_client import NotionClient
import logging

logging.basicConfig(level=logging.INFO)


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
    except Exception as e:
        logging.error(f"Failed to fetch database properties: {e}")
        return None


def find_staff_page_by_name_and_role(
    notion: NotionClient, name: str, role: str, company_page_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Finds a single existing staff page by the person's name, role, and company.
    This ensures that contacts are identified by the unique combination of (Name, Role).

    Args:
        notion: The NotionClient instance
        name: The person's name (Value in 'Nimi' field)
        role: The role/title (Value in 'Name' field)
        company_page_id: Optional company page ID to filter by

    Returns:
        The existing page object, or None
    """
    try:
        # Build filter conditions
        filters = []

        # 1. Filter by person's name (Property: Nimi)
        if name:
             # Nimi on Rich Text: Eeldab täpset vastet
             filters.append({"property": "Nimi", "rich_text": {"equals": name}})

        # 2. Filter by role (Property: Name/Title)
        if role:
             # Name on Title: Eeldab täpset vastet
             filters.append({"property": "Name", "title": {"equals": role}})

        # 3. Filter by company relation if provided (Property: Ettevõte)
        if company_page_id:
            filters.append(
                {"property": "Ettevõte", "relation": {"contains": company_page_id}}
            )

        if len(filters) < 2: # Nimi ja Roll on kriitilised
            return None

        filter_dict = {"and": filters}

        # Query the database
        existing_pages = notion.query_database(filter_dict)

        # Filter out archived pages and return the first active match
        for page in existing_pages:
            if not page.get("archived", False):
                logging.info(f"Existing contact found: {name} ({role}), Page ID: {page.get('id')}")
                return page

        return None

    except Exception as e:
        logging.error(f"Error querying Notion database for existing staff: {e}")
        return None


def map_staff_to_properties(
    staff_member: Dict[str, Any], page_id: Optional[str]
) -> Dict[str, Any]:
    """
    Maps Gemini staff data to Notion property format (flat dictionary).

    Args:
        staff_member: Staff member data from Gemini
        page_id: Optional company page ID for relation

    Returns:
        Dictionary of Notion properties
    """
    properties_data = {
        "Nimi": staff_member.get("name"),
        "Name": staff_member.get("role"),
        "Email": staff_member.get("email") if staff_member.get("email") else None,
        "Telefoninumber": (
            staff_member.get("phone") if staff_member.get("phone") else None
        ),
    }

    # Add company relation if page_id is available
    if page_id:
        # Ettevõte relation expects the company page ID
        properties_data["Ettevõte"] = page_id

    return properties_data


def build_notion_properties(
    properties_data: Dict[str, Any], page_properties: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Converts flat property data into Notion API property format.

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
            notion_properties[prop_name] = {"email": prop_value}

        # Handle Phone Number
        elif prop_name == "Telefoninumber" or prop_name == "Phone":
            notion_properties[prop_name] = {
                "phone_number": prop_value
            }

        # Handle Relation (Ettevõte)
        elif prop_name == "Ettevõte" or prop_name == "Company":
            # Expect single page ID string for company relation (assuming 1 company per contact)
            if isinstance(prop_value, str):
                notion_properties[prop_name] = {"relation": [{"id": prop_value}]}
            elif isinstance(prop_value, list):
                 relation_list = [{"id": item} for item in prop_value if isinstance(item, str)]
                 if relation_list:
                     notion_properties[prop_name] = {"relation": relation_list}


        # Handle Rich Text (for any other text fields)
        elif isinstance(prop_value, str):
            notion_properties[prop_name] = {
                "rich_text": [{"text": {"content": prop_value}}]
            }

    return notion_properties


def sync_staff_data(
    notion: NotionClient,
    staff_data: List[Dict[str, Any]],
    page_id: Optional[str],
    database_id: str,
    page_properties: Optional[Dict[str, Any]],
) -> Tuple[int, int, int, List[str]]:
    """
    Synchronizes staff members: finds existing by (Name, Role) to update,
    otherwise creates a new page.
    """
    created_count = 0
    updated_count = 0
    failed_count = 0
    errors = []


    for staff_member in staff_data:
        person_name = staff_member.get("name")
        person_role = staff_member.get("role")

        if not person_name or not person_role:
            failed_count += 1
            errors.append(f"Puudulikud andmed: Nimi või Roll puudub. ({staff_member})")
            continue

        try:
            existing_page = find_staff_page_by_name_and_role(
                notion, person_name, person_role, page_id
            )

            # Map Gemini staff data to Notion properties (Flat format)
            properties_data = map_staff_to_properties(staff_member, page_id)

            # Convert properties to Notion API format
            notion_properties = build_notion_properties(properties_data, page_properties)

            if not notion_properties:
                failed_count += 1
                errors.append(f"Väljade kaardistamise viga: Andmeid ei saanud vormindada ({person_name}, {person_role})")
                continue

            if existing_page:
                existing_page_id = existing_page.get("id")
                notion.update_page(existing_page_id, notion_properties)
                updated_count += 1
                logging.info(f"Updated existing contact: {person_name} ({person_role})")
            else:
                full_payload = {
                    "parent": {"database_id": database_id},
                    "properties": notion_properties,
                }
                notion.create_page(full_payload)
                created_count += 1
                logging.info(f"Created new contact: {person_name} ({person_role})")

        except requests.HTTPError as e:
            error_details = e.response.json().get("message", str(e.response.text))
            failed_count += 1
            errors.append(f"{person_name} ({person_role}) Notion API viga: {error_details}")

        except Exception as e:
            failed_count += 1
            errors.append(f"{person_name} ({person_role}) üldine viga: {type(e).__name__}: {str(e)}")

    return created_count, updated_count, failed_count, errors
