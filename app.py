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
from search import search_and_answer_query
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
 
 
   
# ✅ Hardcoded Azure Blob Storage connection string
CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=sadocailibrary;AccountKey=QcIs3NdOqHRL8YVe1HoNj+0EZDnC9BBKGTU9Y3PVOgstLwvB2dpkHIMmGgOeReDWsJ0QSWh6brxa+AStMxeyUw==;EndpointSuffix=core.windows.net"
 
# Initialize blob service client
blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
 
 
from search import ask
@app.route('/ask', methods=['POST'])
def call_ask():
    return ask()
 
# === List All Containers ===
@app.route("/blob/list-containers", methods=["GET"])
def list_containers():
    try:
        containers = blob_service.list_containers()
        return jsonify({"containers": [c.name for c in containers]})
    except Exception as e:
        return jsonify({"error": f"Failed to list containers: {str(e)}"}), 500
 
# === List All Blobs in a Container ===
@app.route("/blob/list-blobs", methods=["POST"])
def list_blobs():
    data = request.get_json()
    container_name = data.get("container_name")
    if not container_name:
        return jsonify({"error": "Missing 'container_name'"}), 400
    try:
        container_client = blob_service.get_container_client(container_name)
        blobs = container_client.list_blobs()
        return jsonify({"blobs": [b.name for b in blobs]})
    except Exception as e:
        return jsonify({"error": f"Failed to list blobs: {str(e)}"}), 500
 
# === Upload File to Container ===
@app.route("/blob/upload", methods=["POST"])
def upload_blob():
    container_name = request.form.get("container_name")
    file = request.files.get("file")
    if not container_name or not file:
        return jsonify({"error": "Missing 'container_name' or file"}), 400
 
    try:
        blob_client = blob_service.get_blob_client(container=container_name, blob=file.filename)
        blob_client.upload_blob(file, overwrite=True)
        return jsonify({"message": f"Uploaded '{file.filename}' to '{container_name}'"})
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500
 
# === Download Blob from Container ===
@app.route("/blob/download", methods=["POST"])
def download_blob():
    data = request.get_json()
    container_name = data.get("container_name")
    blob_name = data.get("blob_name")
    download_path = data.get("download_path", f"./{blob_name}")
 
    if not container_name or not blob_name:
        return jsonify({"error": "Missing 'container_name' or 'blob_name'"}), 400
 
    try:
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
        with open(download_path, "wb") as file:
            file.write(blob_client.download_blob().readall())
        return jsonify({"message": f"Downloaded '{blob_name}' to '{download_path}'"})
    except Exception as e:
        return jsonify({"error": f"Download failed: {str(e)}"}), 500
       
   
if __name__ == '__main__':
    # Use the environment variable PORT, or default to port 5000 if not set
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
