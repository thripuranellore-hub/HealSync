
@app.route("/my-tokens")
@login_required
def my_tokens():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT * FROM tokens
            WHERE patient_id = %s
            ORDER BY id DESC
            """,
            (session["patient_id"],)
        )

        tokens = cursor.fetchall()

        return render_template(
            "my_tokens.html",
            tokens=tokens
        )

    finally:
        cursor.close()
        connection.close()
