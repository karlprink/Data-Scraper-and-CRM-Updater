"""
Configuration validation for staff update functionality.
"""

import os
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()


def validate_config() -> Tuple[str, str]:
    """
    Validates and returns Notion API configuration.

    Returns:
        Tuple of (api_key, database_id)

    Raises:
        ValueError: If configuration is missing
    """
    NOTION_API_KEY_CONTACTS = os.getenv("NOTION_API_KEY_CONTACTS")
    NOTION_DATABASE_ID_CONTACTS = os.getenv("NOTION_DATABASE_ID_CONTACTS")

    if not all([NOTION_API_KEY_CONTACTS, NOTION_DATABASE_ID_CONTACTS]):
        raise ValueError(
            "Missing configuration (NOTION_API_KEY_CONTACTS, NOTION_DATABASE_ID_CONTACTS)"
        )

    return NOTION_API_KEY_CONTACTS, NOTION_DATABASE_ID_CONTACTS
