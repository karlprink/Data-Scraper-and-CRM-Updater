"""
Staff data fetching from websites using Gemini.
"""
from typing import Dict, Any, List, Tuple, Optional
from ..gemini import run_full_staff_search


def fetch_staff_data(website_url: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Fetches staff data from website using Gemini.
    
    Args:
        website_url: The website URL to search
        
    Returns:
        Tuple of (staff_data, error_message)
        - If successful: (staff_data, None)
        - If failed to fetch: (None, error_message)
        - If no staff found: ([], None)
    """
    staff_data = run_full_staff_search(website_url)
    
    if staff_data is None:
        return None, "Error: Could not fetch or analyze the website content. Please check the website URL and try again."
    
    if not staff_data or len(staff_data) == 0:
        return [], None
    
    return staff_data, None

