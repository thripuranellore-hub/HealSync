
import os

from flask import render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        role = request.form.get("role", "").strip().lower()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Administrator login
        admin_id = os.environ.get("ADMIN_ID", "").strip()
        admin_password = os.environ.get("ADMIN_PASSWORD", "")

        if role == "admin":

            if (
                email.lower() == admin_id.lower()
                and password == admin_password
            ):
                session.clear()
                session["role"] = "admin"
                session["admin_id"] = admin_id

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
                    (email,)
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
