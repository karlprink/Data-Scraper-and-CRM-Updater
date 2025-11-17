"""
HTML response rendering for staff update endpoint.
"""
import json
from flask import render_template_string
from typing import Dict, Any, Optional, Union, Tuple, List

# HTML Template for User Feedback (Kept in Estonian as user-facing)
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


def prepare_result_message(
    created_count: int,
    failed_count: int,
    staff_found_count: int,
    errors: List[str]
) -> Tuple[str, str, str, Optional[Dict[str, Any]]]:
    """
    Prepares the result message and status for the response.
    
    Args:
        created_count: Number of successfully created pages
        failed_count: Number of failed page creations
        staff_found_count: Total number of staff members found
        errors: List of error messages
        
    Returns:
        Tuple of (status_text, status_class, message, debug_info)
    """
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
    
    # Prepare debug info if there are many errors
    debug_info = None
    if errors and len(errors) > 3:
        debug_info = {
            "total_staff_found": staff_found_count,
            "created": created_count,
            "failed": failed_count,
            "all_errors": errors
        }
    
    return status_text, status_class, result_message, debug_info


def render_error_response(
    status: str,
    message: str,
    notion_url: Optional[str] = None,
    debug_info: Optional[Union[str, Dict[str, Any]]] = None,
    status_code: int = 400
) -> Tuple[str, int]:
    """
    Renders an error response HTML page.
    
    Args:
        status: Status text
        message: Error message
        notion_url: Optional redirect URL
        debug_info: Optional debug information
        status_code: HTTP status code
        
    Returns:
        Tuple of (rendered HTML, status_code)
    """
    if isinstance(debug_info, dict):
        debug_info = json.dumps(debug_info, indent=2, ensure_ascii=False)
    
    return render_template_string(
        HTML_TEMPLATE,
        status=status,
        status_class="error",
        message=message,
        redirect_url=notion_url,
        debug_info=debug_info
    ), status_code


def render_warning_response(
    message: str,
    notion_url: Optional[str] = None,
    debug_info: Optional[str] = None
) -> str:
    """
    Renders a warning response HTML page.
    
    Args:
        message: Warning message
        notion_url: Optional redirect URL
        debug_info: Optional debug information
        
    Returns:
        Rendered HTML
    """
    return render_template_string(
        HTML_TEMPLATE,
        status="Hoiatus",
        status_class="warning",
        message=message,
        redirect_url=notion_url,
        debug_info=debug_info
    )


def render_success_response(
    status: str,
    status_class: str,
    message: str,
    notion_url: Optional[str] = None,
    debug_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Renders a success response HTML page.
    
    Args:
        status: Status text
        status_class: CSS class for status
        message: Success message
        notion_url: Optional redirect URL
        debug_info: Optional debug information
        
    Returns:
        Rendered HTML
    """
    debug_info_str = None
    if debug_info:
        debug_info_str = json.dumps(debug_info, indent=2, ensure_ascii=False)
    
    return render_template_string(
        HTML_TEMPLATE,
        status=status,
        status_class=status_class,
        message=message,
        redirect_url=notion_url,
        debug_info=debug_info_str
    )

