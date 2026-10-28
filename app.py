
from flask import (
    Flask, render_template, request,
    redirect, url_for, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, create_tables
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = "healsync-development-key-change-before-deployment"

create_tables()

ADMIN_ID = "thripurahealsync@"
ADMIN_PASSWORD = "venkysmart"

DEPARTMENTS = [
    "General Medicine",
    "Cardiology",
    "Dermatology",
    "Orthopedics",
    "Pediatrics",
    "Ophthalmology"
]


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


@app.route("/")
def home():
    return render_template("index.html")


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

            try:
                connection.execute(
                    """INSERT INTO patients
                       (name, email, phone, password_hash)
                       VALUES (?, ?, ?, ?)""",
                    (
                        name,
                        email,
                        phone,
                        generate_password_hash(password)
                    )
                )
                connection.commit()
                connection.close()

                return redirect(url_for("login", registered="1"))

            except Exception:
                connection.close()
                error = "This email may already be registered."

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        identifier = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "patient")

        if role == "admin":
            if (
                identifier == ADMIN_ID
                and password == ADMIN_PASSWORD
            ):
                session.clear()
                session["role"] = "admin"
                return redirect(url_for("admin"))

            error = "Invalid admin ID or password."

        else:
            connection = get_connection()
            patient = connection.execute(
                "SELECT * FROM patients WHERE email = ?",
                (identifier,)
            ).fetchone()
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


@app.route("/patient")
@login_required
def patient():
    connection = get_connection()
    patient_id = session["patient_id"]

    total_tokens = connection.execute(
        "SELECT COUNT(*) FROM tokens WHERE patient_id = ?",
        (patient_id,)
    ).fetchone()[0]

    waiting_tokens = connection.execute(
        """SELECT COUNT(*) FROM tokens
           WHERE patient_id = ? AND status = 'Waiting'""",
        (patient_id,)
    ).fetchone()[0]

    recent_tokens = connection.execute(
        """SELECT * FROM tokens
           WHERE patient_id = ?
           ORDER BY id DESC LIMIT 5""",
        (patient_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "patient.html",
        patient_name=session["patient_name"],
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        recent_tokens=recent_tokens
    )


@app.route("/book-token", methods=["GET", "POST"])
@login_required
def book_token():
    error = ""
    booked_token = None

    if request.method == "POST":
        department = request.form.get("department", "").strip()
        visit_date = request.form.get("visit_date", "")
        symptoms = request.form.get("symptoms", "").strip()

        if department not in DEPARTMENTS:
            error = "Please select a valid department."
        elif not visit_date or visit_date < date.today().isoformat():
            error = "Please select today or a future date."
        else:
            connection = get_connection()

            cursor = connection.execute(
                """INSERT INTO tokens
                   (patient_id, patient_name, department,
                    visit_date, symptoms, status)
                   VALUES (?, ?, ?, ?, ?, 'Waiting')""",
                (
                    session["patient_id"],
                    session["patient_name"],
                    department,
                    visit_date,
                    symptoms
                )
            )

            booked_token = cursor.lastrowid
            connection.commit()
            connection.close()

    return render_template(
        "book_token.html",
        patient_name=session["patient_name"],
        departments=DEPARTMENTS,
        today=date.today().isoformat(),
        error=error,
        booked_token=booked_token
    )


@app.route("/my-tokens")
@login_required
def my_tokens():
    connection = get_connection()

    tokens = connection.execute(
        """SELECT * FROM tokens
           WHERE patient_id = ?
           ORDER BY id DESC""",
        (session["patient_id"],)
    ).fetchall()

    connection.close()

    return render_template("my_tokens.html", tokens=tokens)


@app.route("/admin")
@admin_required
def admin():
    connection = get_connection()

    patient_count = connection.execute(
        "SELECT COUNT(*) FROM patients"
    ).fetchone()[0]

    total_tokens = connection.execute(
        "SELECT COUNT(*) FROM tokens"
    ).fetchone()[0]

    waiting_tokens = connection.execute(
        "SELECT COUNT(*) FROM tokens WHERE status = 'Waiting'"
    ).fetchone()[0]

    in_progress = connection.execute(
        "SELECT COUNT(*) FROM tokens WHERE status = 'In Progress'"
    ).fetchone()[0]

    completed_tokens = connection.execute(
        "SELECT COUNT(*) FROM tokens WHERE status = 'Completed'"
    ).fetchone()[0]

    tokens = connection.execute(
        "SELECT * FROM tokens ORDER BY id DESC"
    ).fetchall()

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


@app.route("/update-token/<int:token_id>", methods=["POST"])
@admin_required
def update_token(token_id):
    status = request.form.get("status", "")
    allowed_statuses = ["Waiting", "In Progress", "Completed"]

    if status in allowed_statuses:
        connection = get_connection()
        connection.execute(
            "UPDATE tokens SET status = ? WHERE id = ?",
            (status, token_id)
        )
        connection.commit()
        connection.close()

    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
