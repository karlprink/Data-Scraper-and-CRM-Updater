import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DB_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = DB_URL and DB_URL.startswith("postgres")

def get_db_connection():
    if IS_POSTGRES:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect("/tmp/companies.db")
        conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                regcode TEXT PRIMARY KEY,
                name TEXT,
                data_json JSONB,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                regcode TEXT PRIMARY KEY,
                name TEXT,
                data_json TEXT,
                updated_at TEXT
            )
        """)

    conn.commit()
    conn.close()





