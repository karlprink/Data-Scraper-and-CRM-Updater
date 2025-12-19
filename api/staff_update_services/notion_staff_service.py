"""
Notion API operations for staff/contact person management.
"""

import requests
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
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
        # Use contains since role may have tags like "(Lisatud ...)" or "(uuendatud ...)"
        if role:
            filters.append({"property": "Name", "title": {"contains": role}})

        # 3. Filter by company relation if provided (Property: Ettevõte)
        if company_page_id:
            filters.append(
                {"property": "Ettevõte", "relation": {"contains": company_page_id}}
            )

        if len(filters) < 2:  # Nimi ja Roll on kriitilised
            return None

        filter_dict = {"and": filters}

        # Query the database
        existing_pages = notion.query_database(filter_dict)

        # Filter out archived pages and return the first active match
        for page in existing_pages:
            if not page.get("archived", False):
                logging.info(
                    f"Existing contact found: {name} ({role}), Page ID: {page.get('id')}"
                )
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
            notion_properties[prop_name] = {"phone_number": prop_value}

        # Handle Relation (Ettevõte)
        elif prop_name == "Ettevõte" or prop_name == "Company":
            # Expect single page ID string for company relation (assuming 1 company per contact)
            if isinstance(prop_value, str):
                notion_properties[prop_name] = {"relation": [{"id": prop_value}]}
            elif isinstance(prop_value, list):
                relation_list = [
                    {"id": item} for item in prop_value if isinstance(item, str)
                ]
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
) -> Tuple[int, int, int, int, List[str]]:
    """
    Synchronizes staff members with the following logic:
    1. If Role name AND person's name is the same → update existing instance
    2. If Role exists BUT name is different → create new instance with "uuendatud" tag, mark old as "AEGUNUD"
    3. If role doesn't exist → just add it
    """
    created_count = 0
    updated_count = 0
    failed_count = 0
    skipped_count = 0
    errors = []

    current_date_est = datetime.now().strftime("%d.%m.%Y")

    for staff_member in staff_data:
        person_name = staff_member.get("name")
        person_role = staff_member.get("role")

        if not person_name or not person_role:
            failed_count += 1
            errors.append(f"Puudulikud andmed: Nimi või Roll puudub. ({staff_member})")
            continue

        try:
            # Step 1: Check if exact match exists (same name AND same role)
            existing_page = find_staff_page_by_name_and_role(
                notion, person_name, person_role, page_id
            )

            current_staff_member_data = staff_member.copy()

            if existing_page:
                # Case 1: Same name AND same role → UPDATE existing instance
                existing_flat_data = extract_notion_properties_for_comparison(
                    existing_page
                )

                # Check if any data has changed (email, phone)
                email_changed = current_staff_member_data.get(
                    "email"
                ) != existing_flat_data.get("Email")
                phone_changed = current_staff_member_data.get(
                    "phone"
                ) != existing_flat_data.get("Telefoninumber")

                if email_changed or phone_changed:
                    properties_data = map_staff_to_properties(
                        current_staff_member_data, page_id
                    )
                    notion_properties = build_notion_properties(
                        properties_data, page_properties
                    )

                    existing_page_id = existing_page.get("id")
                    notion.update_page(existing_page_id, notion_properties)
                    updated_count += 1
                    logging.info(
                        f"Updated existing contact (same name & role, data changed): {person_name} ({person_role})"
                    )
                else:
                    skipped_count += 1
                    logging.info(
                        f"Existing contact is up-to-date: {person_name} ({person_role}). Skipping update."
                    )

            else:
                # Step 2: Check if role exists with different name
                existing_role_page = find_staff_page_by_role_only(
                    notion, person_role, page_id, exclude_aegunud=True
                )

                if existing_role_page:
                    # Case 2: Role exists BUT name is different
                    existing_flat_data = extract_notion_properties_for_comparison(
                        existing_role_page
                    )
                    existing_name = existing_flat_data.get("Nimi")
                    existing_role = existing_flat_data.get("Name")
                    
                    if existing_name and existing_name != person_name:
                        # Mark old instance as AEGUNUD
                        old_page_id = existing_role_page.get("id")
                        mark_page_as_aegunud(notion, old_page_id, existing_role or person_role)
                        
                        # Create new instance with "uuendatud" tag
                        new_role = f"{person_role} (uuendatud {current_date_est})"
                        current_staff_member_data["role"] = new_role

                        properties_data = map_staff_to_properties(
                            current_staff_member_data, page_id
                        )
                        notion_properties = build_notion_properties(
                            properties_data, page_properties
                        )

                        if not notion_properties:
                            failed_count += 1
                            errors.append(
                                f"Väljade kaardistamise viga: Andmeid ei saanud vormindada ({person_name}, {person_role})"
                            )
                            continue

                        full_payload = {
                            "parent": {"database_id": database_id},
                            "properties": notion_properties,
                        }
                        notion.create_page(full_payload)
                        created_count += 1
                        logging.info(
                            f"Created new contact (role existed with different name): {person_name} ({person_role}). Old instance marked as AEGUNUD."
                        )
                    else:
                        # Role exists but name is same (shouldn't happen, but handle it)
                        # This means we found a page but name matches - update it
                        properties_data = map_staff_to_properties(
                            current_staff_member_data, page_id
                        )
                        notion_properties = build_notion_properties(
                            properties_data, page_properties
                        )

                        existing_page_id = existing_role_page.get("id")
                        notion.update_page(existing_page_id, notion_properties)
                        updated_count += 1
                        logging.info(
                            f"Updated existing contact: {person_name} ({person_role})"
                        )
                else:
                    # Case 3: Role doesn't exist → just add it
                    new_role = f"{person_role} (Lisatud {current_date_est})"
                    current_staff_member_data["role"] = new_role

                    properties_data = map_staff_to_properties(
                        current_staff_member_data, page_id
                    )
                    notion_properties = build_notion_properties(
                        properties_data, page_properties
                    )

                    if not notion_properties:
                        failed_count += 1
                        errors.append(
                            f"Väljade kaardistamise viga: Andmeid ei saanud vormindada ({person_name}, {person_role})"
                        )
                        continue

                    full_payload = {
                        "parent": {"database_id": database_id},
                        "properties": notion_properties,
                    }
                    notion.create_page(full_payload)
                    created_count += 1
                    logging.info(
                        f"Created new contact (role doesn't exist): {person_name} ({person_role})"
                    )

        except requests.HTTPError as e:
            error_details = e.response.json().get("message", str(e.response.text))
            failed_count += 1
            errors.append(
                f"{person_name} ({person_role}) Notion API viga: {error_details}"
            )

        except Exception as e:
            failed_count += 1
            errors.append(
                f"{person_name} ({person_role}) üldine viga: {type(e).__name__}: {str(e)}"
            )

    return created_count, updated_count, failed_count, skipped_count, errors


