from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from db import get_db_connection
from app.services.billing_service import (
    derive_invoice_status,
    generate_monthly_invoices,
    refresh_invoice_status,
)
from app.utils.audit import log_audit_event

from .common import role_required


bp = Blueprint("billing", __name__)


def _invoice_status(total_amount, amount_paid, selected_status, due_date=None):
    return derive_invoice_status(
        total_amount=total_amount,
        amount_paid=amount_paid,
        due_date=due_date,
        force_status=selected_status,
    )


@bp.route("/invoices")
@role_required("admin", "landlord")
def invoices():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT i.invoice_id, i.invoice_number, i.issue_date, i.due_date, i.total_amount, i.amount_paid, i.status,
               u.first_name, u.last_name, r.room_number, b.building_name
        FROM invoices i
        LEFT JOIN tenants t ON t.tenant_id = i.tenant_id
        LEFT JOIN users u ON u.user_id = t.user_id
        LEFT JOIN room_assignments ra ON ra.assignment_id = i.assignment_id
        LEFT JOIN rooms r ON r.room_id = ra.room_id
        LEFT JOIN buildings b ON b.building_id = r.building_id
        WHERE 1 = 1
    """
    params = []

    if session.get("role") == "landlord":
        query += " AND b.owner_id = ?"
        params.append(session.get("user_id"))

    if search:
        like_search = f"%{search}%"
        query += " AND (i.invoice_number LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR r.room_number LIKE ?)"
        params.extend([like_search, like_search, like_search, like_search])

    if status_filter and status_filter != "all":
        query += " AND i.status = ?"
        params.append(status_filter)

    query += " ORDER BY i.invoice_id DESC"

    try:
        cursor.execute(query, params)
        invoices_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading invoices: {error}", "danger")
        invoices_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template("billing/11_invoices.html", invoices=invoices_list, search=search, status_filter=status_filter)


@bp.route("/api/invoices/user/<int:user_id>")
@role_required("admin", "landlord")
def get_user_open_invoices(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT i.invoice_id, i.invoice_number, i.due_date,
                   (i.total_amount - i.amount_paid) AS balance_due
            FROM invoices i
            LEFT JOIN tenants t ON t.tenant_id = i.tenant_id
            WHERE t.user_id = ?
              AND i.status IN ('unpaid', 'partial', 'overdue')
            ORDER BY i.due_date ASC, i.invoice_id ASC
            """,
            (user_id,),
        )
        invoices_list = [dict(row) for row in cursor.fetchall()]
        return jsonify({"invoices": invoices_list})
    finally:
        cursor.close()
        conn.close()


@bp.route("/invoices/generate_monthly", methods=["POST"])
@role_required("admin", "landlord")
def generate_monthly_invoices_route():
    issue_date = request.form.get("issue_date") or datetime.now().strftime("%Y-%m-%d")
    due_date = request.form.get("due_date") or issue_date

    owner_scope = session.get("user_id") if session.get("role") == "landlord" else None

    conn = get_db_connection()
    try:
        result = generate_monthly_invoices(
            connection=conn,
            issue_date=issue_date,
            due_date=due_date,
            actor_user_id=session.get("user_id"),
            owner_user_id=owner_scope,
        )
        log_audit_event(
            conn,
            actor_user_id=session.get("user_id"),
            action="generate_monthly_invoices",
            entity_type="invoice",
            details=result,
        )
        conn.commit()
        flash(f"Generated {result['generated']} invoice(s), skipped {result['skipped']} existing.", "success")
    except Exception as error:
        conn.rollback()
        flash(f"Error generating invoices: {error}", "danger")
    finally:
        conn.close()

    return redirect(url_for("invoices"))


