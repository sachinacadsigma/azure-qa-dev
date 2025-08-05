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











@app.route('/')
def say_hi():
    return 'Hi! This is a service that offers both addition and translation. Use /add for addition and /translate for translation.'













    # ✅ Hardcoded Azure Blob Storage connection string
CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=sadocailibrary;AccountKey=QcIs3NdOqHRL8YVe1HoNj+0EZDnC9BBKGTU9Y3PVOgstLwvB2dpkHIMmGgOeReDWsJ0QSWh6brxa+AStMxeyUw==;EndpointSuffix=core.windows.net"
 
# Initialize blob service client
blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
 
 

 
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
       
@app.route("/blob/delete", methods=["POST"])
def delete_blob():
    data = request.get_json()
    container_name = data.get("container_name")
    blob_name = data.get("blob_name")

    if not container_name or not blob_name:
        return jsonify({"error": "Missing 'container_name' or 'blob_name'"}), 400

    try:
        blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
        blob_client.delete_blob()
        return jsonify({"message": f"Deleted blob '{blob_name}' from container '{container_name}'"}), 200
    except Exception as e:
        return jsonify({"error": f"Delete failed: {str(e)}"}), 500  

# Azure Cognitive Search configuration
SEARCH_SERVICE_NAME = "acadsigma-search-resource"
API_KEY = "aY8NB9JKH2G0MYsI0tH1hUC3w1F3wMFNjMBHSglxpeAzSeC6ugEH"
API_VERSION = "2020-06-30"

