import sqlite3
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection
from app.services.billing_service import allocate_payment_to_invoices, remove_payment_allocations
from app.utils.audit import log_audit_event

from .common import role_required


bp = Blueprint("payments", __name__)


@bp.route("/payments")
def payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    payments_list = []
    students = []
    buildings = []
    stats = {}

    student_filter = request.args.get("student_filter")
    building_filter = request.args.get("building_filter")
    method_filter = request.args.get("method_filter")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    try:
        base_query = """
                 SELECT p.payment_id, u.username, u.first_name, u.last_name,
                   p.amount, p.payment_method, p.payment_date,
                   p.receipt_number, p.payment_period_start, p.payment_period_end,
                     p.notes, r.room_number, b.building_name, ra.monthly_rate,
                     COALESCE(SUM(pa.allocated_amount), 0) AS allocated_amount
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
            LEFT JOIN rooms r ON ra.room_id = r.room_id
            LEFT JOIN buildings b ON r.building_id = b.building_id
                 LEFT JOIN payment_allocations pa ON pa.payment_id = p.payment_id
        """

        where_clauses = []
        params = []

        if session.get("role") == "landlord":
            where_clauses.append("b.owner_id = ?")
            params.append(session.get("user_id"))
        elif session.get("role") == "student":
            where_clauses.append("p.user_id = ?")
            params.append(session.get("user_id"))

        if student_filter:
            where_clauses.append("p.user_id = ?")
            params.append(student_filter)
        if building_filter:
            where_clauses.append("b.building_id = ?")
            params.append(building_filter)
        if method_filter:
            where_clauses.append("p.payment_method = ?")
            params.append(method_filter)
        if date_from:
            where_clauses.append("p.payment_date >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("p.payment_date <= ?")
            params.append(date_to)

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " GROUP BY p.payment_id ORDER BY p.payment_date DESC, p.payment_id DESC"

        cursor.execute(base_query, params)
        payments_list = cursor.fetchall()

        if session.get("role") == "admin":
            cursor.execute("SELECT SUM(amount) as total FROM payments")
            row = cursor.fetchone()
            stats["total_collected"] = row["total"] if row["total"] else 0

            cursor.execute(
                """
                SELECT SUM(amount) as total FROM payments
                WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')
            """
            )
            row = cursor.fetchone()
            stats["month_collected"] = row["total"] if row["total"] else 0

            cursor.execute("SELECT COUNT(*) as count FROM payments")
            row = cursor.fetchone()
            stats["payment_count"] = row["count"]

            cursor.execute("SELECT AVG(amount) as avg FROM payments")
            row = cursor.fetchone()
            stats["avg_payment"] = row["avg"] if row["avg"] else 0

        elif session.get("role") == "landlord":
            cursor.execute(
                """
                SELECT SUM(p.amount) as total FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
            """,
                (session.get("user_id"),),
            )
            row = cursor.fetchone()
            stats["total_collected"] = row["total"] if row["total"] else 0

            cursor.execute(
                """
                SELECT SUM(p.amount) as total FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ? AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            """,
                (session.get("user_id"),),
            )
            row = cursor.fetchone()
            stats["month_collected"] = row["total"] if row["total"] else 0

            cursor.execute(
                """
                SELECT COUNT(*) as count FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
            """,
                (session.get("user_id"),),
            )
            row = cursor.fetchone()
            stats["payment_count"] = row["count"]

        else:
            cursor.execute("SELECT SUM(amount) as total FROM payments WHERE user_id = ?", (session.get("user_id"),))
            row = cursor.fetchone()
            stats["total_paid"] = row["total"] if row["total"] else 0

            cursor.execute(
                """
                SELECT SUM(ra.monthly_rate) as expected FROM room_assignments ra
                WHERE ra.user_id = ? AND ra.status = 'active'
            """,
                (session.get("user_id"),),
            )
            row = cursor.fetchone()
            expected = row["expected"] if row["expected"] else 0
            stats["balance"] = expected - stats["total_paid"]

            cursor.execute(
                """
                SELECT MIN(end_date) as next_due FROM room_assignments
                WHERE user_id = ? AND status = 'active' AND end_date > date('now')
            """,
                (session.get("user_id"),),
            )
            row = cursor.fetchone()
            stats["next_due"] = row["next_due"] if row and row["next_due"] else "N/A"

        if session.get("role") in ["admin", "landlord"]:
            if session.get("role") == "admin":
                cursor.execute(
                    """
                    SELECT DISTINCT u.user_id, u.first_name, u.last_name
                    FROM users u
                    WHERE u.role = 'student' AND u.is_active = 1
                    ORDER BY u.first_name, u.last_name
                """
                )
            else:
                cursor.execute(
                    """
                    SELECT DISTINCT u.user_id, u.first_name, u.last_name
                    FROM users u
                    JOIN room_assignments ra ON u.user_id = ra.user_id
                    JOIN rooms r ON ra.room_id = r.room_id
                    JOIN buildings b ON r.building_id = b.building_id
                    WHERE b.owner_id = ? AND u.is_active = 1
                    ORDER BY u.first_name, u.last_name
                """,
                    (session.get("user_id"),),
                )
            students = cursor.fetchall()

        if session.get("role") == "admin":
            cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active = 1 ORDER BY building_name")
            buildings = cursor.fetchall()

    except Exception as error:
        flash(f"Error fetching payments: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "payments/07_payments.html",
        payments=payments_list,
        students=students,
        buildings=buildings,
        stats=stats,
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@bp.route("/payment", methods=["GET", "POST"])
@bp.route("/payment/<int:payment_id>", methods=["GET", "POST"])
def payment(payment_id=None):
    if request.method == "POST":
        user_id = request.form.get("user_id")
        amount = request.form.get("amount")
        payment_method = request.form.get("payment_method")
        payment_date = request.form.get("payment_date")
        receipt_number = request.form.get("receipt_number")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO payments (user_id, amount, payment_method, payment_date, receipt_number)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, amount, payment_method, payment_date, receipt_number),
            )
            conn.commit()
            flash("Payment recorded successfully!", "success")
            return redirect(url_for("payments"))
        except Exception as error:
            flash(f"Error recording payment: {error}", "danger")
        finally:
            cursor.close()
            conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get("role") == "landlord":
            cursor.execute(
                """
                SELECT DISTINCT u.user_id, u.username, u.role, u.first_name, u.last_name
                FROM users u
                JOIN room_assignments ra ON u.user_id = ra.user_id
                JOIN rooms r ON ra.room_id = r.room_id
                JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ? AND u.is_active = 1
                ORDER BY u.first_name
            """,
                (session.get("user_id"),),
            )
            users = cursor.fetchall()
        elif session.get("role") == "student":
            cursor.execute(
                "SELECT user_id, username, role, first_name, last_name FROM users WHERE user_id = ? AND is_active = 1",
                (session.get("user_id"),),
            )
            users = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY first_name")
            users = cursor.fetchall()
    except Exception as error:
        flash(f"Error fetching users: {error}", "danger")
        users = []
    finally:
        cursor.close()
        conn.close()

    return render_template("payments/07_payment.html", users=users)


