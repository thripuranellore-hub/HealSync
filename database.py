
import os
import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is missing")

    connection = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    return connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER REFERENCES patients(id),
            patient_name TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            visit_date TEXT NOT NULL DEFAULT '',
            symptoms TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Waiting'
        )
    """)

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("HealSync PostgreSQL database created successfully!")
