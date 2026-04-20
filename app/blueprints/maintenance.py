from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("maintenance", __name__)


@bp.route("/maintenance")
@bp.route("/maintenance_requests")
@role_required("admin", "landlord", "student")
def maintenance():
    status_filter = request.args.get("status", "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT mr.request_id, mr.title, mr.description, mr.status, mr.created_at, mr.resolved_at,
               r.room_number, b.building_name,
               requester.first_name AS requester_first_name, requester.last_name AS requester_last_name,
               handler.first_name AS handler_first_name, handler.last_name AS handler_last_name
        FROM maintenance_requests mr
        LEFT JOIN rooms r ON r.room_id = mr.room_id
        LEFT JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN users requester ON requester.user_id = mr.user_id
        LEFT JOIN users handler ON handler.user_id = mr.handled_by
        WHERE 1 = 1
    """
    params = []

    if session.get("role") == "landlord":
        query += " AND b.owner_id = ?"
        params.append(session.get("user_id"))
    elif session.get("role") == "student":
        query += " AND mr.user_id = ?"
        params.append(session.get("user_id"))

    if status_filter and status_filter != "all":
        query += " AND mr.status = ?"
        params.append(status_filter)

    query += " ORDER BY mr.request_id DESC"

    try:
        cursor.execute(query, params)
        requests_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading maintenance requests: {error}", "danger")
        requests_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "maintenance/12_maintenance.html",
        tickets=requests_list,
        status_filter=status_filter,
    )


@bp.route("/add_maintenance", methods=["GET", "POST"])
@bp.route("/add_maintenance_request", methods=["GET", "POST"])
@role_required("admin", "landlord", "student")
def add_maintenance():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        room_id = request.form.get("room_id") or None
        request_user_id = request.form.get("user_id") or session.get("user_id")
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        status = (request.form.get("status") or "open").strip().lower()
        handled_by = request.form.get("handled_by") or None

        if not title:
            flash("Title is required.", "warning")
            return redirect(url_for("add_maintenance"))

        try:
            cursor.execute(
                """
                INSERT INTO maintenance_requests (
                    user_id, room_id, title, description, status, handled_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_user_id,
                    room_id,
                    title,
                    description,
                    status,
                    handled_by,
                ),
            )
            conn.commit()
            flash("Maintenance request added successfully!", "success")
            return redirect(url_for("maintenance"))
        except Exception as error:
            flash(f"Error adding maintenance request: {error}", "danger")

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

    if session.get("role") == "student":
        cursor.execute(
            """
            SELECT user_id, first_name, last_name
            FROM users
            WHERE user_id = ?
            """,
            (session.get("user_id"),),
        )
    else:
        cursor.execute(
            """
            SELECT user_id, first_name, last_name
            FROM users
            WHERE role = 'student' AND is_active = 1
            ORDER BY first_name, last_name
            """
        )
    requesters = cursor.fetchall()

    cursor.execute(
        """
        SELECT user_id, first_name, last_name
        FROM users
        WHERE role IN ('admin', 'landlord') AND is_active = 1
        ORDER BY first_name, last_name
        """
    )
    handlers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("maintenance/12_add_maintenance.html", rooms=rooms, requesters=requesters, handlers=handlers)


@bp.route("/edit_maintenance/<int:ticket_id>", methods=["GET", "POST"])
@bp.route("/edit_maintenance_request/<int:ticket_id>", methods=["GET", "POST"])
@role_required("admin", "landlord", "student")
def edit_maintenance(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        cursor.close()
        conn.close()
        flash("Maintenance request not found.", "warning")
        return redirect(url_for("maintenance"))

    if session.get("role") == "student" and ticket["user_id"] != session.get("user_id"):
        cursor.close()
        conn.close()
        flash("You do not have access to edit this request.", "danger")
        return redirect(url_for("maintenance"))

    if request.method == "POST":
        room_id = request.form.get("room_id") or None
        request_user_id = request.form.get("user_id") or ticket["user_id"]
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        status = (request.form.get("status") or "open").strip().lower()
        handled_by = request.form.get("handled_by") or None

        try:
            if status in {"resolved", "closed"}:
                cursor.execute(
                    """
                    UPDATE maintenance_requests
                    SET user_id = ?, room_id = ?, title = ?, description = ?, status = ?, handled_by = ?,
                        resolved_at = CURRENT_TIMESTAMP
                    WHERE request_id = ?
                    """,
                    (request_user_id, room_id, title, description, status, handled_by, ticket_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE maintenance_requests
                    SET user_id = ?, room_id = ?, title = ?, description = ?, status = ?, handled_by = ?,
                        resolved_at = NULL
                    WHERE request_id = ?
                    """,
                    (request_user_id, room_id, title, description, status, handled_by, ticket_id),
                )

            conn.commit()
            flash("Maintenance request updated successfully!", "success")
            return redirect(url_for("maintenance"))
        except Exception as error:
            flash(f"Error updating maintenance request: {error}", "danger")

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
        SELECT user_id, first_name, last_name
        FROM users
        WHERE role = 'student' AND is_active = 1 OR user_id = ?
        ORDER BY first_name, last_name
        """,
        (ticket["user_id"],),
    )
    requesters = cursor.fetchall()

    cursor.execute(
        """
        SELECT user_id, first_name, last_name
        FROM users
        WHERE role IN ('admin', 'landlord') AND is_active = 1
        ORDER BY first_name, last_name
        """
    )
    handlers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("maintenance/12_edit_maintenance.html", ticket=ticket, rooms=rooms, requesters=requesters, handlers=handlers)


@bp.route("/delete_maintenance/<int:ticket_id>", methods=["POST"])
@bp.route("/delete_maintenance_request/<int:ticket_id>", methods=["POST"])
@role_required("admin", "landlord")
def delete_maintenance(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM maintenance_requests WHERE request_id = ?", (ticket_id,))
        conn.commit()
        flash("Maintenance request deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting maintenance request: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("maintenance"))
