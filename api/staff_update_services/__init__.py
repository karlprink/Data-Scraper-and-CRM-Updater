"""
Staff update functionality module.
"""
from .staff_config import validate_config
from .request_validator import extract_request_params, normalize_website_url
from .staff_fetcher import fetch_staff_data
from .notion_staff_service import get_database_properties, create_staff_pages
from .response_renderer import (
    render_error_response,
    render_warning_response,
    render_success_response,
    prepare_result_message
)

__all__ = [
    'validate_config',
    'extract_request_params',
    'normalize_website_url',
    'fetch_staff_data',
    'get_database_properties',
    'create_staff_pages',
    'render_error_response',
    'render_warning_response',
    'render_success_response',
    'prepare_result_message',
]

