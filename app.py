
import os
from flask import (
    Flask, render_template, request,
    redirect, url_for, session
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)
from database import get_connection, create_tables
from datetime import date
from functools import wraps


app = Flask(__name__)

# Secret key from Render Environment Variables
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "healsync-development-key-change-before-deployment"
)

# Create PostgreSQL tables
create_tables()


# Admin credentials
ADMIN_ID = os.environ.get("ADMIN_ID", "admin@healsync.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-password")


# Hospital departments
DEPARTMENTS = [
    "General Medicine",
    "Cardiology",
    "Dermatology",
    "Orthopedics",
    "Pediatrics",
    "Ophthalmology"
]


# Patient login protection
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "patient_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# Admin login protection
def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Patient registration
@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, phone, password]):
            error = "Please fill in all fields."

        elif len(password) < 6:
            error = "Password must contain at least 6 characters."

        else:
            connection = get_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO patients
                    (name, email, phone, password_hash)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        name,
                        email,
                        phone,
                        generate_password_hash(password)
                    )
                )

                connection.commit()
                cursor.close()
                connection.close()

                return redirect(
                    url_for("login", registered="1")
                )

            except Exception:
                connection.rollback()
                cursor.close()
                connection.close()

                error = "This email may already be registered."

    return render_template("register.html", error=error)


# Patient and Admin login
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":

        identifier = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        role = request.form.get("role", "patient")

        # Admin login
        if role == "admin":

            if (
                identifier == ADMIN_ID.lower()
                and password == ADMIN_PASSWORD
            ):
                session.clear()
                session["role"] = "admin"

                return redirect(url_for("admin"))

            error = "Invalid admin ID or password."

        # Patient login
        else:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT * FROM patients
                WHERE email = %s
                """,
                (identifier,)
            )

            patient = cursor.fetchone()

            cursor.close()
            connection.close()

            if patient and check_password_hash(
                patient["password_hash"], password
            ):

                session.clear()

                session["patient_id"] = patient["id"]
                session["patient_name"] = patient["name"]
                session["role"] = "patient"

                return redirect(url_for("patient"))

            error = "Invalid patient email or password."

    registered = request.args.get("registered") == "1"

    return render_template(
        "login.html",
        error=error,
        registered=registered
    )


# Patient dashboard
@app.route("/patient")
@login_required
def patient():

    connection = get_connection()
    cursor = connection.cursor()

    patient_id = session["patient_id"]

    cursor.execute(
        """
        SELECT COUNT(*) FROM tokens
        WHERE patient_id = %s
        """,
        (patient_id,)
    )

    total_tokens = cursor.fetchone()["count"]

    cursor.execute(
        """
        SELECT COUNT(*) FROM tokens
        WHERE patient_id = %s
        AND status = 'Waiting'
        """,
        (patient_id,)
    )

    waiting_tokens = cursor.fetchone()["count"]

    cursor.execute(
        """
        SELECT * FROM tokens
        WHERE patient_id = %s
        ORDER BY id DESC
        LIMIT 5
        """,
        (patient_id,)
    )

    recent_tokens = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "patient.html",
        patient_name=session["patient_name"],
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        recent_tokens=recent_tokens
    )


# Book hospital token
@app.route("/book-token", methods=["GET", "POST"])
@login_required
def book_token():

    error = ""
    booked_token = None

    if request.method == "POST":

        department = request.form.get(
            "department", ""
        ).strip()

        visit_date = request.form.get(
            "visit_date", ""
        )

        symptoms = request.form.get(
            "symptoms", ""
        ).strip()

        if department not in DEPARTMENTS:

            error = "Please select a valid department."

        elif (
            not visit_date
            or visit_date < date.today().isoformat()
        ):

            error = "Please select today or a future date."

        else:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO tokens
                (
                    patient_id,
                    patient_name,
                    department,
                    visit_date,
                    symptoms,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, 'Waiting')
                RETURNING id
                """,
                (
                    session["patient_id"],
                    session["patient_name"],
                    department,
                    visit_date,
                    symptoms
                )
            )

            booked_token = cursor.fetchone()["id"]

            connection.commit()
            cursor.close()
            connection.close()

    return render_template(
        "book_token.html",
        patient_name=session["patient_name"],
        departments=DEPARTMENTS,
        today=date.today().isoformat(),
        error=error,
        booked_token=booked_token
    )


# Patient token history
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


# Admin dashboard
@app.route("/admin")
@admin_required
def admin():

    connection = get_connection()
    cursor = connection.cursor()

    # Total registered patients
    cursor.execute(
        "SELECT COUNT(*) FROM patients"
    )

    patient_count = cursor.fetchone()["count"]

    # Total booked tokens
    cursor.execute(
        "SELECT COUNT(*) FROM tokens"
    )

    total_tokens = cursor.fetchone()["count"]

    # Waiting tokens
    cursor.execute(
        """
        SELECT COUNT(*) FROM tokens
        WHERE status = 'Waiting'
        """
    )

    waiting_tokens = cursor.fetchone()["count"]

    # In-progress tokens
    cursor.execute(
        """
        SELECT COUNT(*) FROM tokens
        WHERE status = 'In Progress'
        """
    )

    in_progress = cursor.fetchone()["count"]

    # Completed tokens
    cursor.execute(
        """
        SELECT COUNT(*) FROM tokens
        WHERE status = 'Completed'
        """
    )

    completed_tokens = cursor.fetchone()["count"]

    # All booked tokens
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
        patient_count=patient_count,
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        in_progress=in_progress,
        completed_tokens=completed_tokens,
        tokens=tokens
    )


# Update token status
@app.route("/update-token/<int:token_id>", methods=["POST"])
@admin_required
def update_token(token_id):

    status = request.form.get("status", "")

    allowed_statuses = [
        "Waiting",
        "In Progress",
        "Completed"
    ]

    if status in allowed_statuses:

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


# Logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# Run locally
if __name__ == "__main__":
    app.run(debug=True)
