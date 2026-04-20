from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from db import get_db_connection


bp = Blueprint("rooms", __name__)


@bp.route("/landlord_rooms/<int:building_id>/<int:floor_number>")
def landlord_rooms(building_id, floor_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    if session.get("role") == "admin":
        cursor.execute(
            """
            SELECT room_id, room_number
            FROM rooms
            WHERE building_id=? AND floor_number=? AND is_available=1
        """,
            (building_id, floor_number),
        )
    else:
        cursor.execute(
            """
            SELECT r.room_id, r.room_number
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.building_id=? AND r.floor_number=? AND r.is_available=1 AND b.owner_id=?
        """,
            (building_id, floor_number, session.get("user_id")),
        )

    rooms_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([dict(r) for r in rooms_list])


@bp.route("/edit_room/<int:room_id>", methods=["GET", "POST"])
def edit_room(room_id):
    if session.get("role") == "student":
        flash("You are not allowed to perform this action.", "danger")
        return redirect(url_for("rooms"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.*, b.building_name, b.total_floors, t.type_name
        FROM rooms r
        LEFT JOIN buildings b ON r.building_id = b.building_id
        LEFT JOIN room_types t ON r.type_id = t.type_id
        WHERE r.room_id = ?
    """,
        (room_id,),
    )
    room = cursor.fetchone()

    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if not room:
        flash("Room not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    total_floors = room["total_floors"]
    floors = list(range(1, total_floors + 1))

    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if request.method == "POST":
        room_number = request.form.get("room_number", "").strip()
        floor_number = request.form.get("floor_number", "").strip()
        type_id = request.form.get("type_id")
        is_available = request.form.get("is_available", "1")

        if not room_number or not floor_number:
            flash("Room number and floor number are required.", "warning")
            return redirect(url_for("edit_room", room_id=room_id))

        cursor.execute(
            """
            UPDATE rooms
            SET room_number = ?, floor_number = ?, type_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE room_id = ?
        """,
            (room_number, floor_number, type_id, room_id),
        )

        conn.commit()
        flash("Room updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.close()
    conn.close()

    return render_template("rooms/05_edit_rooms.html", room=room, room_types=room_types, floors=floors)


@bp.route("/delete_room/<int:room_id>", methods=["POST"])
def delete_room(room_id):
    if session.get("role") not in ["admin", "landlord"]:
        flash("You do not have permission to delete rooms.", "danger")
        return redirect(url_for("rooms"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    room = cursor.fetchone()
    if not room:
        flash("Room not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.execute(
        """
        SELECT COUNT(*) as active_count
        FROM room_assignments
        WHERE room_id = ? AND status = 'active'
    """,
        (room_id,),
    )
    active_count = cursor.fetchone()["active_count"]

    if not room["is_available"] or active_count > 0:
        flash("Cannot delete room. It is either occupied or assigned to a tenant.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Room deleted successfully.", "success")
    return redirect(url_for("rooms"))


@bp.route("/add_room", methods=["GET", "POST"])
def add_room():
    if session.get("role") not in ["admin", "landlord"]:
        flash("You do not have permission to add rooms.", "danger")
        return redirect(url_for("rooms"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if session.get("role") == "admin":
        cursor.execute("SELECT building_id, building_name, total_floors FROM buildings WHERE is_active = 1")
    else:
        cursor.execute(
            """
            SELECT building_id, building_name, total_floors
            FROM buildings
            WHERE is_active = 1 AND owner_id = ?
        """,
            (session.get("user_id"),),
        )

    buildings = cursor.fetchall()

    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if request.method == "POST":
        building_id = request.form.get("building_id")
        floor_number = request.form.get("floor_number")
        room_number = request.form.get("room_number").strip()
        type_id = request.form.get("type_id")

        if not building_id or not floor_number or not room_number or not type_id:
            flash("All fields are required.", "warning")
            return redirect(url_for("add_room"))

        if session.get("role") == "landlord":
            cursor.execute(
                "SELECT COUNT(*) as count FROM buildings WHERE building_id = ? AND owner_id = ?",
                (building_id, session.get("user_id")),
            )
            allowed = cursor.fetchone()["count"]
            if allowed == 0:
                flash("You cannot add a room to a building you do not own.", "danger")
                return redirect(url_for("add_room"))

        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM rooms
            WHERE building_id = ? AND room_number = ?
        """,
            (building_id, room_number),
        )
        exists = cursor.fetchone()["count"]

        if exists > 0:
            flash(f"Room number '{room_number}' already exists in the selected building.", "warning")
            return redirect(url_for("add_room"))

        cursor.execute(
            """
            INSERT INTO rooms (building_id, room_number, floor_number, type_id, is_available, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
            (building_id, room_number, floor_number, type_id),
        )
        conn.commit()

        flash("Room added successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.close()
    conn.close()
    return render_template("rooms/05_add_room.html", buildings=buildings, room_types=room_types)


@bp.route("/building_floors/<int:building_id>")
def building_floors(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total_floors FROM buildings WHERE building_id = ?", (building_id,))
    building = cursor.fetchone()
    cursor.close()
    conn.close()

    if building:
        return jsonify([i for i in range(1, building["total_floors"] + 1)])
    return jsonify([])


@bp.route("/room_types")
def room_types():
    conn = get_db_connection()
    cursor = conn.cursor()
    types = []
    try:
        cursor.execute(
            """
            SELECT type_id, type_name, base_rate, capacity, description, is_active
            FROM room_types
            ORDER BY type_id
        """
        )
        types = cursor.fetchall()
    except Exception as error:
        flash(f"Error fetching room types: {error}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("rooms/04_room_types.html", room_types=types)


@bp.route("/rooms")
def rooms():
    search = request.args.get("search", "").strip()
    building_filter = request.args.get("building", "").strip()
    status_filter = request.args.get("status", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    rooms_list = []

    try:
        query = """
            SELECT r.room_id, r.room_number, r.floor_number, b.building_name,
                   rt.type_name, r.is_available, b.owner_id
            FROM rooms r
            LEFT JOIN buildings b ON r.building_id = b.building_id
            LEFT JOIN room_types rt ON r.type_id = rt.type_id
            WHERE 1=1
        """
        params = []

        if session.get("role") == "landlord":
            query += " AND b.owner_id = ?"
            params.append(session.get("user_id"))
        elif session.get("role") == "student":
            query += " AND r.is_available = 1"

        if search:
            query += " AND r.room_number LIKE ?"
            params.append(f"%{search}%")

        if building_filter and building_filter.lower() != "all buildings":
            query += " AND b.building_name = ?"
            params.append(building_filter)

        if status_filter and status_filter.lower() != "all status":
            if status_filter.lower() == "available":
                query += " AND r.is_available = 1"
            else:
                query += " AND r.is_available = 0"

        query += " ORDER BY r.room_id"

        cursor.execute(query, params)
        rooms_list = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT building_name FROM buildings ORDER BY building_name")
        buildings_list = [row["building_name"] for row in cursor.fetchall()]

    except Exception as error:
        flash(f"Error fetching rooms: {error}", "danger")
        buildings_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "rooms/05_rooms.html",
        rooms=rooms_list,
        search=search,
        building_filter=building_filter,
        status_filter=status_filter,
        buildings_list=buildings_list,
    )
