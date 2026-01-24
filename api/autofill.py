import traceback

from flask import Flask, request, Response, render_template_string

from .config import load_config
# Assuming these are relative imports in the project structure
from .sync import autofill_page_by_page_id

# --- Flask App Initialization ---
app = Flask(__name__)

# --- HTML Template for User Feedback (Kept in Estonian as user-facing) ---
RESULT_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Autofill Tulemus</title>
    <style>
        body { font-family: sans-serif; line-height: 1.6; padding: 20px; max-width: 600px; margin: 0 auto; }
        .card { border: 1px solid #ddd; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .success { color: #2ecc71; }
        .warning { color: #f39c12; }
        .error { color: #e74c3c; }
        h2 { margin-top: 0; }
        pre { background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="card">
        <h2 class="{{ 'success' if success else 'error' }}">
            {{ '✅ Valmis!' if success else '❌ Viga!' }}
        </h2>
        <p>{{ message }}</p>
        {% if company_name %}
            <p><strong>Ettevõte:</strong> {{ company_name }}</p>
        {% endif %}
        <hr>
        <p><small>Võid selle akna nüüd sulgeda.</small></p>
    </div>
</body>
</html>
"""


# --- API Endpoints ---


@app.route("/api/autofill", methods=["GET", "POST"])
def autofill():
    """
    Triggers the autofill process.
    Returns a minimal HTML page that automatically CLOSES THE TAB (does not keep reports on screen).
    """
    page_id = None
    config = load_config()

    try:
        if request.method == "GET":
            page_id = request.args.get("pageId")
        else:
            data = request.get_json(silent=True) or {}
            page_id = data.get("pageId") or request.args.get("pageId")

        if not page_id:
            return "Viga: pageId puudub", 400

        # Käivitame sünkroonimise
        result = autofill_page_by_page_id(page_id, config)

        return render_template_string(
            RESULT_HTML,
            success=result.get("success"),
            message=result.get("message"),
            company_name=result.get("company_name")
        )

    except Exception as e:
        err_msg = f"Kriitiline viga: {str(e)}"
        return render_template_string(RESULT_HTML, success=False, message=err_msg), 200



@app.route("/", methods=["GET"])
def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {
        "status": "ok",
        "message": "Notioni automaatse täitmise API töötab",
    }


# --- Local Development Entry Point ---
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
