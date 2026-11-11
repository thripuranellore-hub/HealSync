
import os
from functools import wraps
from datetime import date

from flask import (
    Flask, render_template, request, redirect,
    url_for, session
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)
from database import get_connection, create_tables


app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")

# Administrator credentials are read from Render Environment.
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


# ---------------- LOGIN PROTECTION ----------------

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


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- PATIENT REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, phone, password]):
            return render_template(
                "register.html",
                error="Please fill in all fields."
            )

        connection = get_connection()
        cursor = connection.cursor()

        try:
            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO patients (name, email, phone, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email, phone, password_hash)
            )

            connection.commit()

            return redirect(url_for("login"))

        except Exception:
            connection.rollback()
            return render_template(
                "register.html",
                error="Registration failed. This email may already be registered."
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        role = request.form.get("role", "").strip().lower()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Administrator login
        if role == "admin":

            if not ADMIN_ID or not ADMIN_PASSWORD:
                return render_template(
                    "login.html",
                    error="Administrator credentials are not configured on the server."
                )

            if (
                email.lower() == ADMIN_ID.lower()
                and password == ADMIN_PASSWORD
            ):
                session.clear()
                session["role"] = "admin"
                session["admin_id"] = ADMIN_ID

                return redirect(url_for("admin"))

            return render_template(
                "login.html",
                error="Invalid administrator ID or password."
            )

        # Patient login
        elif role == "patient":

            connection = get_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(
                    "SELECT * FROM patients WHERE email = %s",
                    (email.lower(),)
                )

                patient = cursor.fetchone()

            finally:
                cursor.close()
                connection.close()

            if patient and check_password_hash(
                patient["password_hash"], password
            ):
                session.clear()
                session["patient_id"] = patient["id"]
                session["patient_name"] = patient["name"]
                session["role"] = "patient"

                return redirect(url_for("patient_dashboard"))

            return render_template(
                "login.html",
                error="Invalid patient email or password."
            )

        return render_template(
            "login.html",
            error="Please select a valid login role."
        )

    return render_template("login.html")


# ---------------- PATIENT DASHBOARD ----------------

@app.route("/patient")
@login_required
def patient_dashboard():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM tokens
            WHERE patient_id = %s
            """,
            (session["patient_id"],)
        )

        result = cursor.fetchone()
        total_tokens = result["total"]

        cursor.execute(
            """
            SELECT *
            FROM tokens
            WHERE patient_id = %s
            ORDER BY id DESC
            LIMIT 5
            """,
            (session["patient_id"],)
        )

        recent_tokens = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "patient.html",
        patient_name=session.get("patient_name"),
        total_tokens=total_tokens,
        tokens=recent_tokens,
        departments=DEPARTMENTS
    )


# ---------------- BOOK TOKEN ----------------

@app.route("/book-token", methods=["GET", "POST"])
@login_required
def book_token():

    if request.method == "POST":

        department = request.form.get("department", "").strip()
        visit_date = request.form.get("visit_date", "").strip()
        symptoms = request.form.get("symptoms", "").strip()

        if not department or not visit_date or not symptoms:
            return render_template(
                "book_token.html",
                departments=DEPARTMENTS,
                error="Please fill in all fields."
            )

        if department not in DEPARTMENTS:
            return render_template(
                "book_token.html",
                departments=DEPARTMENTS,
                error="Please select a valid department."
            )

        connection = get_connection()
        cursor = connection.cursor()

        try:
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
                    session["patient_name"],
                    department,
                    visit_date,
                    symptoms,
                    "Waiting"
                )
            )

            token = cursor.fetchone()
            token_id = token["id"]

            connection.commit()

            return render_template(
                "book_token.html",
                departments=DEPARTMENTS,
                success=f"Token booked successfully! Your token number is {token_id}."
            )

        except Exception:
            connection.rollback()
            return render_template(
                "book_token.html",
                departments=DEPARTMENTS,
                error="Unable to book token. Please try again."
            )

        finally:
            cursor.close()
            connection.close()

    return render_template(
        "book_token.html",
        departments=DEPARTMENTS
    )


# ---------------- MY TOKENS ----------------

@app.route("/my-tokens")
@login_required
def my_tokens():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM tokens
            WHERE patient_id = %s
            ORDER BY id DESC
            """,
            (session["patient_id"],)
        )

        tokens = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template("my_tokens.html", tokens=tokens)


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
@admin_required
def admin():

    connection = get_connection()
    cursor = connection.cursor()

    try:
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
            "SELECT * FROM tokens ORDER BY id DESC"
        )
        tokens = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin.html",
        total_patients=total_patients,
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        tokens=tokens
    )


# ---------------- UPDATE TOKEN STATUS ----------------

@app.route("/update-token/<int:token_id>", methods=["POST"])
@admin_required
def update_token(token_id):

    status = request.form.get("status", "").strip()

    allowed_statuses = ["Waiting", "In Progress", "Completed"]

    if status not in allowed_statuses:
        return redirect(url_for("admin"))

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE tokens
            SET status = %s
            WHERE id = %s
            """,
            (status, token_id)
        )

        connection.commit()

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin"))


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)
