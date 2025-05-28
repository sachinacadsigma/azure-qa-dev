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
    

# Database connection details
DB_CONFIG = {
    'dbname': 'settings_db',
    'user': 'citus',
    'password': 'password@123',
    'host': 'c-settings-details.4frco7jk32qfsk.postgres.cosmos.azure.com',
    'port': '5432'
}


# Language mapping
language_mapping = {
    "Arabic": "AR",
    "Bulgarian": "BG",
    "Czech": "CS",
    "Danish": "DA",
    "German": "DE",
    "Greek": "EL",
    "English": "EN",  # General English
    "English (British)": "EN-GB",
    "English (American)": "EN-US",
    "Spanish": "ES",
    "Estonian": "ET",
    "Finnish": "FI",
    "French": "FR",
    "Hungarian": "HU",
    "Indonesian": "ID",
    "Italian": "IT",
    "Japanese": "JA",
    "Korean": "KO",
    "Lithuanian": "LT",
    "Latvian": "LV",
    "Norwegian Bokmål": "NB",
    "Dutch": "NL",
    "Polish": "PL",
    "Portuguese": "PT",  # General Portuguese
    "Portuguese (Brazilian)": "PT-BR",
    "Portuguese (European)": "PT-PT",
    "Romanian": "RO",
    "Russian": "RU",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Swedish": "SV",
    "Turkish": "TR",
    "Ukrainian": "UK",
    "Chinese": "ZH",  # General Chinese
    "Chinese (Simplified)": "ZH-HANS",
    "Chinese (Traditional)": "ZH-HANT"
}


def translate_text(text, target_lang_name, source_lang_name=None, formality='default', preserve_formatting=True):
    # Validate required parameters
    if not text or not target_lang_name:
        raise ValueError("Missing required parameters: 'text' and 'target_lang'.")

    # Convert language names to codes
    source_lang = language_mapping.get(source_lang_name) if source_lang_name else None
    target_lang = language_mapping.get(target_lang_name)

    if target_lang is None:
        raise ValueError(f"Invalid target language: '{target_lang_name}'. Please provide a valid language name.")

    try:
        # Perform the translation
        result = translator.translate_text(
            text,
            source_lang=source_lang,
            target_lang=target_lang,
            formality=formality,
            preserve_formatting=preserve_formatting
        )

        # Return the translated text
        return result.text

    except Exception as e:
        raise RuntimeError(f"Translation failed: {str(e)}")

def translate_document(file, source_lang, target_lang):
    # Convert language names to language codes
    source_lang_code = language_mapping.get(source_lang, 'EN')  # Default to English if not found
    target_lang_code = language_mapping.get(target_lang, 'FR')  # Default to French if not found

    # Step 1: Submit the document to DeepL for translation
    url = "https://api.deepl.com/v2/document"
    data = {
        'auth_key': DEEPL_API_KEY,
        'source_lang': source_lang_code,
        'target_lang': target_lang_code
    }
    files = {
        'file': (file.filename, file.stream, file.content_type)
    }

    response = requests.post(url, data=data, files=files)

    if response.status_code != 200:
        return None, None, f"Error submitting document: {response.status_code}, {response.text}"

    # Extract document_id and document_key
    json_response = response.json()
    document_id = json_response.get('document_id')
    document_key = json_response.get('document_key')

    if not document_id or not document_key:
        return None, None, "Error: document_id or document_key missing in response"

    # Step 2: Check the translation status until it's done
    status_url = f"https://api.deepl.com/v2/document/{document_id}"
    status_params = {
        'auth_key': DEEPL_API_KEY,
        'document_key': document_key
    }

    while True:
        status_response = requests.get(status_url, params=status_params)
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data['status'] == 'done':
                break  # Translation is complete!
            elif status_data['status'] == 'error':
                return None, None, "Error during translation"
        else:
            return None, None, f"Error checking status: {status_response.status_code}, {status_response.text}"

        time.sleep(5)  # Wait before checking again

    # Step 3: Download the translated document
    download_url = f"https://api.deepl.com/v2/document/{document_id}/result"
    download_params = {
        'auth_key': DEEPL_API_KEY,
        'document_key': document_key
    }
    download_response = requests.get(download_url, params=download_params)

    if download_response.status_code == 200:
        translated_file_name = f"translated_{document_id}.docx"
        with open(translated_file_name, 'wb') as f:
            f.write(download_response.content)
        return translated_file_name, download_response.content, None
    else:
        return None, None, f"Error downloading document: {download_response.status_code}, {download_response.text}"