@app.route("/search/indexer/run", methods=["POST"])
def run_indexer():
    data = request.get_json()
    indexer_name = data.get("indexer_name")

    if not indexer_name:
        return jsonify({"error": "Missing 'indexer_name' in request body"}), 400

    url = f"https://{SEARCH_SERVICE_NAME}.search.windows.net/indexers/{indexer_name}/run?api-version={API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }

    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 202:
            return jsonify({"message": f"Indexer '{indexer_name}' triggered successfully"}), 202
        else:
            return jsonify({
                "error": "Failed to trigger indexer",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code
    except Exception as e:
        return jsonify({"error": f"Exception occurred: {str(e)}"}), 500
    




STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=sadocailibrary;AccountKey=QcIs3NdOqHRL8YVe1HoNj+0EZDnC9BBKGTU9Y3PVOgstLwvB2dpkHIMmGgOeReDWsJ0QSWh6brxa+AStMxeyUw==;EndpointSuffix=core.windows.net"
 



# Initialize Azure Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
from search import search_handler  # Make sure search.py is in the same folder or adjust import accordingly



@app.route("/ask", methods=["POST"])
def ask_question():
    try:
        data = request.json
        query = data.get("query")
        user_id = data.get("user_id", "default_user")  # fallback to a default user if not provided

        if not query:
            return jsonify({"error": "Missing 'query' field in request"}), 400

        result = search_handler.handle_query(query, user_id)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



#############################################################
from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient
import requests
import time



# Hardcoded constants
CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=sadocailibrary;AccountKey=QcIs3NdOqHRL8YVe1HoNj+0EZDnC9BBKGTU9Y3PVOgstLwvB2dpkHIMmGgOeReDWsJ0QSWh6brxa+AStMxeyUw==;EndpointSuffix=core.windows.net"
AZURE_SEARCH_SERVICE = "acadsigma-search-resource"
AZURE_SEARCH_KEY = "aY8NB9JKH2G0MYsI0tH1hUC3w1F3wMFNjMBHSglxpeAzSeC6ugEH"
AZURE_OPENAI_ACCOUNT = "https://open23.openai.azure.com/"
AZURE_OPENAI_KEY = "b04a94c2d9334a1a9dcbfee4bdb8fdc3"
EMBEDDING_MODEL = "text-embedding-3-large"
SKILLSET_NAME = "demo-skillset"

@app.route("/auto-index", methods=["POST"])
def auto_index():
    try:
        data = request.get_json()
        name = data["name"]

        result = create_pipeline(name)
        return jsonify(result), 200 if "error" not in result else 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_pipeline(name):
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_KEY
    }

    status = {}

    container_name = name
    data_source_name = name
    index_name = f"{name}-index"
    indexer_name = f"{name}-indexer"
    algorithm_name = f"{name}-algorithm"
    vectorizer_name = "Demo-azureOpenAi-text-vectorizer"
    vector_profile_name = f"{name}-vector-profile"
    semantic_config_name = f"{name}-semantic-config"

    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
            status["container"] = "Created"
        else:
            status["container"] = "Already exists"
    except Exception as e:
        return {"error": f"Failed to create container: {str(e)}"}

    # Data source
    base_url = f"https://{AZURE_SEARCH_SERVICE}.search.windows.net"
    ds_url = f"{base_url}/datasources/{data_source_name}?api-version=2023-11-01"
    if requests.get(ds_url, headers=headers).status_code != 200:
        ds_payload = {
            "name": data_source_name,
            "type": "azureblob",
            "credentials": {"connectionString": CONNECTION_STRING},
            "container": {"name": container_name}
        }
        resp = requests.post(f"{base_url}/datasources?api-version=2023-11-01", headers=headers, json=ds_payload)
        if resp.status_code not in [200, 201]:
            return {"error": f"Data source creation failed: {resp.text}"}
        status["data_source"] = "Created"
    else:
        status["data_source"] = "Already exists"

    # Index
    index_url = f"{base_url}/indexes/{index_name}?api-version=2024-09-01-preview"
    if requests.get(index_url, headers=headers).status_code != 200:
        index_payload = {
            "name": index_name,
            "fields": [
                {"name": "chunk_id", "type": "Edm.String", "key": True, "searchable": True, "retrievable": True, "sortable": True, "analyzer": "keyword"},
                {"name": "parent_id", "type": "Edm.String", "filterable": True, "retrievable": True},
                {"name": "chunk", "type": "Edm.String", "searchable": True, "retrievable": True},
                {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True},
                {
                    "name": "text_vector",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "retrievable": True,
                    "dimensions": 1536,
                    "vectorSearchProfile": vector_profile_name
                },
                {"name": "metadata_storage_path", "type": "Edm.String", "searchable": True, "retrievable": False}
            ],
            "similarity": {"@odata.type": "#Microsoft.Azure.Search.BM25Similarity"},
            "semantic": {
                "defaultConfiguration": semantic_config_name,
                "configurations": [
                    {
                        "name": semantic_config_name,
                        "prioritizedFields": {
                            "titleField": {"fieldName": "title"},
                            "prioritizedContentFields": [{"fieldName": "chunk"}]
                        }
                    }
                ]
            },
            "vectorSearch": {
                "algorithms": [
                    {
                        "name": algorithm_name,
                        "kind": "hnsw",
                        "hnswParameters": {"metric": "cosine", "m": 4, "efConstruction": 400, "efSearch": 500}
                    }
                ],
                "profiles": [
                    {
                        "name": vector_profile_name,
                        "algorithm": algorithm_name,
                        "vectorizer": vectorizer_name
                    }
                ],
                "vectorizers": [
                    {
                        "name": vectorizer_name,
                        "kind": "azureOpenAI",
                        "azureOpenAIParameters": {
                            "resourceUri": AZURE_OPENAI_ACCOUNT,
                            "deploymentId": EMBEDDING_MODEL,
                            "modelName": EMBEDDING_MODEL,
                            "apiKey": AZURE_OPENAI_KEY
                        }
                    }
                ]
            }
        }

        resp = requests.post(f"{base_url}/indexes?api-version=2024-09-01-preview", headers=headers, json=index_payload)
        if resp.status_code not in [200, 201]:
            return {"error": f"Index creation failed: {resp.text}"}
        status["index"] = "Created"
    else:
        status["index"] = "Already exists"

    # Indexer
    indexer_url = f"{base_url}/indexers/{indexer_name}?api-version=2024-03-01-preview"
    if requests.get(indexer_url, headers=headers).status_code != 200:
        indexer_payload = {
            "name": indexer_name,
            "dataSourceName": data_source_name,
            "skillsetName": SKILLSET_NAME,
            "targetIndexName": index_name,
            "parameters": {
                "configuration": {
                    "dataToExtract": "contentAndMetadata",
                    "parsingMode": "default",
                    "imageAction": "generateNormalizedImages"
                }
            },
            "fieldMappings": [
                {
                    "sourceFieldName": "metadata_storage_name",
                    "targetFieldName": "title"
                }
            ]
        }

        resp = requests.post(f"{base_url}/indexers?api-version=2024-03-01-preview", headers=headers, json=indexer_payload)
        if resp.status_code not in [200, 201]:
            return {"error": f"Indexer creation failed: {resp.text}"}
        status["indexer"] = "Created"
    else:
        status["indexer"] = "Already exists"

    # Wait and check indexer status
    indexer_status_url = f"{base_url}/indexers/{indexer_name}/status?api-version=2024-03-01-preview"
    time.sleep(10)
    r = requests.get(indexer_status_url, headers=headers)
    if r.status_code == 200:
        result = r.json().get("lastResult", {})
        status["indexer_run_status"] = result.get("status", "Unknown")
    else:
        status["indexer_run_status"] = f"Failed to fetch status: {r.text}"

    return status




    
if __name__ == '__main__':
    # Use the environment variable PORT, or default to port 5000 if not set
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
