
import os
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import get_connection, create_tables


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local-development-key"
)

ADMIN_ID = os.environ.get("ADMIN_ID", "").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

DEPARTMENTS = [
    "General Medicine",
    "Cardiology",
    "Dermatology",
    "Orthopedics",
    "Pediatrics",
    "Ophthalmology"
]


# Create database tables
create_tables()


# -------------------------------
# LOGIN PROTECTION
# -------------------------------

def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "patient_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# -------------------------------
# HOME PAGE
# -------------------------------

@app.route("/")
def home():
    # Always display homepage first
    return render_template("index.html")


# -------------------------------
# PATIENT REGISTRATION
# -------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    error = None
    success = None

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, phone, password]):
            error = "Please fill all the fields."

        else:
            connection = get_connection()
            cursor = connection.cursor()

            try:
                password_hash = generate_password_hash(password)

                cursor.execute(
                    """
                    INSERT INTO patients
                    (name, email, phone, password_hash)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (name, email, phone, password_hash)
                )

                connection.commit()

                success = "Registration successful. Please login."

            except Exception:
                connection.rollback()
                error = "Email already registered or registration failed."

            finally:
                cursor.close()
                connection.close()

    return render_template(
        "register.html",
        error=error,
        success=success
    )


# -------------------------------
# LOGIN
# -------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        role = request.form.get("role", "patient")
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # ADMIN LOGIN
        if role == "admin":

            if (
                ADMIN_ID
                and ADMIN_PASSWORD
                and email == ADMIN_ID
                and password == ADMIN_PASSWORD
            ):

                session.clear()
                session["role"] = "admin"

                return redirect(url_for("admin"))

            error = "Invalid admin ID or password."

        # PATIENT LOGIN
        else:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT * FROM patients WHERE email = %s",
                (email.lower(),)
            )

            patient = cursor.fetchone()

            cursor.close()
            connection.close()

            if (
                patient
                and check_password_hash(
                    patient["password_hash"],
                    password
                )
            ):

                session.clear()
                session["patient_id"] = patient["id"]
                session["patient_name"] = patient["name"]
                session["role"] = "patient"

                return redirect(url_for("patient_dashboard"))

            error = "Invalid patient email or password."

    return render_template("login.html", error=error)


# -------------------------------
# PATIENT DASHBOARD
# -------------------------------

@app.route("/patient")
@login_required
def patient_dashboard():

    connection = get_connection()
    cursor = connection.cursor()

    patient_id = session["patient_id"]

    cursor.execute(
        "SELECT * FROM patients WHERE id = %s",
        (patient_id,)
    )

    patient = cursor.fetchone()

    cursor.execute(
        """
        SELECT * FROM tokens
        WHERE patient_id = %s
        ORDER BY id DESC
        """,
        (patient_id,)
    )

    tokens = cursor.fetchall()

    total_tokens = len(tokens)

    cursor.close()
    connection.close()

    return render_template(
        "patient.html",
        patient_name=patient["name"] if patient else session.get("patient_name", ""),
        total_tokens=total_tokens,
        tokens=tokens,
        departments=DEPARTMENTS
    )


# -------------------------------
# BOOK TOKEN
# -------------------------------

@app.route("/book-token", methods=["GET", "POST"])
@login_required
def book_token():

    if request.method == "POST":

        department = request.form.get("department", "").strip()
        visit_date = request.form.get("visit_date", "").strip()
        symptoms = request.form.get("symptoms", "").strip()

        if (
            department not in DEPARTMENTS
            or not visit_date
            or not symptoms
        ):
            return render_template(
                "book_token.html",
                departments=DEPARTMENTS,
                error="Please enter valid booking details."
            )

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO tokens
            (patient_id, patient_name, department,
             visit_date, symptoms, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                session["patient_id"],
                session.get("patient_name", ""),
                department,
                visit_date,
                symptoms,
                "Waiting"
            )
        )

        token = cursor.fetchone()

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("my_tokens"))

    return render_template(
        "book_token.html",
        departments=DEPARTMENTS
    )


# -------------------------------
# MY TOKENS
# -------------------------------

@app.route("/my-tokens")
@login_required
def my_tokens():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT * FROM tokens
        WHERE patient_id = %s
        ORDER BY id DESC
        """,
        (session["patient_id"],)
    )

    tokens = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_tokens.html",
        tokens=tokens
    )


# -------------------------------
# ADMIN DASHBOARD
# -------------------------------

@app.route("/admin")
@admin_required
def admin():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM patients")
    total_patients = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM tokens")
    total_tokens = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tokens WHERE status = %s",
        ("Waiting",)
    )

    waiting_tokens = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT * FROM tokens
        ORDER BY id DESC
        """
    )

    tokens = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin.html",
        total_patients=total_patients,
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        tokens=tokens
    )


# -------------------------------
# UPDATE TOKEN STATUS
# -------------------------------

@app.route("/update-token/<int:token_id>", methods=["POST"])
@admin_required
def update_token(token_id):

    status = request.form.get("status")

    allowed_statuses = [
        "Waiting",
        "In Progress",
        "Completed"
    ]

    if status not in allowed_statuses:
        return redirect(url_for("admin"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tokens
        SET status = %s
        WHERE id = %s
        """,
        (status, token_id)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin"))


# -------------------------------
# LOGOUT
# -------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# -------------------------------
# RUN APPLICATION
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True)