@bp.route("/add_invoice", methods=["GET", "POST"])
@role_required("admin", "landlord")
def add_invoice():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        tenant_id = request.form.get("tenant_id") or None
        assignment_id = request.form.get("assignment_id") or None
        invoice_number = (request.form.get("invoice_number") or "").strip()
        issue_date = request.form.get("issue_date") or datetime.now().strftime("%Y-%m-%d")
        due_date = request.form.get("due_date") or issue_date
        period_start = request.form.get("period_start") or None
        period_end = request.form.get("period_end") or None
        subtotal = request.form.get("subtotal") or 0
        late_fee = request.form.get("late_fee") or 0
        amount_paid = request.form.get("amount_paid") or 0
        notes = (request.form.get("notes") or "").strip() or None
        selected_status = (request.form.get("status") or "unpaid").strip().lower()

        total_amount = float(subtotal) + float(late_fee)

        if not invoice_number:
            timestamp_part = datetime.now().strftime("%Y%m%d%H%M%S")
            invoice_number = f"INV-{timestamp_part}"

        status = _invoice_status(total_amount, amount_paid, selected_status, due_date)

        try:
            cursor.execute(
                """
                INSERT INTO invoices (
                    tenant_id, assignment_id, invoice_number, issue_date, due_date,
                    period_start, period_end, subtotal, late_fee, total_amount,
                    amount_paid, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    assignment_id,
                    invoice_number,
                    issue_date,
                    due_date,
                    period_start,
                    period_end,
                    subtotal,
                    late_fee,
                    total_amount,
                    amount_paid,
                    status,
                    notes,
                ),
            )
            invoice_id = cursor.lastrowid
            refresh_invoice_status(conn, invoice_id, force_status=selected_status)
            log_audit_event(
                conn,
                actor_user_id=session.get("user_id"),
                action="create",
                entity_type="invoice",
                entity_id=invoice_id,
                details={"invoice_number": invoice_number, "total_amount": total_amount},
            )
            conn.commit()
            flash("Invoice added successfully!", "success")
            return redirect(url_for("invoices"))
        except Exception as error:
            flash(f"Error adding invoice: {error}", "danger")

    cursor.execute(
        """
        SELECT t.tenant_id, u.first_name, u.last_name
        FROM tenants t
        LEFT JOIN users u ON u.user_id = t.user_id
        WHERE t.status = 'active'
        ORDER BY u.first_name, u.last_name
        """
    )
    tenants = cursor.fetchall()

    assignments_query = """
        SELECT ra.assignment_id, r.room_number, b.building_name, u.first_name, u.last_name
        FROM room_assignments ra
        JOIN rooms r ON r.room_id = ra.room_id
        JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN users u ON u.user_id = ra.user_id
        WHERE ra.status = 'active'
    """
    assignments_params = []
    if session.get("role") == "landlord":
        assignments_query += " AND b.owner_id = ?"
        assignments_params.append(session.get("user_id"))
    assignments_query += " ORDER BY b.building_name, r.room_number"

    cursor.execute(assignments_query, assignments_params)
    assignments = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("billing/11_add_invoice.html", tenants=tenants, assignments=assignments)


@bp.route("/edit_invoice/<int:invoice_id>", methods=["GET", "POST"])
@role_required("admin", "landlord")
def edit_invoice(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
    invoice = cursor.fetchone()

    if not invoice:
        cursor.close()
        conn.close()
        flash("Invoice not found.", "warning")
        return redirect(url_for("invoices"))

    if request.method == "POST":
        tenant_id = request.form.get("tenant_id") or None
        assignment_id = request.form.get("assignment_id") or None
        invoice_number = (request.form.get("invoice_number") or "").strip()
        issue_date = request.form.get("issue_date") or invoice["issue_date"]
        due_date = request.form.get("due_date") or invoice["due_date"]
        period_start = request.form.get("period_start") or None
        period_end = request.form.get("period_end") or None
        subtotal = request.form.get("subtotal") or 0
        late_fee = request.form.get("late_fee") or 0
        amount_paid = request.form.get("amount_paid") or 0
        notes = (request.form.get("notes") or "").strip() or None
        selected_status = (request.form.get("status") or "unpaid").strip().lower()

        total_amount = float(subtotal) + float(late_fee)
        status = _invoice_status(total_amount, amount_paid, selected_status, due_date)

        try:
            cursor.execute(
                """
                UPDATE invoices
                SET tenant_id = ?, assignment_id = ?, invoice_number = ?, issue_date = ?, due_date = ?,
                    period_start = ?, period_end = ?, subtotal = ?, late_fee = ?, total_amount = ?,
                    amount_paid = ?, status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE invoice_id = ?
                """,
                (
                    tenant_id,
                    assignment_id,
                    invoice_number,
                    issue_date,
                    due_date,
                    period_start,
                    period_end,
                    subtotal,
                    late_fee,
                    total_amount,
                    amount_paid,
                    status,
                    notes,
                    invoice_id,
                ),
            )
            refresh_invoice_status(conn, invoice_id, force_status=selected_status)
            log_audit_event(
                conn,
                actor_user_id=session.get("user_id"),
                action="update",
                entity_type="invoice",
                entity_id=invoice_id,
                details={"invoice_number": invoice_number, "status": status},
            )
            conn.commit()
            flash("Invoice updated successfully!", "success")
            return redirect(url_for("invoices"))
        except Exception as error:
            flash(f"Error updating invoice: {error}", "danger")

    cursor.execute(
        """
        SELECT t.tenant_id, u.first_name, u.last_name
        FROM tenants t
        LEFT JOIN users u ON u.user_id = t.user_id
        WHERE t.status = 'active' OR t.tenant_id = ?
        ORDER BY u.first_name, u.last_name
        """,
        (invoice["tenant_id"],),
    )
    tenants = cursor.fetchall()

    assignments_query = """
        SELECT ra.assignment_id, r.room_number, b.building_name, u.first_name, u.last_name
        FROM room_assignments ra
        JOIN rooms r ON r.room_id = ra.room_id
        JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN users u ON u.user_id = ra.user_id
        WHERE ra.status = 'active' OR ra.assignment_id = ?
    """
    assignments_params = [invoice["assignment_id"]]
    if session.get("role") == "landlord":
        assignments_query += " AND b.owner_id = ?"
        assignments_params.append(session.get("user_id"))
    assignments_query += " ORDER BY b.building_name, r.room_number"

    cursor.execute(assignments_query, assignments_params)
    assignments = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("billing/11_edit_invoice.html", invoice=invoice, tenants=tenants, assignments=assignments)


@bp.route("/delete_invoice/<int:invoice_id>", methods=["POST"])
@role_required("admin", "landlord")
def delete_invoice(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM invoices WHERE invoice_id = ?", (invoice_id,))
        log_audit_event(
            conn,
            actor_user_id=session.get("user_id"),
            action="delete",
            entity_type="invoice",
            entity_id=invoice_id,
        )
        conn.commit()
        flash("Invoice deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting invoice: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("invoices"))
