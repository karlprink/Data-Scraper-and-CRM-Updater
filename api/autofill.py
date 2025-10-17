from flask import Flask, request, jsonify
import os
import sys

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import load_config
from sync import autofill_page_by_page_id

app = Flask(__name__)

# IMPORTANT for Vercel: the function is mounted at /api/autofill, so the route here must be '/'
@app.route('/', methods=['GET', 'POST'])
def autofill():
    try:
        # Get pageId from query parameters or JSON body
        if request.method == 'GET':
            page_id = request.args.get('pageId')
        else:  # POST
            data = request.get_json() or {}
            page_id = data.get('pageId') or request.args.get('pageId')
        
        if not page_id:
            return jsonify({"error": "No pageId provided"}), 400
        
        # Load config
        config = load_config()
        
        # Run autofill
        autofill_page_by_page_id(page_id, config)
        
        return jsonify({
            "success": True, 
            "message": "Notion page updated successfully",
            "pageId": page_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Notion Autofill API is running",
        "endpoint": "GET /?pageId=YOUR_PAGE_ID"
    })

# For Vercel deployment: exporting `app` is sufficient

# For local development
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    print("Test with: curl http://localhost:5001/api/autofill?pageId=YOUR_PAGE_ID")
    app.run(debug=True, host='0.0.0.0', port=5001)
