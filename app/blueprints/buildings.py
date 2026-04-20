from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("buildings", __name__)


@bp.route("/delete_building/<int:building_id>", methods=["POST"])
def delete_building(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM buildings WHERE building_id = ?", (building_id,))
        building = cursor.fetchone()

        if not building:
            flash("Building not found.", "danger")
            return redirect(url_for("buildings"))

        cursor.execute("SELECT room_id FROM rooms WHERE building_id = ?", (building_id,))
        rooms = cursor.fetchall()

        if rooms:
            room_ids = [r["room_id"] for r in rooms]
            cursor.execute(
                f"""
                SELECT assignment_id FROM room_assignments
                WHERE room_id IN ({','.join('?' * len(room_ids))})
                """,
                room_ids,
            )
            assignments = cursor.fetchall()

            if assignments:
                flash("Cannot delete building. One or more rooms still have occupants or assignments.", "warning")
                return redirect(url_for("buildings"))

        cursor.execute("DELETE FROM buildings WHERE building_id = ?", (building_id,))
        conn.commit()
        flash("Building deleted successfully!", "success")

    except Exception as error:
        print("Error deleting building:", error)
        flash("Error deleting building.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("buildings"))


@bp.route("/buildings")
def buildings():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    buildings_list = []

    try:
        query = """
            SELECT b.building_id, b.building_name, b.address, b.total_floors,
                   b.is_active, b.owner_id, u.username AS owner_username, b.created_at
            FROM buildings b
            LEFT JOIN users u ON b.owner_id = u.user_id
            WHERE 1=1
        """
        params = []

        if session.get("role") == "landlord":
            query += " AND b.owner_id = ?"
            params.append(session.get("user_id"))
        elif session.get("role") == "student":
            query += " AND b.is_active = 1"

        if search:
            query += " AND (b.building_name LIKE ? OR b.address LIKE ?)"
            like_search = f"%{search}%"
            params.extend([like_search, like_search])

        if status_filter and status_filter.lower() != "all status":
            is_active = 1 if status_filter.lower() == "active" else 0
            query += " AND b.is_active = ?"
            params.append(is_active)

        query += " ORDER BY b.building_id"

        cursor.execute(query, params)
        buildings_list = [dict(row) for row in cursor.fetchall()]

    except Exception as error:
        flash(f"Error fetching buildings: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template("buildings/03_buildings.html", buildings=buildings_list, search=search, status_filter=status_filter)


@bp.route("/add_building", methods=["GET", "POST"])
@role_required("admin", "landlord")
def add_building():
    if request.method == "POST":
        building_name = request.form.get("building_name")
        address = request.form.get("address")
        total_floors = request.form.get("total_floors")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if session.get("role") == "landlord":
                owner_id = session.get("user_id")
            else:
                owner_id = request.form.get("owner_id") or None
            cursor.execute(
                """
                INSERT INTO buildings (building_name, address, total_floors, owner_id, is_active)
                VALUES (?, ?, ?, ?, 1)
            """,
                (building_name, address, total_floors, owner_id),
            )
            conn.commit()
            flash("Building added successfully!", "success")
            return redirect(url_for("buildings"))
        except Exception as error:
            flash(f"Error adding building: {error}", "danger")
        finally:
            cursor.close()
            conn.close()

    landlords = []
    if session.get("role") == "admin":
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, first_name, last_name FROM users WHERE role = 'landlord' AND is_active = 1 ORDER BY username"
            )
            landlords = cursor.fetchall()
        except Exception:
            landlords = []
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
    return render_template("buildings/03_add_building.html", landlords=landlords)


@bp.route("/edit_building/<int:building_id>", methods=["GET", "POST"])
def edit_building(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    building = None
    try:
        if request.method == "POST":
            building_name = request.form.get("building_name")
            address = request.form.get("address")
            total_floors = request.form.get("total_floors")
            owner_id = None
            if session.get("role") == "admin":
                owner_id = request.form.get("owner_id") or None

            if session.get("role") == "landlord" and building and building.get("owner_id") != session.get("user_id"):
                flash("Permission denied: you can only edit your own buildings.", "danger")
                return redirect(url_for("buildings"))

            if owner_id is not None:
                cursor.execute(
                    """
                    UPDATE buildings
                    SET building_name=?, address=?, total_floors=?, owner_id=?
                    WHERE building_id=?
                """,
                    (building_name, address, total_floors, owner_id, building_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE buildings
                    SET building_name=?, address=?, total_floors=?
                    WHERE building_id=?
                """,
                    (building_name, address, total_floors, building_id),
                )
            conn.commit()
            flash("Building updated successfully!", "success")
            return redirect(url_for("buildings"))

        cursor.execute("SELECT * FROM buildings WHERE building_id=?", (building_id,))
        building = cursor.fetchone()

        if not building:
            flash("Building not found.", "warning")
            return redirect(url_for("buildings"))

    except Exception as error:
        flash(f"Error editing building: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    landlords = []
    if session.get("role") == "admin":
        try:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute(
                "SELECT user_id, username, first_name, last_name FROM users WHERE role = 'landlord' AND is_active = 1 ORDER BY username"
            )
            landlords = cursor2.fetchall()
        except Exception:
            landlords = []
        finally:
            try:
                cursor2.close()
            except Exception:
                pass
            try:
                conn2.close()
            except Exception:
                pass
    return render_template("buildings/03_edit_building.html", building=building, landlords=landlords)
