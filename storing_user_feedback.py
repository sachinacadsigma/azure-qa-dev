from flask import jsonify
import psycopg2
from psycopg2 import sql
from db_connection import connect_db  # Import the connection function from a shared module

def store_feedback(feedback_data):
    """Store user feedback in the database."""
    user_id = feedback_data.get('user_id')
    feedback_text = feedback_data.get('feedback_text')
    source_language = feedback_data.get('source_language')
    target_language = feedback_data.get('target_language')
    document_name = feedback_data.get('document_name')
    source_text = feedback_data.get('source_text')
    translated_text = feedback_data.get('translated_text')
    vendor = feedback_data.get('vendor')

    try:
        conn = connect_db()  # Use the connection function from your db module
        cursor = conn.cursor()

        insert_query = sql.SQL("""
            INSERT INTO user_feedback (
                user_id, feedback_text, source_language, 
                target_language, document_name, 
                source_text, translated_text, vendor
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """)

        cursor.execute(insert_query, (user_id, feedback_text, source_language,
                                      target_language, document_name,
                                      source_text, translated_text, vendor))
        conn.commit()
        return jsonify({"message": "Feedback added successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            cursor.close()
            conn.close()
