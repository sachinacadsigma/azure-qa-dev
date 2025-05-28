from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql

# Database connection details
DB_CONFIG = {
    'dbname': 'settings_db',
    'user': 'citus',
    'password': 'password@123',
    'host': 'c-settings-details.4frco7jk32qfsk.postgres.cosmos.azure.com',
    'port': '5432'
}

def connect_db():
    """Create a database connection."""
    conn = psycopg2.connect(
        dbname=DB_CONFIG['dbname'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port']
    )
    return conn
