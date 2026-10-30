
import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Use Render's persistent disk when configured.
# Otherwise, use the project folder locally.
DATABASE_NAME = os.environ.get(
    "DATABASE_PATH",
    str(BASE_DIR / "healsync.db")
)


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            visit_date TEXT NOT NULL DEFAULT '',
            symptoms TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Waiting',
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(tokens)"
        ).fetchall()
    }

    missing_columns = {
        "patient_id": "INTEGER",
        "patient_name": "TEXT NOT NULL DEFAULT ''",
        "department": "TEXT NOT NULL DEFAULT ''",
        "visit_date": "TEXT NOT NULL DEFAULT ''",
        "symptoms": "TEXT NOT NULL DEFAULT ''",
        "status": "TEXT NOT NULL DEFAULT 'Waiting'"
    }

    for column, definition in missing_columns.items():
        if column not in columns:
            connection.execute(
                f"ALTER TABLE tokens ADD COLUMN {column} {definition}"
            )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("HealSync database updated successfully.")
