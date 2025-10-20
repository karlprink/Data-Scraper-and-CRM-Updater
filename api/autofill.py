from flask import Flask, request, jsonify
import os
import traceback

# Use relative imports to find files in the same directory.
from .sync import autofill_page_by_page_id

app = Flask(__name__)

# This is the route that will be triggered by your Notion button.
@app.route('/api/autofill', methods=['GET', 'POST'])
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
        
        # Run autofill. The function will get its own config from env variables.
        result = autofill_page_by_page_id(page_id)
        
        return jsonify({
            "success": True, 
            "message": "Notion page updated successfully",
            "pageId": page_id,
            "debug": result
        })
        
    except Exception as e:
        # Log the full exception for debugging in Vercel
        print(f"An error occurred in the Flask endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# A simple health check to confirm the server is running.
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Notion Autofill API is running",
    })

# For local development
if __name__ == "__main__":
    print("Starting Flask API on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)

