from flask import Blueprint, redirect, render_template, session, url_for

from db import get_db_connection


bp = Blueprint("main", __name__)


@bp.route("/get_rooms/<int:building_id>")
def get_rooms(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT room_number FROM rooms WHERE building_id = ? AND is_available = 1",
        (building_id,),
    )
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"rooms": [r["room_number"] for r in rooms]}


@bp.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    role = session.get("role")

    conn = get_db_connection()
    cursor = conn.cursor()

    collections_this_month = 0.0
    occupancy_pct = 0.0

    if role == "admin":
        cursor.execute("SELECT COUNT(*) AS total_rooms FROM rooms")
        total_rooms = cursor.fetchone()["total_rooms"]

        cursor.execute("SELECT COUNT(*) AS occupied FROM rooms WHERE is_available = 0")
        occupied = cursor.fetchone()["occupied"]

        cursor.execute("SELECT COUNT(*) AS available FROM rooms WHERE is_available = 1")
        available = cursor.fetchone()["available"]

        cursor.execute("SELECT COUNT(*) AS pending FROM room_assignments WHERE status='pending'")
        pending = cursor.fetchone()["pending"]

        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS collections_this_month
            FROM payments
            WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')
            """
        )
        collections_this_month = float(cursor.fetchone()["collections_this_month"] or 0)
    elif role == "landlord":
        cursor.execute(
            "SELECT COUNT(*) AS total_buildings FROM buildings WHERE owner_id = ?",
            (user_id,),
        )
        total_buildings = cursor.fetchone()["total_buildings"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total_rooms,
                   SUM(CASE WHEN is_available = 0 THEN 1 ELSE 0 END) AS occupied,
                   SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) AS available
            FROM rooms
            WHERE building_id IN (SELECT building_id FROM buildings WHERE owner_id = ?)
        """,
            (user_id,),
        )
        rooms_stats = cursor.fetchone()
        total_rooms = rooms_stats["total_rooms"] or 0
        occupied = rooms_stats["occupied"] or 0
        available = rooms_stats["available"] or 0

        cursor.execute(
            """
            SELECT COUNT(*) AS pending
            FROM room_assignments ra
            JOIN rooms r ON ra.room_id = r.room_id
            WHERE r.building_id IN (SELECT building_id FROM buildings WHERE owner_id = ?)
              AND ra.status = 'pending'
        """,
            (user_id,),
        )
        pending = cursor.fetchone()["pending"]

        cursor.execute(
            """
            SELECT COALESCE(SUM(p.amount), 0) AS collections_this_month
            FROM payments p
                        LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                        LEFT JOIN rooms r ON ra.room_id = r.room_id
                        LEFT JOIN buildings b ON r.building_id = b.building_id
                        WHERE b.owner_id = ?
              AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            """,
            (user_id,),
        )
        collections_this_month = float(cursor.fetchone()["collections_this_month"] or 0)
    else:
        total_rooms = occupied = available = pending = None

    if total_rooms:
        occupancy_pct = round((occupied / total_rooms) * 100, 1)

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        role=role,
        total_rooms=total_rooms,
        occupied=occupied,
        available=available,
        pending=pending,
        collections_this_month=collections_this_month,
        occupancy_pct=occupancy_pct,
    )