def extract_notion_properties_for_comparison(page: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts key property values (flat format) from a Notion page object for comparison.
    This helps in comparing existing data with newly scraped data.
    """
    properties = page.get("properties", {})
    extracted = {}

    nimi_prop = properties.get("Nimi", {})
    if nimi_prop.get("type") == "rich_text" and nimi_prop.get("rich_text"):
        extracted["Nimi"] = nimi_prop["rich_text"][0].get("plain_text")
    else:
        extracted["Nimi"] = None

    name_prop = properties.get("Name", {})
    if name_prop.get("type") == "title" and name_prop.get("title"):
        extracted["Name"] = name_prop["title"][0].get("plain_text")
    else:
        extracted["Name"] = None

    email_prop = properties.get("Email", {})
    if email_prop.get("type") == "email":
        extracted["Email"] = email_prop.get("email")
    else:
        extracted["Email"] = None

    phone_prop = properties.get("Telefoninumber", {})
    if phone_prop.get("type") == "phone_number":
        extracted["Telefoninumber"] = phone_prop.get("phone_number")
    else:
        extracted["Telefoninumber"] = None

    return extracted


def find_staff_page_by_role_only(
    notion: NotionClient, 
    role: str, 
    company_page_id: Optional[str] = None,
    exclude_aegunud: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Finds an existing staff page by role only (to check if role exists with different name).
    Uses contains filter since roles may have tags like "(Lisatud ...)" or "(uuendatud ...)".
    Excludes pages marked as AEGUNUD by default.

    Args:
        notion: The NotionClient instance
        role: The role/title (Value in 'Name' field) - base role name without tags
        company_page_id: Optional company page ID to filter by
        exclude_aegunud: If True, excludes pages with "AEGUNUD" in the Name field

    Returns:
        The existing page object, or None
    """
    try:
        filters = []

        # Filter by role (Property: Name/Title) - use contains since role may have tags
        if role:
            filters.append({"property": "Name", "title": {"contains": role}})

        if company_page_id:
            filters.append(
                {"property": "Ettevõte", "relation": {"contains": company_page_id}}
            )

        if not filters:
            return None

        filter_dict = {"and": filters} if len(filters) > 1 else filters[0]

        existing_pages = notion.query_database(filter_dict)

        # Filter out archived pages and AEGUNUD pages
        for page in existing_pages:
            if page.get("archived", False):
                continue
            
            # Check if page is marked as AEGUNUD
            if exclude_aegunud:
                page_props = page.get("properties", {})
                name_prop = page_props.get("Name", {})
                if name_prop.get("type") == "title" and name_prop.get("title"):
                    name_text = name_prop["title"][0].get("plain_text", "")
                    if "AEGUNUD" in name_text.upper():
                        continue
            
            logging.info(
                f"Existing contact found by role: {role}, Page ID: {page.get('id')}"
            )
            return page

        return None

    except Exception as e:
        logging.error(
            f"Error querying Notion database for existing staff by role: {e}"
        )
        return None


def mark_page_as_aegunud(notion: NotionClient, page_id: str, current_role: str) -> bool:
    """
    Marks a page as AEGUNUD by adding "AEGUNUD" tag to the Name field.

    Args:
        notion: The NotionClient instance
        page_id: The page ID to mark
        current_role: The current role text (to preserve it)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Remove any existing tags and add AEGUNUD
        # Extract base role (remove any existing tags like "AEGUNUD", "uuendatud", dates, etc.)
        base_role = current_role
        # Remove common tags and dates
        for tag in ["AEGUNUD", "uuendatud", "Lisatud"]:
            base_role = base_role.replace(tag, "").strip()
        # Remove date patterns like (dd.mm.yyyy)
        base_role = re.sub(r'\s*\([^)]*\)\s*', '', base_role).strip()
        
        # Add AEGUNUD tag
        new_role = f"{base_role} AEGUNUD"
        
        notion_properties = {
            "Name": {
                "title": [{"text": {"content": new_role}}]
            }
        }
        
        notion.update_page(page_id, notion_properties)
        logging.info(f"Marked page {page_id} as AEGUNUD")
        return True
    except Exception as e:
        logging.error(f"Error marking page as AEGUNUD: {e}")
        return False
