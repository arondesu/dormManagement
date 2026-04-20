from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("maintenance", __name__)


@bp.route("/maintenance")
@role_required("admin", "landlord")
def maintenance():
    status_filter = request.args.get("status", "").strip().lower()
    priority_filter = request.args.get("priority", "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT mt.ticket_id, mt.title, mt.priority, mt.status, mt.reported_at, mt.resolved_at,
               r.room_number, b.building_name,
               reporter.first_name AS reporter_first_name, reporter.last_name AS reporter_last_name,
               assignee.first_name AS assignee_first_name, assignee.last_name AS assignee_last_name
        FROM maintenance_tickets mt
        LEFT JOIN rooms r ON r.room_id = mt.room_id
        LEFT JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN users reporter ON reporter.user_id = mt.reported_by
        LEFT JOIN users assignee ON assignee.user_id = mt.assigned_to
        WHERE 1 = 1
    """
    params = []

    if session.get("role") == "landlord":
        query += " AND b.owner_id = ?"
        params.append(session.get("user_id"))

    if status_filter and status_filter != "all":
        query += " AND mt.status = ?"
        params.append(status_filter)

    if priority_filter and priority_filter != "all":
        query += " AND mt.priority = ?"
        params.append(priority_filter)

    query += " ORDER BY mt.ticket_id DESC"

    try:
        cursor.execute(query, params)
        tickets = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading maintenance tickets: {error}", "danger")
        tickets = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "maintenance/12_maintenance.html",
        tickets=tickets,
        status_filter=status_filter,
        priority_filter=priority_filter,
    )


@bp.route("/add_maintenance", methods=["GET", "POST"])
@role_required("admin", "landlord")
def add_maintenance():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        tenant_id = request.form.get("tenant_id") or None
        room_id = request.form.get("room_id") or None
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        priority = (request.form.get("priority") or "medium").strip().lower()
        status = (request.form.get("status") or "open").strip().lower()
        assigned_to = request.form.get("assigned_to") or None
        notes = (request.form.get("notes") or "").strip() or None

        if not title:
            flash("Title is required.", "warning")
            return redirect(url_for("add_maintenance"))

        try:
            cursor.execute(
                """
                INSERT INTO maintenance_tickets (
                    tenant_id, room_id, title, description, priority, status,
                    reported_by, assigned_to, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    room_id,
                    title,
                    description,
                    priority,
                    status,
                    session.get("user_id"),
                    assigned_to,
                    notes,
                ),
            )
            conn.commit()
            flash("Maintenance ticket added successfully!", "success")
            return redirect(url_for("maintenance"))
        except Exception as error:
            flash(f"Error adding maintenance ticket: {error}", "danger")

    rooms_query = """
        SELECT r.room_id, r.room_number, b.building_name
        FROM rooms r
        JOIN buildings b ON b.building_id = r.building_id
        WHERE 1 = 1
    """
    rooms_params = []
    if session.get("role") == "landlord":
        rooms_query += " AND b.owner_id = ?"
        rooms_params.append(session.get("user_id"))
    rooms_query += " ORDER BY b.building_name, r.room_number"

    cursor.execute(rooms_query, rooms_params)
    rooms = cursor.fetchall()

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

    cursor.execute(
        """
        SELECT user_id, first_name, last_name
        FROM users
        WHERE role IN ('admin', 'landlord') AND is_active = 1
        ORDER BY first_name, last_name
        """
    )
    staff = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("maintenance/12_add_maintenance.html", rooms=rooms, tenants=tenants, staff=staff)


@bp.route("/edit_maintenance/<int:ticket_id>", methods=["GET", "POST"])
@role_required("admin", "landlord")
def edit_maintenance(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM maintenance_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        cursor.close()
        conn.close()
        flash("Maintenance ticket not found.", "warning")
        return redirect(url_for("maintenance"))

    if request.method == "POST":
        tenant_id = request.form.get("tenant_id") or None
        room_id = request.form.get("room_id") or None
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        priority = (request.form.get("priority") or "medium").strip().lower()
        status = (request.form.get("status") or "open").strip().lower()
        assigned_to = request.form.get("assigned_to") or None
        notes = (request.form.get("notes") or "").strip() or None

        try:
            if status in {"resolved", "closed"}:
                cursor.execute(
                    """
                    UPDATE maintenance_tickets
                    SET tenant_id = ?, room_id = ?, title = ?, description = ?, priority = ?, status = ?,
                        assigned_to = ?, notes = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE ticket_id = ?
                    """,
                    (tenant_id, room_id, title, description, priority, status, assigned_to, notes, ticket_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE maintenance_tickets
                    SET tenant_id = ?, room_id = ?, title = ?, description = ?, priority = ?, status = ?,
                        assigned_to = ?, notes = ?, resolved_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE ticket_id = ?
                    """,
                    (tenant_id, room_id, title, description, priority, status, assigned_to, notes, ticket_id),
                )

            conn.commit()
            flash("Maintenance ticket updated successfully!", "success")
            return redirect(url_for("maintenance"))
        except Exception as error:
            flash(f"Error updating maintenance ticket: {error}", "danger")

    rooms_query = """
        SELECT r.room_id, r.room_number, b.building_name
        FROM rooms r
        JOIN buildings b ON b.building_id = r.building_id
        WHERE 1 = 1
    """
    rooms_params = []
    if session.get("role") == "landlord":
        rooms_query += " AND b.owner_id = ?"
        rooms_params.append(session.get("user_id"))
    rooms_query += " ORDER BY b.building_name, r.room_number"

    cursor.execute(rooms_query, rooms_params)
    rooms = cursor.fetchall()

    cursor.execute(
        """
        SELECT t.tenant_id, u.first_name, u.last_name
        FROM tenants t
        LEFT JOIN users u ON u.user_id = t.user_id
        WHERE t.status = 'active' OR t.tenant_id = ?
        ORDER BY u.first_name, u.last_name
        """,
        (ticket["tenant_id"],),
    )
    tenants = cursor.fetchall()

    cursor.execute(
        """
        SELECT user_id, first_name, last_name
        FROM users
        WHERE role IN ('admin', 'landlord') AND is_active = 1
        ORDER BY first_name, last_name
        """
    )
    staff = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("maintenance/12_edit_maintenance.html", ticket=ticket, rooms=rooms, tenants=tenants, staff=staff)


@bp.route("/delete_maintenance/<int:ticket_id>", methods=["POST"])
@role_required("admin", "landlord")
def delete_maintenance(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM maintenance_tickets WHERE ticket_id = ?", (ticket_id,))
        conn.commit()
        flash("Maintenance ticket deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting maintenance ticket: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("maintenance"))
