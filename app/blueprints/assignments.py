from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("assignments", __name__)


@bp.route("/edit_assignment/<int:assignment_id>", methods=["GET", "POST"])
def edit_assignment(assignment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT ra.*, u.first_name, u.last_name,
               r.room_number, r.room_id, r.building_id,
               b.building_name
        FROM room_assignments ra
        LEFT JOIN users u ON ra.user_id = u.user_id
        LEFT JOIN rooms r ON ra.room_id = r.room_id
        LEFT JOIN buildings b ON r.building_id = b.building_id
        WHERE ra.assignment_id = ?
    """,
        (assignment_id,),
    )
    assignment = cursor.fetchone()

    if not assignment:
        flash("Assignment not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("assignments"))

    cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active = 1")
    buildings = cursor.fetchall()

    selected_building = request.form.get("building_id") or assignment["building_id"]

    cursor.execute(
        """
        SELECT room_id, room_number, is_available
        FROM rooms
        WHERE building_id = ? OR room_id = ?
        ORDER BY room_number
    """,
        (selected_building, assignment["room_id"]),
    )
    rooms = cursor.fetchall()

    statuses = ["active", "pending", "completed", "cancelled"]

    if request.method == "POST":
        raw_building = request.form.get("building_id") or request.form.get("building_id_hidden")
        raw_room_number = request.form.get("room_number") or request.form.get("room_number_hidden")
        end_date = request.form.get("end_date")
        monthly_rate = request.form.get("monthly_rate")
        status = request.form.get("status")

        if not raw_building or not raw_room_number or status is None:
            flash("Missing required fields.", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for("edit_assignment", assignment_id=assignment_id))

        try:
            new_building_id = int(raw_building)
        except Exception:
            flash("Invalid building selected.", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for("edit_assignment", assignment_id=assignment_id))

        cursor.execute(
            "SELECT room_id FROM rooms WHERE room_number = ? AND building_id = ?",
            (raw_room_number, new_building_id),
        )
        new_room_row = cursor.fetchone()
        if not new_room_row:
            flash("Selected room not found.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for("edit_assignment", assignment_id=assignment_id))

        new_room_id = new_room_row["room_id"]
        old_room_id = assignment["room_id"]

        if end_date:
            try:
                start_date = datetime.strptime(request.form.get("start_date") or assignment.get("start_date"), "%Y-%m-%d")
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
                if parsed_end <= start_date:
                    flash("End date must be later than start date.", "warning")
                    cursor.close()
                    conn.close()
                    return redirect(url_for("edit_assignment", assignment_id=assignment_id))
            except Exception:
                pass

        cursor.execute(
            """
            UPDATE room_assignments
            SET room_id = ?, end_date = ?, monthly_rate = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE assignment_id = ?
        """,
            (new_room_id, end_date or None, monthly_rate or None, status, assignment_id),
        )

        if status == "completed":
            cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = ?", (new_room_id,))
        else:
            cursor.execute("UPDATE rooms SET is_available = 0 WHERE room_id = ?", (new_room_id,))

        if old_room_id != new_room_id:
            cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = ?", (old_room_id,))

        conn.commit()
        flash("Assignment updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("assignments"))

    cursor.close()
    conn.close()
    return render_template(
        "edit_assignment.html",
        assignment=assignment,
        buildings=buildings,
        rooms=rooms,
        statuses=statuses,
    )


@bp.route("/admin_assign_room", methods=["GET", "POST"])
def admin_assign_room():
    conn = get_db_connection()
    cursor = conn.cursor()

    if session.get("role") == "admin":
        cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active=1")
    else:
        cursor.execute(
            "SELECT building_id, building_name FROM buildings WHERE is_active=1 AND owner_id=?",
            (session.get("user_id"),),
        )
    buildings = cursor.fetchall()

    if session.get("role") == "admin":
        cursor.execute(
            """
            SELECT r.room_id, r.room_number, b.building_name
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.is_available=1
        """
        )
    else:
        cursor.execute(
            """
            SELECT r.room_id, r.room_number, b.building_name
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.is_available=1 AND b.owner_id=?
        """,
            (session.get("user_id"),),
        )
    rooms = cursor.fetchall()

    if request.method == "POST":
        username_or_email = request.form.get("username_or_email").strip()
        room_id = request.form.get("room_id")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        monthly_rate = request.form.get("monthly_rate")
        assigned_by = request.form.get("assigned_by")

        if not username_or_email or not room_id or not start_date:
            flash("Username/email, room, and start date are required.", "danger")
            return redirect(request.path)

        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
                if parsed_end <= parsed_start:
                    flash("End date must be later than start date.", "danger")
                    return redirect(request.path)
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(request.path)

        cursor.execute(
            """
            SELECT user_id FROM users
            WHERE username=? OR email=?
        """,
            (username_or_email, username_or_email),
        )
        user = cursor.fetchone()
        if not user:
            flash("User not found. Please enter a valid username or email.", "danger")
            return redirect(request.path)
        user_id = user["user_id"]

        if session.get("role") == "admin":
            cursor.execute("SELECT is_available FROM rooms WHERE room_id=?", (room_id,))
        else:
            cursor.execute(
                """
                SELECT r.is_available
                FROM rooms r
                JOIN buildings b ON r.building_id = b.building_id
                WHERE r.room_id=? AND b.owner_id=?
            """,
                (room_id, session.get("user_id")),
            )
        room = cursor.fetchone()
        if not room:
            flash("Room not found or not allowed.", "danger")
            return redirect(request.path)
        if room["is_available"] == 0:
            flash("Room is not available.", "danger")
            return redirect(request.path)

        cursor.execute(
            """
            INSERT INTO room_assignments
            (user_id, room_id, start_date, end_date, monthly_rate, status, assigned_by)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
            (user_id, room_id, start_date, end_date, monthly_rate, assigned_by),
        )

        cursor.execute("UPDATE rooms SET is_available=0 WHERE room_id=?", (room_id,))
        conn.commit()

        flash("Room successfully assigned!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("users"))

    cursor.close()
    conn.close()
    return render_template(
        "06_assign_room.html",
        buildings=buildings,
        rooms=rooms,
        current_user={"user_id": session.get("user_id")},
    )


@bp.route("/assignments")
def assignments():
    conn = get_db_connection()
    cursor = conn.cursor()
    assignments_list = []
    try:
        if session.get("role") == "landlord":
            cursor.execute(
                """
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date,
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY ra.assignment_id
            """,
                (session.get("user_id"),),
            )
        elif session.get("role") == "student":
            cursor.execute(
                """
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date,
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE ra.user_id = ?
                ORDER BY ra.assignment_id
            """,
                (session.get("user_id"),),
            )
        else:
            cursor.execute(
                """
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date,
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                ORDER BY ra.assignment_id
            """
            )
        assignments_list = cursor.fetchall()
        converted = []
        for row in assignments_list:
            assignment = dict(row)
            assignment["monthly_rate"] = float(assignment["monthly_rate"])
            converted.append(assignment)
    except Exception as error:
        flash(f"Error fetching assignments: {error}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("06_assignments.html", assignments=converted)


@bp.route("/api/assignments/<int:user_id>")
@role_required("admin", "landlord")
def get_user_assignments(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT ra.assignment_id, ra.monthly_rate, r.room_number, b.building_name
            FROM room_assignments ra
            LEFT JOIN rooms r ON ra.room_id = r.room_id
            LEFT JOIN buildings b ON r.building_id = b.building_id
            WHERE ra.user_id = ? AND ra.status = 'active'
            ORDER BY ra.start_date DESC
        """,
            (user_id,),
        )

        assignments_list = cursor.fetchall()

        return jsonify({"assignments": [dict(item) for item in assignments_list]})

    except Exception as error:
        return jsonify({"error": str(error)}), 500
    finally:
        cursor.close()
        conn.close()
