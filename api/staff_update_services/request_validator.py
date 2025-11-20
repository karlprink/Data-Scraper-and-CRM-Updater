"""
Request parameter extraction and validation for staff update endpoint.
"""
from flask import request
from typing import Tuple, Optional


def extract_request_params() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extracts page_id, notion_url, and website_url from the request.
    Supports both GET and POST methods.
    
    Returns:
        Tuple of (page_id, notion_url, website_url)
    """
    if request.method == 'GET':
        page_id = request.args.get('pageId')
        notion_url = request.args.get('notionUrl')
        website_url = request.args.get('websiteUrl')
    else:  # POST
        data = request.get_json() or {}
        page_id = data.get('pageId') or request.args.get('pageId')
        notion_url = data.get('notionUrl') or request.args.get('notionUrl')
        website_url = data.get('websiteUrl') or request.args.get('websiteUrl')
    
    return page_id, notion_url, website_url


def normalize_website_url(website_url: str) -> str:
    """
    Normalizes website URL by adding https:// if missing.
    
    Args:
        website_url: The website URL to normalize
        
    Returns:
        Normalized URL with protocol
    """
    if not website_url.startswith(('http://', 'https://')):
        return 'https://' + website_url
    return website_url