# Function to connect to the database
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None


def test_api_key(auth_key):
    # Hardcoded values inside the function
    text = "Hello, how are you?"  # Text to be translated
    target_language = "French"    # Target language for translation
    source_language = "English"   # Source language for translation
    formality = 'default'         # Optional formality parameter
    preserve_formatting = True    # Optional formatting preservation
    
    # Language mapping
    language_mapping = {
        "English": "EN",
        "French": "FR"
    }

    # Validate the provided API key
    if not auth_key:
        raise ValueError("Missing required parameter: 'auth_key'.")

    # Initialize the DeepL translator with the provided API key
    translator = deepl.Translator(auth_key)

    # Get language codes from hardcoded names
    source_lang = language_mapping.get(source_language)
    target_lang = language_mapping.get(target_language)

    try:
        # Perform translation using DeepL API
        result = translator.translate_text(
            text,
            source_lang=source_lang,
            target_lang=target_lang,
            formality=formality if formality != 'default' else None,
            preserve_formatting=preserve_formatting
        )
        return result.text
    except deepl.DeepLException as e:
        raise RuntimeError(f"Translation failed: {str(e)}")







@app.route('/')
def say_hi():
    return 'Hi! This is a service that offers both addition and translation. Use /add for addition and /translate for translation.'

@app.route('/add', methods=['POST'])
def add_numbers():
    # Get JSON data from the request
    data = request.get_json()
    
    # Extract numbers from the JSON data
    num1 = data.get('num1')
    num2 = data.get('num2')
    
    # Check if both numbers are provided and are valid
    if num1 is None or num2 is None:
        return jsonify({'error': 'Please provide both num1 and num2'}), 400
    if not isinstance(num1, (int, float)) or not isinstance(num2, (int, float)):
        return jsonify({'error': 'Both num1 and num2 must be numbers'}), 400

    # Perform addition
    result = num1 + num2

    # Return the result as JSON
    return jsonify({'result': result})

