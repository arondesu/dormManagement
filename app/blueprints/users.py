import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from db import get_db_connection

from .common import role_required


bp = Blueprint("users", __name__)


@bp.route("/users")
def users():
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    users_list = []

    try:
        query = """
            SELECT user_id, username, first_name, last_name, role,
                   email, phone, is_active
            FROM users
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (first_name LIKE ? OR last_name LIKE ? OR username LIKE ? OR email LIKE ?)"
            like_search = f"%{search}%"
            params.extend([like_search, like_search, like_search, like_search])

        if role_filter and role_filter.lower() != "all roles":
            query += " AND role = ?"
            params.append(role_filter.lower())

        query += " ORDER BY user_id"

        cursor.execute(query, params)
        users_list = [dict(row) for row in cursor.fetchall()]

    except Exception as error:
        flash(f"Error fetching users: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template("02_users.html", users=users_list, search=search, role_filter=role_filter)


@bp.route("/add_user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        role = request.form.get("role", "student")
        birth_date = request.form.get("birth_date")

        if not username or not email or not password:
            flash("Username, email and password are required.", "danger")
            return redirect(request.path)

        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, email):
            flash("Invalid email format.", "danger")
            return redirect(request.path)

        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            flash("Password must be at least 8 characters long and include letters and numbers.", "danger")
            return redirect(request.path)

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE username=?", (username,))
            if cursor.fetchone()[0] > 0:
                flash("Username already taken.", "danger")
                return redirect(request.path)
            cursor.execute("SELECT COUNT(*) FROM users WHERE email=?", (email,))
            if cursor.fetchone()[0] > 0:
                flash("Email already registered.", "danger")
                return redirect(request.path)

            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, role, first_name, last_name, email, phone, birth_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
                (username, password_hash, role, first_name, last_name, email, phone, birth_date),
            )
            conn.commit()
            flash("User added successfully!", "success")
            try:
                send_confirmation_email(email, username)
                flash("Confirmation email sent.", "info")
            except Exception:
                flash("Confirmation email not sent (SMTP not configured).", "warning")

            if session.get("user_id"):
                return redirect(url_for("users"))
            return redirect(url_for("login"))
        except Exception as error:
            flash(f"Error adding user: {error}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")


@bp.route("/admin/add_user", methods=["GET", "POST"])
@role_required("admin")
def admin_add_user():
    if session.get("role") != "admin":
        flash("Admin access required to add users.", "danger")
        return redirect(url_for("users"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        role = request.form.get("role", "student")
        birth_date = request.form.get("birth_date")

        if not username or not email or not password:
            flash("Username, email and password are required.", "danger")
            return redirect(url_for("admin_add_user"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE username=?", (username,))
            if cursor.fetchone()[0] > 0:
                flash("Username already taken.", "danger")
                return redirect(url_for("admin_add_user"))
            cursor.execute("SELECT COUNT(*) FROM users WHERE email=?", (email,))
            if cursor.fetchone()[0] > 0:
                flash("Email already registered.", "danger")
                return redirect(url_for("admin_add_user"))

            password_hash = generate_password_hash(password)
            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, role, first_name, last_name, email, phone, birth_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
                (username, password_hash, role, first_name, last_name, email, phone, birth_date),
            )
            conn.commit()
            flash("User added successfully!", "success")
            return redirect(url_for("users"))
        except Exception as error:
            flash(f"Error adding user: {error}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("02_add_user.html")


def send_confirmation_email(to_email, username):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not smtp_host or not smtp_port or not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = "Welcome to Dorm Management"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content(f"Hi {username},\n\nThank you for registering.\n\nRegards,\nDorm Management")

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)


@bp.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = None
    try:
        if request.method == "POST":
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            password = request.form.get("password", "")
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            birth_date = request.form.get("birth_date", "").strip()
            role = request.form.get("role", "student").strip()
            is_active = int(request.form.get("is_active", "1"))

            if not first_name or not last_name:
                flash("First name and last name are required.", "warning")
                return redirect(url_for("edit_user", user_id=user_id))

            if password:
                if len(password) < 8:
                    flash("Password must be at least 8 characters long.", "warning")
                    return redirect(url_for("edit_user", user_id=user_id))
                password_hash = generate_password_hash(password)
                cursor.execute(
                    """
                    UPDATE users
                    SET first_name = ?, last_name = ?, password_hash = ?, email = ?, phone = ?,
                        birth_date = ?, role = ?, is_active = ?
                    WHERE user_id = ?
                    """,
                    (first_name, last_name, password_hash, email, phone, birth_date or None, role, is_active, user_id),
                )

            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET first_name = ?, last_name = ?, email = ?, phone = ?,
                        birth_date = ?, role = ?, is_active = ?
                    WHERE user_id = ?
                    """,
                    (first_name, last_name, email, phone, birth_date or None, role, is_active, user_id),
                )

            conn.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for("users"))

        cursor.execute(
            """
            SELECT user_id, username, first_name, last_name, role, email, phone, birth_date, is_active
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("users"))

        if user.get("birth_date"):
            try:
                birth_date = user["birth_date"]
                if isinstance(birth_date, str):
                    parsed = None
                    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                        try:
                            parsed = datetime.strptime(birth_date, fmt)
                            break
                        except Exception:
                            continue
                    if parsed:
                        user = dict(user)
                        user["birth_date"] = parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

    except Exception:
        pass
    finally:
        cursor.close()
        conn.close()

    return render_template("02_edit_user.html", user=user)


@bp.route("/delete_user/<int:user_id>", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM room_assignments WHERE user_id=?", (user_id,))
        assignment_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM payments WHERE user_id=?", (user_id,))
        payment_count = cursor.fetchone()[0]

        if assignment_count > 0 or payment_count > 0:
            cursor.execute("UPDATE users SET is_active = 0 WHERE user_id=?", (user_id,))
            conn.commit()
            flash(
                "User cannot be deleted because related records exist. User has been deactivated instead.",
                "warning",
            )
        else:
            cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            flash("User deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting user: {error}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("users"))