@bp.route("/record_payment", methods=["POST"])
@role_required("admin", "landlord")
def record_payment():
    user_id = request.form.get("user_id")
    assignment_id = request.form.get("assignment_id") or None
    invoice_id = request.form.get("invoice_id") or None
    amount = request.form.get("amount")
    payment_method = request.form.get("payment_method")
    payment_date = request.form.get("payment_date")
    receipt_number = request.form.get("receipt_number")
    payment_period_start = request.form.get("payment_period_start") or None
    payment_period_end = request.form.get("payment_period_end") or None
    notes = request.form.get("notes") or None

    if not user_id or not amount or not payment_method or not payment_date:
        flash("Please fill in all required fields.", "warning")
        return redirect(url_for("payments"))

    if not receipt_number:
        receipt_number = f"PMT-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp() * 1000) % 10000:04d}"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO payments (
                user_id, assignment_id, amount, payment_method, payment_date,
                payment_period_start, payment_period_end, receipt_number,
                recorded_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                assignment_id,
                amount,
                payment_method,
                payment_date,
                payment_period_start,
                payment_period_end,
                receipt_number,
                session.get("user_id"),
                notes,
            ),
        )

        payment_id = cursor.lastrowid
        allocations = allocate_payment_to_invoices(
            connection=conn,
            payment_id=payment_id,
            user_id=user_id,
            payment_amount=amount,
            preferred_invoice_id=invoice_id,
        )

        log_audit_event(
            conn,
            actor_user_id=session.get("user_id"),
            action="record",
            entity_type="payment",
            entity_id=payment_id,
            details={"amount": amount, "allocations": allocations},
        )

        conn.commit()
        flash(f"Payment recorded successfully! Receipt: {receipt_number}", "success")

    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            flash("Receipt number already exists. Please use a different one.", "danger")
        else:
            flash(f"Error recording payment: {error}", "danger")
    except Exception as error:
        flash(f"Error recording payment: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("payments"))


@bp.route("/payment/<int:payment_id>/view")
def view_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT p.*, u.first_name, u.last_name, u.email, u.phone,
                   r.room_number, b.building_name, ra.monthly_rate,
                   rec.first_name as recorded_by_first, rec.last_name as recorded_by_last
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
            LEFT JOIN rooms r ON ra.room_id = r.room_id
            LEFT JOIN buildings b ON r.building_id = b.building_id
            LEFT JOIN users rec ON p.recorded_by = rec.user_id
            WHERE p.payment_id = ?
        """,
            (payment_id,),
        )

        payment_row = cursor.fetchone()

        if not payment_row:
            flash("Payment not found.", "warning")
            return redirect(url_for("payments"))

        if session.get("role") == "student" and payment_row["user_id"] != session.get("user_id"):
            flash("You don't have permission to view this payment.", "danger")
            return redirect(url_for("payments"))

        return render_template("payments/view_payment.html", payment=payment_row)

    except Exception as error:
        flash(f"Error fetching payment: {error}", "danger")
        return redirect(url_for("payments"))
    finally:
        cursor.close()
        conn.close()


@bp.route("/payment/<int:payment_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        amount = request.form.get("amount")
        payment_method = request.form.get("payment_method")
        payment_date = request.form.get("payment_date")
        notes = request.form.get("notes")

        try:
            cursor.execute("SELECT user_id FROM payments WHERE payment_id = ?", (payment_id,))
            row = cursor.fetchone()
            if not row:
                flash("Payment not found.", "warning")
                return redirect(url_for("payments"))

            user_id = row["user_id"]
            remove_payment_allocations(conn, payment_id)

            cursor.execute(
                """
                UPDATE payments
                SET amount = ?, payment_method = ?, payment_date = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = ?
            """,
                (amount, payment_method, payment_date, notes, payment_id),
            )

            allocations = allocate_payment_to_invoices(
                connection=conn,
                payment_id=payment_id,
                user_id=user_id,
                payment_amount=amount,
            )

            log_audit_event(
                conn,
                actor_user_id=session.get("user_id"),
                action="update",
                entity_type="payment",
                entity_id=payment_id,
                details={"amount": amount, "allocations": allocations},
            )

            conn.commit()
            flash("Payment updated successfully!", "success")
            return redirect(url_for("payments"))

        except Exception as error:
            flash(f"Error updating payment: {error}", "danger")
        finally:
            cursor.close()
            conn.close()

    try:
        cursor.execute(
            """
            SELECT p.*, u.first_name, u.last_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.payment_id = ?
        """,
            (payment_id,),
        )

        payment_row = cursor.fetchone()

        if not payment_row:
            flash("Payment not found.", "warning")
            return redirect(url_for("payments"))

        return render_template("payments/edit_payment.html", payment=payment_row)

    except Exception as error:
        flash(f"Error fetching payment: {error}", "danger")
        return redirect(url_for("payments"))
    finally:
        cursor.close()
        conn.close()


@bp.route("/delete_payment/<int:payment_id>", methods=["POST"])
@role_required("admin")
def delete_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        remove_payment_allocations(conn, payment_id)
        cursor.execute("DELETE FROM payments WHERE payment_id = ?", (payment_id,))
        log_audit_event(
            conn,
            actor_user_id=session.get("user_id"),
            action="delete",
            entity_type="payment",
            entity_id=payment_id,
        )
        conn.commit()
        flash("Payment deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting payment: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("payments"))