# Route for translation service
@app.route('/translate', methods=['POST'])
def translate():
    # Get JSON data from the request
    data = request.get_json()

    # Extract text and languages from the JSON data
    text = data.get('text')
    target_language = data.get('target_language')
    source_language = data.get('source_language', None)

    if not text or not target_language:
        return jsonify({'error': 'Please provide text and target_language'}), 400

    # Optional formality and formatting preservation flags
    formality = data.get('formality', 'prefer_more')
    preserve_formatting = data.get('preserve_formatting', True)

    try:
        # Perform translation
        translated_text = translate_text(text, target_language, source_language, formality, preserve_formatting)
        return jsonify({'translated_text': translated_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/document-translate', methods=['POST'])
def document_translate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    source_lang = request.form.get('source_lang', 'English')  # Default source language to English
    target_lang = request.form.get('target_lang', 'French')  # Default target language to French

    # Call the function to translate the document
    translated_file_name, translated_content, error = translate_document(file, source_lang, target_lang)

    if error:
        return jsonify({'error': error}), 500

    # Send the translated file to the user
    return send_file(translated_file_name, as_attachment=True)


@app.route('/save_settings_deepl', methods=['POST'])
def save_settings_deepl():
    # Check if the required form data is present
    if 'admin_id' not in request.form or 'api_key' not in request.form:
        return jsonify({"error": "Missing admin_id or api_key"}), 400

    admin_id = request.form['admin_id']
    api_key = request.form['api_key']

    # Insert data into the database
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()

        # SQL query to insert admin_id and api_key into the deepl_settings table
        query = """
        INSERT INTO deepl_settings (admin_id, api_key)
        VALUES (%s, %s)
        ON CONFLICT (admin_id) DO UPDATE
        SET api_key = EXCLUDED.api_key;
        """

        cursor.execute(query, (admin_id, api_key))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Settings saved successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/test_translation', methods=['POST'])
def test_translation():
    # Get the inputs from form-data or query parameters
    key = request.form.get('key')  # Azure Translator API key
    text_translation_endpoint = request.form.get('endpoint')  # Translator service endpoint URL
    region = request.form.get('region')  # Azure region

    # Hardcoded values for translation
    source_language_code = "en"  # English as source language
    target_language_code = "es"  # Spanish as target language
    text_to_translate = "This is a test"  # Text to translate

    # Check if key, endpoint, and region are provided
    if not key or not text_translation_endpoint or not region:
        return jsonify({"error": "API key, endpoint, and region are required."}), 400

    # Construct the Azure Translator API URL
    path = 'translate'
    constructed_url = f"{text_translation_endpoint}/{path}"

    # Setup the query parameters and headers
    params = {
        'api-version': '3.0',
        'from': source_language_code,
        'to': target_language_code
    }

    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-Type': 'application/json'
    }

    # Body of the request with the hardcoded text to be translated
    body = [{'text': text_to_translate}]

    try:
        # Make the request to the Azure Translator API
        response = requests.post(constructed_url, params=params, headers=headers, json=body)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        # Parse the response JSON
        response_json = response.json()

        # Return the JSON response from the API
        return jsonify(response_json), 200

    except requests.exceptions.HTTPError as http_err:
        # Catch HTTP errors from the API call
        return jsonify({"error": f"HTTP error occurred: {http_err}"}), 500
    except Exception as e:
        # Catch any other errors
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


# Hardcoded source document URL, source language, and target language
SOURCE_DOCUMENT_URL = "https://devaitranslationstorage.blob.core.windows.net/source/Body%20is%20the%20temple.docx?sp=r&st=2024-10-10T13:21:05Z&se=2026-02-25T21:21:05Z&spr=https&sv=2022-11-02&sr=b&sig=TUldqtSd0ljLMMOzrMnrot0FzBI7r0uwz%2BnDKkpntRc%3D"
TARGET_DOCUMENT_URL = "https://devaitranslationstorage.blob.core.windows.net/translated/translated_doc_es.docx"
SOURCE_LANGUAGE_CODE = "en"  # English as source language
TARGET_LANGUAGE_CODE = "es"  # Spanish as target language

@app.route('/translate_document', methods=['POST'])
def translate_document():
    # Get key, endpoint, and region from request
    key = request.form.get('key')
    text_translation_endpoint = request.form.get('endpoint')
    region = request.form.get('region')

    # Validate key, endpoint, and region
    if not key or not text_translation_endpoint or not region:
        return jsonify({"error": "API key, endpoint, and region are required."}), 400

    # Construct the Azure Document Translation API URL
    constructed_url = f"{text_translation_endpoint}/translator/text/batch/v1.0/batches"

    # Setup the request body and headers with hardcoded URLs and languages
    body = {
        "inputs": [
            {
                "source": {
                    "sourceUrl": SOURCE_DOCUMENT_URL,
                    "language": SOURCE_LANGUAGE_CODE
                },
                "targets": [
                    {
                        "targetUrl": TARGET_DOCUMENT_URL,
                        "language": TARGET_LANGUAGE_CODE
                    }
                ]
            }
        ]
    }

    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-Type': 'application/json'
    }

    try:
        # Make the request to the Azure Document Translation API
        response = requests.post(constructed_url, headers=headers, json=body)

        # Log the status code and response text
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)

        # Raise an error for bad responses
        response.raise_for_status()

        # If the request is successful, return success message
        return jsonify({"success": True, "message": "Document translation started successfully."}), 200

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return jsonify({"error": f"HTTP error occurred: {http_err}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

def validate_connection_string(connection_string):
    try:
        # Attempt to create BlobServiceClient with the provided connection string
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        # Try to list containers to validate the connection
        containers = blob_service_client.list_containers()
        for container in containers:
            pass  # Just to iterate and check if we can access containers
        return True
    except Exception as e:
        print(f"Connection string validation failed: {str(e)}")
        return False

# Route to validate the connection string separately
@app.route('/validate_connection_string', methods=['POST'])
def validate_connection_string_route():
    # Extract connection string from request
    connection_string = request.form.get('connection_string')

    # Ensure connection string is provided
    if not connection_string:
        return jsonify({"error": "Connection string is required."}), 400

    # Validate the connection string using the function
    if validate_connection_string(connection_string):
        return jsonify({"success": True, "message": "Valid Azure Blob Storage connection string."}), 200
    else:
        return jsonify({"error": "Invalid Azure Blob Storage connection string."}), 400




# Route to check API key validity
@app.route('/test-api-key', methods=['POST'])
def check_api_key():
    if request.content_type != 'application/json':
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    # Get JSON data from the request
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body must be in JSON format'}), 400

    # Extract the DeepL API key from the request
    auth_key = data.get('auth_key')
    if not auth_key:
        return jsonify({'error': 'Please provide the "auth_key".'}), 400

    try:
        # Test the API key by performing a translation
        translated_text = test_api_key(auth_key)
        return jsonify({'success': True, 'translated_text': translated_text}), 200
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except RuntimeError as re:
        return jsonify({'error': str(re)}), 500
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred: ' + str(e)}), 500


# Route to retrieve all columns using admin_id from form data
@app.route('/test_deepl_api', methods=['POST'])
def get_api():
    try:
        # Get admin_id from the form data
        admin_id = request.form.get('admin_id')

        if not admin_id:
            return jsonify({"error": "admin_id is required"}), 400

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # SQL query to fetch all columns for the given admin_id
        cursor.execute("SELECT * FROM deepl_settings WHERE admin_id = %s", (admin_id,))

        # Fetch the result
        result = cursor.fetchone()

        # Check if result is None (no admin_id found)
        if not result:
            return jsonify({"error": "No record found for the given admin_id"}), 404

        # Map the result to column names (assuming columns are admin_id and api in that order)
        record = {
            "admin_id": result[0],  # First column (admin_id)
            "api": result[1]         # Second column (api key)
        }

        # Close the connection
        cursor.close()
        conn.close()

        return jsonify(record), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





DEEPL_API_URL = 'https://api.deepl.com/v2/document'

@app.route('/multiple_files', methods=['POST'])
def translate_files():
    try:
        # Retrieve form data
        files = request.files.getlist('file')  # The list of uploaded files
        source_lang = request.form.get('source_lang', 'auto')  # Default to auto-detect if not provided
        target_lang = request.form['target_lang']  # Target language

        # Convert human-readable language names to language codes
        source_lang_code = language_mapping.get(source_lang, 'auto')  # Use 'auto' for detection if not in mapping
        target_lang_code = language_mapping.get(target_lang)

        if not target_lang_code:
            return jsonify({"error": "Invalid target language"}), 400

        download_urls = []  # To store file names and download URLs

        # Process each file individually
        for file in files:
            # Prepare file and payload for the DeepL API request
            file_payload = {
                'file': (file.filename, file.stream, file.content_type),
                'target_lang': (None, target_lang_code),
                'source_lang': (None, source_lang_code if source_lang_code != 'auto' else None)
            }

            headers = {
                'Authorization': f'DeepL-Auth-Key {DEEPL_API_KEY}'
            }

            # 1. Upload document for translation
            response = requests.post(DEEPL_API_URL, files=file_payload, headers=headers)

            if response.status_code != 200:
                return jsonify({"error": f"File upload failed for {file.filename}"}), response.status_code

            response_data = response.json()
            document_id = response_data['document_id']
            document_key = response_data['document_key']

            # 2. Check translation status (polling)
            check_status_url = f"{DEEPL_API_URL}/{document_id}"
            status_payload = {"document_key": document_key}

            status = 'translating'
            while status == 'translating':
                status_response = requests.post(check_status_url, json=status_payload, headers=headers)
                status_data = status_response.json()
                status = status_data['status']

            if status != 'done':
                return jsonify({"error": f"Translation failed for {file.filename}"}), 500

            # 3. Instead of downloading the file, get the URL for download
            download_url = f"{DEEPL_API_URL}/{document_id}/result"
            
            # Append the file name and corresponding download URL to the list
            download_urls.append({
                'file_name': file.filename,
                'download_url': download_url,
                'document_key': document_key  # document_key needed for accessing the result later
            })

        # Return the list of file names and download URLs
        return jsonify({
            'message': 'Files translated successfully',
            'translations': download_urls
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    feedback_data = request.json  # Get feedback data from the request
    return store_feedback(feedback_data)  # Call the feedback storage function








@app.route('/download_translated_file', methods=['POST'])
def download_translated_document():
    data = request.json
    download_url = data.get('download_url')
    document_key = data.get('document_key')

    if not download_url or not document_key:
        return jsonify({"error": "Missing document URL or document key"}), 400

    # Extract document_id from the download URL
    document_id = download_url.split('/v2/document/')[1].split('/result')[0]

    # Prepare the headers for the POST request
    headers = {
        "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
        "User-Agent": "YourApp/1.0",
        "Content-Type": "application/json"
    }

    # Prepare the payload with the document_key
    payload = {
        "document_key": document_key
    }

    # Send the POST request to DeepL API to download the translated document
    response = requests.post(f'https://api.deepl.com/v2/document/{document_id}/result', headers=headers, json=payload)

    # If request fails, return the error
    if response.status_code != 200:
        return jsonify({"error": f"Failed to download the document. Status code: {response.status_code}"}), response.status_code

    # Send the file content as a response directly to the client
    return Response(
        response.content,
        mimetype='application/octet-stream',
        headers={
            "Content-Disposition": f"attachment;filename=translated_document_{document_id}.txt"
        }
    )




from flask import Flask, jsonify
import datetime
import logging
from azure.storage.blob import BlobServiceClient
# Hardcoded connection string for Azure Blob Storage
connection_string = "DefaultEndpointsProtocol=https;AccountName=devaitranslationstorage;AccountKey=GtiG/Hm1kzpGy8aElsdqgBiApPvUgEg+8DbylzCUYV+f4ZCfsNFRCLLIsfrvPemzXqm5hnIw6VGA+AStpe8FWQ==;EndpointSuffix=core.windows.net"

def get_container_timestamp(container_name):
    # Extract timestamp from container name, assuming format 'source-YYYYMMDDHHMMSS'
    try:
        timestamp_str = container_name.split('-')[-1]
        return datetime.datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    except ValueError:
        return None

@app.route('/delete_old_containers', methods=['POST'])
def delete_old_containers():
    logging.info("Flask App to delete containers created over an hour ago")

    # Create BlobServiceClient using the hardcoded connection string
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    # Get current time
    current_time = datetime.datetime.utcnow()
    logging.info(f"Current UTC Time: {current_time}")

    # List all containers in the storage account
    containers = blob_service_client.list_containers()

    deleted_containers = []

    for container in containers:
        container_name = container['name']

        # Get the timestamp from the container name
        container_timestamp = get_container_timestamp(container_name)

        if container_timestamp:
            # Check if the container is older than one hour
            time_difference = current_time - container_timestamp
            if time_difference.total_seconds() > 15:  # Older than 1 hour
                try:
                    # Delete the container
                    blob_service_client.delete_container(container_name)
                    deleted_containers.append(container_name)
                    logging.info(f"Deleted container: {container_name}")
                except Exception as e:
                    logging.error(f"Failed to delete container {container_name}: {e}")
            else:
                logging.info(f"Container {container_name} is less than 1 hour old, skipping...")
        else:
            logging.info(f"Container {container_name} does not match the expected naming pattern.")

    return jsonify({"deleted_containers": deleted_containers}), 200








from flask import Flask, request, jsonify
import requests
import time
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

# Language mapping as provided
language_mapping = {
    "Arabic": "AR",
    "Bulgarian": "BG",
    "Czech": "CS",
    "Danish": "DA",
    "German": "DE",
    "Greek": "EL",
    "English": "EN",
    "English (British)": "EN-GB",
    "English (American)": "EN-US",
    "Spanish": "ES",
    "Estonian": "ET",
    "Finnish": "FI",
    "French": "FR",
    "Hungarian": "HU",
    "Indonesian": "ID",
    "Italian": "IT",
    "Japanese": "JA",
    "Korean": "KO",
    "Lithuanian": "LT",
    "Latvian": "LV",
    "Norwegian Bokmål": "NB",
    "Dutch": "NL",
    "Polish": "PL",
    "Portuguese": "PT",
    "Portuguese (Brazilian)": "PT-BR",
    "Portuguese (European)": "PT-PT",
    "Romanian": "RO",
    "Russian": "RU",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Swedish": "SV",
    "Turkish": "TR",
    "Ukrainian": "UK",
    "Chinese": "ZH",
    "Chinese (Simplified)": "ZH-HANS",
    "Chinese (Traditional)": "ZH-HANT"
}

# Supported languages for formality
formality_supported_languages = {"DE", "FR", "IT", "ES", "NL", "PL", "PT-BR", "PT-PT", "JA", "RU"}

DEEPL_API_URL = 'https://api.deepl.com/v2/document'
DEEPL_API_KEY = '82a64fae-73d4-4739-9935-bbf3cfc15010'  # Replace with your actual DeepL API key
STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=devaitranslationstorage;AccountKey=GtiG/Hm1kzpGy8aElsdqgBiApPvUgEg+8DbylzCUYV+f4ZCfsNFRCLLIsfrvPemzXqm5hnIw6VGA+AStpe8FWQ==;EndpointSuffix=core.windows.net"

# Initialize Azure Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

@app.route('/multiple_files2', methods=['POST'])
def translate_files2():
    try:
        # Retrieve form data
        files = request.files.getlist('file')
        source_lang = request.form.get('source_lang', 'auto')
        target_lang = request.form['target_lang']
        formality = request.form['formality']

        source_lang_code = language_mapping.get(source_lang, 'auto')
        target_lang_code = language_mapping.get(target_lang)

        if not target_lang_code:
            return jsonify({"error": "Invalid target language"}), 400

        if target_lang_code not in formality_supported_languages and formality in ['more', 'less']:
            return jsonify({
                "error": f"Formality '{formality}' is not supported for the target language '{target_lang}'."
            }), 400

        # List to hold SAS URLs for all translated files
        sas_urls = []

        for file in files:
            # Prepare file and payload for the DeepL API request
            file_payload = {
                'file': (file.filename, file.stream, file.content_type),
                'target_lang': (None, target_lang_code),
                'source_lang': (None, source_lang_code if source_lang_code != 'auto' else None),
                'formality': (None, formality)
            }

            headers = {
                'Authorization': f'DeepL-Auth-Key {DEEPL_API_KEY}'
            }

            # 1. Upload document for translation
            response = requests.post(DEEPL_API_URL, files=file_payload, headers=headers)

            if response.status_code != 200:
                return jsonify({"error": f"File upload failed for {file.filename}"}), response.status_code

            response_data = response.json()
            document_id = response_data['document_id']
            document_key = response_data['document_key']

            # 2. Check translation status (polling)
            check_status_url = f"{DEEPL_API_URL}/{document_id}"
            status_payload = {"document_key": document_key}

            max_retries = 20
            retry_count = 0
            status = 'translating'

            retry_count = 0
            retry_interval = 10  # Start with 10 seconds
    
            while status in ['translating', 'queued'] and retry_count < max_retries:
                time.sleep(retry_interval)
                status_response = requests.post(check_status_url, json=status_payload, headers=headers)
                status_data = status_response.json()
                status = status_data['status']
    
                if status == 'done':
                    break
                elif status == 'failed':
                    error_message = status_data.get('error', 'Unknown error occurred')
                    return jsonify({
                        "error": f"Translation failed for {file.filename}",
                        "status_details": status_data,
                        "error_message": error_message
                    }), 500
    
                # Exponential backoff: double the wait time after each retry
                retry_interval = min(retry_interval * 2, 300)  # Cap the wait time at 5 minutes
                retry_count += 1

            if status != 'done':
                return jsonify({
                    "error": f"Translation still in progress for {file.filename} after maximum retries.",
                    "status_details": status_data
                }), 500

            # 3. Download the translated document
            download_response = requests.post(f"{DEEPL_API_URL}/{document_id}/result", 
                                            json={"document_key": document_key}, 
                                            headers=headers)

            if download_response.status_code != 200:
                return jsonify({"error": f"Failed to download translated file for {file.filename}"}), download_response.status_code

            # Create translated blob name using original file name and target language code
            translated_blob_name = f"{file.filename.rsplit('.', 1)[0]}-{target_lang_code}.{file.filename.rsplit('.', 1)[-1]}"

            # Upload the translated document to Azure Blob Storage
            container_name = f"destination-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            blob_service_client.create_container(container_name)

            blob_client = blob_service_client.get_blob_client(container=container_name, blob=translated_blob_name)

            # Upload the translated content
            blob_client.upload_blob(download_response.content, overwrite=True)

            # Generate a SAS URL for the uploaded blob
            sas_token = generate_blob_sas(
                account_name='devaitranslationstorage',  # Your storage account name
                account_key='GtiG/Hm1kzpGy8aElsdqgBiApPvUgEg+8DbylzCUYV+f4ZCfsNFRCLLIsfrvPemzXqm5hnIw6VGA+AStpe8FWQ==',  # Your account key
                container_name=container_name,
                blob_name=translated_blob_name,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )

            sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{translated_blob_name}?{sas_token}"
            sas_urls.append({"filename": file.filename, "sas_url": sas_url})

        # Return the list of SAS URLs for all uploaded files
        return jsonify({"sas_urls": sas_urls})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    # Use the environment variable PORT, or default to port 5000 if not set
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
