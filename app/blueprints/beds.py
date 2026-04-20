from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("beds", __name__)


@bp.route("/beds")
@role_required("admin", "landlord")
def beds():
    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT bd.bed_id, bd.bed_label, bd.is_available, bd.notes,
               r.room_id, r.room_number, b.building_name,
               t.tenant_id, u.first_name AS tenant_first_name, u.last_name AS tenant_last_name
        FROM beds bd
        JOIN rooms r ON r.room_id = bd.room_id
        JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN tenants t ON t.tenant_id = bd.occupied_by_tenant_id
        LEFT JOIN users u ON u.user_id = t.user_id
        WHERE 1 = 1
    """
    params = []

    if session.get("role") == "landlord":
        query += " AND b.owner_id = ?"
        params.append(session.get("user_id"))

    if search:
        query += " AND (bd.bed_label LIKE ? OR r.room_number LIKE ? OR b.building_name LIKE ?)"
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search])

    query += " ORDER BY b.building_name, r.room_number, bd.bed_label"

    try:
        cursor.execute(query, params)
        beds_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading beds: {error}", "danger")
        beds_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template("beds/10_beds.html", beds=beds_list, search=search)


@bp.route("/add_bed", methods=["GET", "POST"])
@role_required("admin", "landlord")
def add_bed():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        room_id = request.form.get("room_id")
        bed_label = (request.form.get("bed_label") or "").strip()
        occupied_by_tenant_id = request.form.get("occupied_by_tenant_id") or None
        notes = (request.form.get("notes") or "").strip() or None

        if not room_id or not bed_label:
            flash("Room and bed label are required.", "warning")
            return redirect(url_for("add_bed"))

        is_available = 0 if occupied_by_tenant_id else 1

        try:
            cursor.execute(
                """
                INSERT INTO beds (room_id, bed_label, occupied_by_tenant_id, is_available, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (room_id, bed_label, occupied_by_tenant_id, is_available, notes),
            )
            conn.commit()
            flash("Bed added successfully!", "success")
            return redirect(url_for("beds"))
        except Exception as error:
            flash(f"Error adding bed: {error}", "danger")

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
    tenants_list = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("beds/10_add_bed.html", rooms=rooms, tenants=tenants_list)


@bp.route("/edit_bed/<int:bed_id>", methods=["GET", "POST"])
@role_required("admin", "landlord")
def edit_bed(bed_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM beds WHERE bed_id = ?", (bed_id,))
    bed = cursor.fetchone()

    if not bed:
        cursor.close()
        conn.close()
        flash("Bed not found.", "warning")
        return redirect(url_for("beds"))

    if request.method == "POST":
        room_id = request.form.get("room_id")
        bed_label = (request.form.get("bed_label") or "").strip()
        occupied_by_tenant_id = request.form.get("occupied_by_tenant_id") or None
        notes = (request.form.get("notes") or "").strip() or None
        is_available = 0 if occupied_by_tenant_id else 1

        try:
            cursor.execute(
                """
                UPDATE beds
                SET room_id = ?, bed_label = ?, occupied_by_tenant_id = ?, is_available = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE bed_id = ?
                """,
                (room_id, bed_label, occupied_by_tenant_id, is_available, notes, bed_id),
            )
            conn.commit()
            flash("Bed updated successfully!", "success")
            return redirect(url_for("beds"))
        except Exception as error:
            flash(f"Error updating bed: {error}", "danger")

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
        (bed["occupied_by_tenant_id"],),
    )
    tenants_list = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("beds/10_edit_bed.html", bed=bed, rooms=rooms, tenants=tenants_list)


@bp.route("/delete_bed/<int:bed_id>", methods=["POST"])
@role_required("admin", "landlord")
def delete_bed(bed_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM beds WHERE bed_id = ?", (bed_id,))
        conn.commit()
        flash("Bed deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting bed: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("beds"))
