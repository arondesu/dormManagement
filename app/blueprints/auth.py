from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from db import get_db_connection


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Please enter username and password.", "warning")
            return render_template("logIn.html")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id, username, password_hash, role, is_active FROM users WHERE username=? OR email=? LIMIT 1",
                (identifier, identifier),
            )
            row = cursor.fetchone()

            if not row:
                flash("Invalid username or password", "danger")
                return render_template("logIn.html")

            user = dict(row)

            if not user.get("is_active", 1):
                flash("Account is deactivated. Contact admin.", "danger")
                return render_template("logIn.html")

            if not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
                flash("Invalid username or password", "danger")
                return render_template("logIn.html")

            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user.get("role")

            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("home"))

        except Exception as error:
            flash(f"Error during login: {error}", "danger")
            print(f"Login error: {error}")
        finally:
            cursor.close()
            conn.close()

    return render_template("logIn.html")


@bp.route("/register", methods=["GET"])
def register():
    return render_template("register.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))
