import requests
import time
import os
import deepl
import psycopg2
from flask import Flask, request, jsonify, send_file, Response
from saml import saml_login, saml_callback, get_data_from_token
import json
from azure.storage.blob import BlobServiceClient
from storing_user_feedback import store_feedback  # Import the feedback function
from sync_logic import sync_sharepoint_to_blob
from search import search_handler
from openai import OpenAIError
app = Flask(__name__)

# DeepL API key
DEEPL_API_KEY = '82a64fae-73d4-4739-9935-bbf3cfc15010'

# Replace with your DeepL API auth key
auth_key = "82a64fae-73d4-4739-9935-bbf3cfc15010"
translator = deepl.Translator(auth_key)

app.config["SECRET_KEY"] = "onelogindemopytoolkit"
app.config["SAML_PATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saml")
# SAML routes
@app.route('/saml/login')
def login():
    return saml_login(app.config["SAML_PATH"])

@app.route('/saml/callback', methods=['POST'])
def login_callback():
    return saml_callback(app.config["SAML_PATH"])

@app.route('/data_from_token', methods=['POST'])
def data_from_token():
    data = request.get_json()
    token = data.get('token')
    return get_data_from_token(token)


@app.route('/sync-sharepoint', methods=["POST", "GET"])
def webhook_handler():
    # ✅ Microsoft Graph sends a POST with validationToken in query params
    validation_token = request.args.get("validationToken")
    if validation_token:
        print("🔐 Responding to Microsoft Graph validation request.")
        return validation_token, 200, {"Content-Type": "text/plain"}

    # ✅ Actual change notification from Graph
    if request.method == "POST":
        try:
            success = sync_sharepoint_to_blob()
            return jsonify({"status": "success" if success else "failed"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Unsupported method"}), 405





























# Initialize Azure Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    user_id = data.get("user_id", "default_user")
    try:
        result = search_handler.handle_query(data["query"], user_id)
        return jsonify(result)
    except OpenAIError as e:
        return jsonify({"error": f"OpenAI Error: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"Unhandled Exception: {str(e)}"}), 500



    
if __name__ == '__main__':
    # Use the environment variable PORT, or default to port 5000 if not set
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
