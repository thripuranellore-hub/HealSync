
import sqlite3

DATABASE_NAME = "healsync.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()

    # Create the patients table if it does not exist.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Create the tokens table for new databases.
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

    # Check columns in an existing tokens table.
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(tokens)"
        ).fetchall()
    }

    # Add missing columns without deleting existing records.
    if "patient_id" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN patient_id INTEGER"
        )

    if "patient_name" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN patient_name TEXT NOT NULL DEFAULT ''"
        )

    if "department" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN department TEXT NOT NULL DEFAULT ''"
        )

    if "visit_date" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN visit_date TEXT NOT NULL DEFAULT ''"
        )

    if "symptoms" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN symptoms TEXT NOT NULL DEFAULT ''"
        )

    if "status" not in columns:
        connection.execute(
            "ALTER TABLE tokens ADD COLUMN status TEXT NOT NULL DEFAULT 'Waiting'"
        )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("HealSync database updated successfully.")
