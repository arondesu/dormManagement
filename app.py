from flask import Flask, current_app, render_template, request, redirect, flash, url_for, session, Response,jsonify
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import re
import smtplib
from email.message import EmailMessage
from datetime import datetime
from functools import wraps
import csv
from io import StringIO
import seed_data, db

db.init_db()
seed_data.seed_database()  # Ensure database is seeded on startup
load_dotenv()

######################################3




app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key_please_change")

# In app.py, add cache headers
@app.after_request
def add_header(response):
    response.cache_control.max_age = 300  # 5 minutes
    return response
#



# Role-based decorator to centralize access rules
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get('role')
            if not role or role not in allowed_roles:
                flash('Permission denied: insufficient role.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route("/delete_building/<int:building_id>", methods=["POST"])
def delete_building(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1️⃣ Check if building exists
        cursor.execute("SELECT * FROM buildings WHERE building_id = ?", (building_id,))
        building = cursor.fetchone()

        if not building:
            flash("Building not found.", "danger")
            return redirect(url_for("buildings"))

        # 2️⃣ Check if building has rooms
        cursor.execute("SELECT room_id FROM rooms WHERE building_id = ?", (building_id,))
        rooms = cursor.fetchall()

        if rooms:
            # Extract room IDs for next check
            room_ids = [r["room_id"] for r in rooms]

            # 3️⃣ Check if any room has assignments
            cursor.execute(
                f"""
                SELECT assignment_id FROM room_assignments
                WHERE room_id IN ({','.join('?' * len(room_ids))})
                """,
                room_ids
            )
            assignments = cursor.fetchall()

            if assignments:
                flash("Cannot delete building. One or more rooms still have occupants or assignments.", "warning")
                return redirect(url_for("buildings"))

        # 4️⃣ Safe to delete
        cursor.execute("DELETE FROM buildings WHERE building_id = ?", (building_id,))
        conn.commit()

        flash("Building deleted successfully!", "success")

    except Exception as e:
        print("Error deleting building:", e)
        flash("Error deleting building.", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("buildings"))

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, jsonify
)
from datetime import datetime

@app.route("/edit_assignment/<int:assignment_id>", methods=["GET", "POST"])
def edit_assignment(assignment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch assignment with room + building info
    cursor.execute("""
        SELECT ra.*, u.first_name, u.last_name,
               r.room_number, r.room_id, r.building_id,
               b.building_name
        FROM room_assignments ra
        LEFT JOIN users u ON ra.user_id = u.user_id
        LEFT JOIN rooms r ON ra.room_id = r.room_id
        LEFT JOIN buildings b ON r.building_id = b.building_id
        WHERE ra.assignment_id = ?
    """, (assignment_id,))
    assignment = cursor.fetchone()

    if not assignment:
        flash("Assignment not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("assignments"))

    # Fetch all buildings
    cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active = 1")
    buildings = cursor.fetchall()

    # Determine building for initial room list (include current assigned room even if occupied)
    selected_building = request.form.get("building_id") or assignment["building_id"]

    cursor.execute("""
        SELECT room_id, room_number, is_available
        FROM rooms
        WHERE building_id = ? OR room_id = ?
        ORDER BY room_number
    """, (selected_building, assignment["room_id"]))
    rooms = cursor.fetchall()

    statuses = ["active", "pending", "completed", "cancelled"]

    if request.method == "POST":
        # read form values; use hidden fallbacks for selects (because selects may be disabled in UI)
        raw_building = request.form.get("building_id") or request.form.get("building_id_hidden")
        raw_room_number = request.form.get("room_number") or request.form.get("room_number_hidden")
        end_date = request.form.get("end_date")
        monthly_rate = request.form.get("monthly_rate")
        status = request.form.get("status")

        # validation
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

        # find new_room_id from room_number/building
        cursor.execute(
            "SELECT room_id FROM rooms WHERE room_number = ? AND building_id = ?",
            (raw_room_number, new_building_id)
        )
        new_room_row = cursor.fetchone()
        if not new_room_row:
            flash("Selected room not found.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for("edit_assignment", assignment_id=assignment_id))

        new_room_id = new_room_row["room_id"]
        old_room_id = assignment["room_id"]

        # Validate dates (optional)
        if end_date:
            try:
                sd = datetime.strptime(request.form.get("start_date") or assignment.get("start_date"), "%Y-%m-%d")
                ed = datetime.strptime(end_date, "%Y-%m-%d")
                if ed <= sd:
                    flash("End date must be later than start date.", "warning")
                    cursor.close()
                    conn.close()
                    return redirect(url_for("edit_assignment", assignment_id=assignment_id))
            except Exception:
                # ignore if parsing fails (could be None or different format); you may tighten this
                pass

        # Update assignment record
        cursor.execute("""
            UPDATE room_assignments
            SET room_id = ?, end_date = ?, monthly_rate = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE assignment_id = ?
        """, (new_room_id, end_date or None, monthly_rate or None, status, assignment_id))

        # ROOM AVAILABILITY logic:
        # - If status == completed => assigned room should be free (is_available = 1)
        # - Else assigned room should be occupied (is_available = 0)
        if status == "completed":
            cursor.execute("UPDATE rooms SET is_available = 1 WHERE room_id = ?", (new_room_id,))
        else:
            cursor.execute("UPDATE rooms SET is_available = 0 WHERE room_id = ?", (new_room_id,))

        # If the user changed to a different room, free the old room
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
        statuses=statuses
    )





@app.route("/get_rooms/<int:building_id>")
def get_rooms(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT room_number FROM rooms WHERE building_id = ? AND is_available = 1", 
        (building_id,)
    )
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"rooms": [r["room_number"] for r in rooms]}




























# -----------------------
# HOME PAGE / DASHBOARD
# -----------------------
@app.route("/")
def home():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    role = session.get('role')

    conn = get_db_connection()
    cursor = conn.cursor()

    # For admin: show all buildings and rooms
    if role == "admin":
        cursor.execute("SELECT COUNT(*) AS total_rooms FROM rooms")
        total_rooms = cursor.fetchone()["total_rooms"]

        cursor.execute("SELECT COUNT(*) AS occupied FROM rooms WHERE is_available = 0")
        occupied = cursor.fetchone()["occupied"]

        cursor.execute("SELECT COUNT(*) AS available FROM rooms WHERE is_available = 1")
        available = cursor.fetchone()["available"]

        cursor.execute("SELECT COUNT(*) AS pending FROM room_assignments WHERE status='pending'")
        pending = cursor.fetchone()["pending"]

    # For landlord: show only their buildings and rooms
    elif role == "landlord":
        # Buildings owned
        cursor.execute("SELECT COUNT(*) AS total_buildings FROM buildings WHERE owner_id = ?", (user_id,))
        total_buildings = cursor.fetchone()["total_buildings"]

        # Rooms in owned buildings
        cursor.execute("""
            SELECT COUNT(*) AS total_rooms,
                   SUM(CASE WHEN is_available = 0 THEN 1 ELSE 0 END) AS occupied,
                   SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) AS available
            FROM rooms
            WHERE building_id IN (SELECT building_id FROM buildings WHERE owner_id = ?)
        """, (user_id,))
        rooms_stats = cursor.fetchone()
        total_rooms = rooms_stats["total_rooms"] or 0
        occupied = rooms_stats["occupied"] or 0
        available = rooms_stats["available"] or 0

        # Pending assignments in their buildings
        cursor.execute("""
            SELECT COUNT(*) AS pending
            FROM room_assignments ra
            JOIN rooms r ON ra.room_id = r.room_id
            WHERE r.building_id IN (SELECT building_id FROM buildings WHERE owner_id = ?)
              AND ra.status = 'pending'
        """, (user_id,))
        pending = cursor.fetchone()["pending"]

    else:
        # For students, you can leave stats empty or only their info
        total_rooms = occupied = available = pending = None

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        role=role,
        total_rooms=total_rooms,
        occupied=occupied,
        available=available,
        pending=pending
    )


@app.route("/admin_assign_room", methods=["GET", "POST"])
def admin_assign_room():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch buildings for admin (all active), landlord (only their buildings)
    if session.get("role") == "admin":
        cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active=1")
    else:
        cursor.execute(
            "SELECT building_id, building_name FROM buildings WHERE is_active=1 AND owner_id=?",
            (session.get("user_id"),)
        )
    buildings = cursor.fetchall()

    # Fetch available rooms based on role
    if session.get("role") == "admin":
        cursor.execute("""
            SELECT r.room_id, r.room_number, b.building_name
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.is_available=1
        """)
    else:
        cursor.execute("""
            SELECT r.room_id, r.room_number, b.building_name
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.is_available=1 AND b.owner_id=?
        """, (session.get("user_id"),))
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

        # Validate dates
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                ed = datetime.strptime(end_date, "%Y-%m-%d")
                if ed <= sd:
                    flash("End date must be later than start date.", "danger")
                    return redirect(request.path)
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(request.path)

        # Check if user exists
        cursor.execute("""
            SELECT user_id FROM users
            WHERE username=? OR email=?
        """, (username_or_email, username_or_email))
        user = cursor.fetchone()
        if not user:
            flash("User not found. Please enter a valid username or email.", "danger")
            return redirect(request.path)
        user_id = user["user_id"]

        # Check room availability and ownership
        if session.get("role") == "admin":
            cursor.execute("SELECT is_available FROM rooms WHERE room_id=?", (room_id,))
        else:
            cursor.execute("""
                SELECT r.is_available
                FROM rooms r
                JOIN buildings b ON r.building_id = b.building_id
                WHERE r.room_id=? AND b.owner_id=?
            """, (room_id, session.get("user_id")))
        room = cursor.fetchone()
        if not room:
            flash("Room not found or not allowed.", "danger")
            return redirect(request.path)
        if room["is_available"] == 0:
            flash("Room is not available.", "danger")
            return redirect(request.path)

        # Assign the room
        cursor.execute("""
            INSERT INTO room_assignments
            (user_id, room_id, start_date, end_date, monthly_rate, status, assigned_by)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """, (user_id, room_id, start_date, end_date, monthly_rate, assigned_by))

        cursor.execute("UPDATE rooms SET is_available=0 WHERE room_id=?", (room_id,))
        conn.commit()

        flash("Room successfully assigned!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("users"))

    cursor.close()
    conn.close()
    return render_template("06_assign_room.html", buildings=buildings, rooms=rooms,
                           current_user={'user_id': session.get('user_id')})

# API route: landlord-specific available rooms by building & floor
@app.route("/landlord_rooms/<int:building_id>/<int:floor_number>")
def landlord_rooms(building_id, floor_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    if session.get("role") == "admin":
        cursor.execute("""
            SELECT room_id, room_number
            FROM rooms
            WHERE building_id=? AND floor_number=? AND is_available=1
        """, (building_id, floor_number))
    else:
        cursor.execute("""
            SELECT r.room_id, r.room_number
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            WHERE r.building_id=? AND r.floor_number=? AND r.is_available=1 AND b.owner_id=?
        """, (building_id, floor_number, session.get("user_id")))

    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([dict(r) for r in rooms])


@app.route("/edit_room/<int:room_id>", methods=["GET", "POST"])
def edit_room(room_id):
    if session.get('role') == 'student':
        flash("You are not allowed to perform this action.", "danger")
        return redirect(url_for('rooms'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch room + building info
    cursor.execute("""
        SELECT r.*, b.building_name, b.total_floors, t.type_name
        FROM rooms r
        LEFT JOIN buildings b ON r.building_id = b.building_id
        LEFT JOIN room_types t ON r.type_id = t.type_id
        WHERE r.room_id = ?
    """, (room_id,))
    room = cursor.fetchone()

    # Fetch all active room types for dropdown
    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if not room:
        flash("Room not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    # Get all floors for that building (1 to total_floors)
    total_floors = room["total_floors"]
    floors = list(range(1, total_floors + 1))

    # Fetch active room types
    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if request.method == "POST":
        room_number = request.form.get("room_number", "").strip()
        floor_number = request.form.get("floor_number", "").strip()
        type_id = request.form.get("type_id")
        is_available = request.form.get("is_available", "1")

        # Basic validation
        if not room_number or not floor_number:
            flash("Room number and floor number are required.", "warning")
            return redirect(url_for("edit_room", room_id=room_id))

        # Update room
        cursor.execute("""
            UPDATE rooms
            SET room_number = ?, floor_number = ?, type_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE room_id = ?
        """, (room_number, floor_number, type_id, room_id))

        conn.commit()
        flash("Room updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.close()
    conn.close()

    return render_template("05_edit_rooms.html", room=room, room_types=room_types, floors=floors)

@app.route("/delete_room/<int:room_id>", methods=["POST"])
def delete_room(room_id):
    if session.get("role") not in ["admin", "landlord"]:
        flash("You do not have permission to delete rooms.", "danger")
        return redirect(url_for("rooms"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if room exists
    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    room = cursor.fetchone()
    if not room:
        flash("Room not found.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    # Check if room is available AND has no active assignments
    cursor.execute("""
        SELECT COUNT(*) as active_count
        FROM room_assignments
        WHERE room_id = ? AND status = 'active'
    """, (room_id,))
    active_count = cursor.fetchone()["active_count"]

    if not room["is_available"] or active_count > 0:
        flash("Cannot delete room. It is either occupied or assigned to a tenant.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    # Safe to delete
    cursor.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Room deleted successfully.", "success")
    return redirect(url_for("rooms"))

@app.route("/add_room", methods=["GET", "POST"])
def add_room():
    if session.get("role") not in ["admin", "landlord"]:
        flash("You do not have permission to add rooms.", "danger")
        return redirect(url_for("rooms"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Admin can see all active buildings
    if session.get("role") == "admin":
        cursor.execute("SELECT building_id, building_name, total_floors FROM buildings WHERE is_active = 1")
    else:
        # Landlord can only see their own buildings
        cursor.execute("""
            SELECT building_id, building_name, total_floors 
            FROM buildings 
            WHERE is_active = 1 AND owner_id = ?
        """, (session.get("user_id"),))
    
    buildings = cursor.fetchall()

    # Fetch active room types
    cursor.execute("SELECT type_id, type_name FROM room_types WHERE is_active = 1")
    room_types = cursor.fetchall()

    if request.method == "POST":
        building_id = request.form.get("building_id")
        floor_number = request.form.get("floor_number")
        room_number = request.form.get("room_number").strip()
        type_id = request.form.get("type_id")

        # Validation
        if not building_id or not floor_number or not room_number or not type_id:
            flash("All fields are required.", "warning")
            return redirect(url_for("add_room"))

        # Ensure landlords only select their own buildings
        if session.get("role") == "landlord":
            cursor.execute("SELECT COUNT(*) as count FROM buildings WHERE building_id = ? AND owner_id = ?", 
                           (building_id, session.get("user_id")))
            allowed = cursor.fetchone()["count"]
            if allowed == 0:
                flash("You cannot add a room to a building you do not own.", "danger")
                return redirect(url_for("add_room"))

        # Prevent duplicate room number in the same building
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM rooms
            WHERE building_id = ? AND room_number = ?
        """, (building_id, room_number))
        exists = cursor.fetchone()["count"]

        if exists > 0:
            flash(f"Room number '{room_number}' already exists in the selected building.", "warning")
            return redirect(url_for("add_room"))

        # Insert the new room
        cursor.execute("""
            INSERT INTO rooms (building_id, room_number, floor_number, type_id, is_available, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (building_id, room_number, floor_number, type_id))
        conn.commit()

        flash("Room added successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("rooms"))

    cursor.close()
    conn.close()
    return render_template("05_add_room.html", buildings=buildings, room_types=room_types)

@app.route("/building_floors/<int:building_id>")
def building_floors(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total_floors FROM buildings WHERE building_id = ?", (building_id,))
    building = cursor.fetchone()
    cursor.close()
    conn.close()

    if building:
        # Return a list of floor numbers
        return jsonify([i for i in range(1, building["total_floors"] + 1)])
    return jsonify([])

# ===========================
# 1. USERS MANAGEMENT
# ===========================
@app.route("/users")
def users():
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    users = []
    
    try:
        query = """
            SELECT user_id, username, first_name, last_name, role, 
                   email, phone, is_active 
            FROM users
            WHERE 1=1
        """
        params = []

        # Search filter
        if search:
            query += " AND (first_name LIKE ? OR last_name LIKE ? OR username LIKE ? OR email LIKE ?)"
            like_search = f"%{search}%"
            params.extend([like_search, like_search, like_search, like_search])
        
        # Role filter
        if role_filter and role_filter.lower() != "all roles":
            query += " AND role = ?"
            params.append(role_filter.lower())

        query += " ORDER BY user_id"

        cursor.execute(query, params)
        users = [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        flash(f"Error fetching users: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return render_template("02_users.html", users=users, search=search, role_filter=role_filter)

@app.route("/add_user", methods=["GET", "POST"])
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
        # Basic validation
        if not username or not email or not password:
            flash("Username, email and password are required.", "danger")
            return redirect(request.path)

        # email format
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, email):
            flash("Invalid email format.", "danger")
            return redirect(request.path)

        # password strength: min 8 chars, at least one letter and one digit
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            flash("Password must be at least 8 characters long and include letters and numbers.", "danger")
            return redirect(request.path)

        # Hash the password before storing
        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Basic uniqueness checks
            cursor.execute("SELECT COUNT(*) FROM users WHERE username=?", (username,))
            if cursor.fetchone()[0] > 0:
                flash("Username already taken.", "danger")
                return redirect(request.path)
            cursor.execute("SELECT COUNT(*) FROM users WHERE email=?", (email,))
            if cursor.fetchone()[0] > 0:
                flash("Email already registered.", "danger")
                return redirect(request.path)
                return redirect(request.path)            
            cursor.execute("""
                INSERT INTO users 
                (username, password_hash, role, first_name, last_name, email, phone, birth_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (username, password_hash, role, first_name, last_name, email, phone, birth_date))
            conn.commit()
            flash("User added successfully!", "success")
            # try to send confirmation email (if configured)
            try:
                send_confirmation_email(email, username)
                flash("Confirmation email sent.", "info")
            except Exception:
                flash("Confirmation email not sent (SMTP not configured).", "warning")
            # If an admin (logged-in) created the user, go to users list; otherwise go to login
            if session.get('user_id'):
                return redirect(url_for("users"))
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error adding user: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    # Default public registration view
    return render_template("register.html")


# Role-based decorator to centralize access rules
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get('role')
            if not role or role not in allowed_roles:
                flash('Permission denied: insufficient role.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/admin/add_user', methods=['GET', 'POST'])
@role_required('admin')
def admin_add_user():
    # allow only admin users
    if session.get('role') != 'admin':
        flash('Admin access required to add users.', 'danger')
        return redirect(url_for('users'))

    if request.method == 'POST':
        # reuse mostly same logic as add_user but redirect to users list
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        role = request.form.get('role', 'student')
        birth_date = request.form.get('birth_date')

        # Validation (simple)
        if not username or not email or not password:
            flash('Username, email and password are required.', 'danger')
            return redirect(url_for('admin_add_user'))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE username=?", (username,))
            if cursor.fetchone()[0] > 0:
                flash('Username already taken.', 'danger')
                return redirect(url_for('admin_add_user'))
            cursor.execute("SELECT COUNT(*) FROM users WHERE email=?", (email,))
            if cursor.fetchone()[0] > 0:
                flash('Email already registered.', 'danger')
                return redirect(url_for('admin_add_user'))

            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users 
                (username, password_hash, role, first_name, last_name, email, phone, birth_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (username, password_hash, role, first_name, last_name, email, phone, birth_date))
            conn.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            flash(f'Error adding user: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()

    return render_template('02_add_user.html')


def send_confirmation_email(to_email, username):
    # Reads SMTP settings from environment and sends a simple confirmation email.
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587')) if os.getenv('SMTP_PORT') else None
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if not smtp_host or not smtp_port or not smtp_user or not smtp_pass:
        raise RuntimeError('SMTP not configured')

    msg = EmailMessage()
    msg['Subject'] = 'Welcome to Dorm Management'
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg.set_content(f'Hi {username},\n\nThank you for registering.\n\nRegards,\nDorm Management')

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)


# Role-based decorator to centralize access rules
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = session.get('role')
            if not role or role not in allowed_roles:
                flash('Permission denied: insufficient role.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    conn = get_db_connection()  # make sure this sets conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = None
    try:
        if request.method == "POST":
            # read form inputs
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            password = request.form.get("password", "")  # empty string if not provided
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            birth_date = request.form.get("birth_date", "").strip()
            role = request.form.get("role", "student").strip()
            is_active = int(request.form.get("is_active", "1"))


            # basic validation
            if not first_name or not last_name:
                flash("First name and last name are required.", "warning")
                return redirect(url_for("edit_user", user_id=user_id))

            # if password provided, optional validation (example: min 8 chars)
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
                    (first_name, last_name, password_hash, email, phone, birth_date or None,
                    role, is_active, user_id)
                )

            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET first_name = ?, last_name = ?, email = ?, phone = ?, 
                        birth_date = ?, role = ?, is_active = ?
                    WHERE user_id = ?
                    """,
                    (first_name, last_name, email, phone, birth_date or None,
                    role, is_active, user_id)
                )


            conn.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for("users"))

        # GET: fetch user to show in form
        cursor.execute(
            """
            SELECT user_id, username, first_name, last_name, role, email, phone, birth_date, is_active
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("users"))

        # If birth_date is a datetime string in DB, convert to YYYY-MM-DD for the input
        # This only runs if the field is not None/empty; adapt to your DB format
        if user.get("birth_date"):
            try:
                # try parsing common formats, adjust if your DB has a different format
                bd = user["birth_date"]
                if isinstance(bd, str):
                    # attempt to parse ISO-like
                    parsed = None
                    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
                        try:
                            parsed = datetime.strptime(bd, fmt)
                            break
                        except Exception:
                            continue
                    if parsed:
                        # attach an iso date string for template use
                        user = dict(user)  # convert row to mutable dict if needed
                        user["birth_date"] = parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

    except Exception as e:
        # log error server-side in production
        #flash(f"Error editing user: {e}", "danger")
        pass
    finally:
        cursor.close()
        conn.close()

    return render_template("02_edit_user.html", user=user)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
@role_required('admin')
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check for child records that reference this user
        cursor.execute("SELECT COUNT(*) FROM room_assignments WHERE user_id=?", (user_id,))
        assignment_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM payments WHERE user_id=?", (user_id,))
        payment_count = cursor.fetchone()[0]

        if assignment_count > 0 or payment_count > 0:
            # Instead of failing with a FK constraint, perform a soft-delete (deactivate)
            cursor.execute("UPDATE users SET is_active = 0 WHERE user_id=?", (user_id,))
            conn.commit()
            flash("User cannot be deleted because related records exist. User has been deactivated instead.", "warning")
        else:
            cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            flash("User deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("users"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        if not identifier or not password:
            flash('Please enter username and password.', 'warning')
            return render_template('logIn.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id, username, password_hash, role, is_active FROM users WHERE username=? OR email=? LIMIT 1",
                (identifier, identifier)
            )
            row = cursor.fetchone()
            
            if not row:
                flash('Invalid username or password', 'danger')
                return render_template('logIn.html')
            
            user = dict(row)
            
            if not user.get('is_active', 1):
                flash('Account is deactivated. Contact admin.', 'danger')
                return render_template('logIn.html')
            
            if not user.get('password_hash') or not check_password_hash(user['password_hash'], password):
                flash('Invalid username or password', 'danger')
                return render_template('logIn.html')
            
            # SET SESSION
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user.get('role')
            
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f'Error during login: {e}', 'danger')
            print(f"Login error: {e}")  # DEBUG
        finally:
            cursor.close()
            conn.close()
    
    return render_template('logIn.html')

@app.route('/register', methods=['GET'])
def register():
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# ===========================
# 2. BUILDINGS MANAGEMENT
# ===========================


@app.route("/buildings")
def buildings():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()  # Active/Inactive/All

    conn = get_db_connection()
    cursor = conn.cursor()
    buildings = []

    try:
        # Base query
        query = """
            SELECT b.building_id, b.building_name, b.address, b.total_floors,
                   b.is_active, b.owner_id, u.username AS owner_username, b.created_at
            FROM buildings b
            LEFT JOIN users u ON b.owner_id = u.user_id
            WHERE 1=1
        """
        params = []

        # Landlord role: only their buildings
        if session.get('role') == 'landlord':
            query += " AND b.owner_id = ?"
            params.append(session.get('user_id'))
        # Student role: only active buildings
        elif session.get('role') == 'student':
            query += " AND b.is_active = 1"

        # Search filter
        if search:
            query += " AND (b.building_name LIKE ? OR b.address LIKE ?)"
            like_search = f"%{search}%"
            params.extend([like_search, like_search])

        # Status filter
        if status_filter and status_filter.lower() != "all status":
            is_active = 1 if status_filter.lower() == "active" else 0
            query += " AND b.is_active = ?"
            params.append(is_active)

        query += " ORDER BY b.building_id"

        cursor.execute(query, params)
        buildings = [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        flash(f"Error fetching buildings: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template("03_buildings.html", buildings=buildings, search=search, status_filter=status_filter)

@app.route("/add_building", methods=["GET", "POST"])
@role_required('admin','landlord')
def add_building():
    if request.method == "POST":
        building_name = request.form.get("building_name")
        address = request.form.get("address")
        total_floors = request.form.get("total_floors")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # If user is landlord, automatically assign them as owner. Admin can select an owner
            if session.get('role') == 'landlord':
                owner_id = session.get('user_id')
            else:
                owner_id = request.form.get('owner_id') or None
            cursor.execute("""
                INSERT INTO buildings (building_name, address, total_floors, owner_id, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (building_name, address, total_floors, owner_id))
            conn.commit()
            flash("Building added successfully!", "success")
            return redirect(url_for("buildings"))
        except Exception as e:
            flash(f"Error adding building: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    # For admin users provide a list of landlord users to choose as owner
    landlords = []
    if session.get('role') == 'admin':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, first_name, last_name FROM users WHERE role = 'landlord' AND is_active = 1 ORDER BY username")
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
    return render_template("03_add_building.html", landlords=landlords)

@app.route("/edit_building/<int:building_id>", methods=["GET", "POST"])
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
            if session.get('role') == 'admin':
                owner_id = request.form.get('owner_id') or None
            # Security: landlord can only edit their own building
            if session.get('role') == 'landlord' and building and building.get('owner_id') != session.get('user_id'):
                flash('Permission denied: you can only edit your own buildings.', 'danger')
                return redirect(url_for('buildings'))

            if owner_id is not None:
                cursor.execute("""
                    UPDATE buildings 
                    SET building_name=?, address=?, total_floors=?, owner_id=?
                    WHERE building_id=?
                """, (building_name, address, total_floors, owner_id, building_id))
            else:
                cursor.execute("""
                    UPDATE buildings 
                    SET building_name=?, address=?, total_floors=?
                    WHERE building_id=?
                """, (building_name, address, total_floors, building_id))
            conn.commit()
            flash("Building updated successfully!", "success")
            return redirect(url_for("buildings"))

        cursor.execute("SELECT * FROM buildings WHERE building_id=?", (building_id,))
        building = cursor.fetchone()

        if not building:
            flash("Building not found.", "warning")
            return redirect(url_for("buildings"))

    except Exception as e:
        flash(f"Error editing building: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    # For admin users include the landlords select
    landlords = []
    if session.get('role') == 'admin':
        try:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor(dictionary=True)
            cursor2.execute("SELECT user_id, username, first_name, last_name FROM users WHERE role = 'landlord' AND is_active = 1 ORDER BY username")
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
    return render_template("03_edit_building.html", building=building, landlords=landlords)

# ===========================
# 3. ROOM TYPES MANAGEMENT
# ===========================

@app.route("/room_types")
def room_types():
    conn = get_db_connection()
    cursor = conn.cursor()
    types = []
    try:
        cursor.execute("""
            SELECT type_id, type_name, base_rate, capacity, description, is_active
            FROM room_types 
            ORDER BY type_id
        """)
        types = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching room types: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("04_room_types.html", room_types=types)

# ===========================
# 4. ROOMS MANAGEMENT
# ===========================
from flask import request

@app.route("/rooms")
def rooms():
    search = request.args.get("search", "").strip()
    building_filter = request.args.get("building", "").strip()
    status_filter = request.args.get("status", "").strip()  # Available / Occupied / All

    conn = get_db_connection()
    cursor = conn.cursor()
    rooms = []

    try:
        # Base query
        query = """
            SELECT r.room_id, r.room_number, r.floor_number, b.building_name,
                   rt.type_name, r.is_available, b.owner_id
            FROM rooms r
            LEFT JOIN buildings b ON r.building_id = b.building_id
            LEFT JOIN room_types rt ON r.type_id = rt.type_id
            WHERE 1=1
        """
        params = []

        # Role-based filtering
        if session.get('role') == 'landlord':
            query += " AND b.owner_id = ?"
            params.append(session.get('user_id'))
        elif session.get('role') == 'student':
            query += " AND r.is_available = 1"

        # Search by room number
        if search:
            query += " AND r.room_number LIKE ?"
            params.append(f"%{search}%")

        # Filter by building
        if building_filter and building_filter.lower() != "all buildings":
            query += " AND b.building_name = ?"
            params.append(building_filter)

        # Filter by status
        if status_filter and status_filter.lower() != "all status":
            if status_filter.lower() == "available":
                query += " AND r.is_available = 1"
            else:  # Occupied
                query += " AND r.is_available = 0"

        query += " ORDER BY r.room_id"

        cursor.execute(query, params)
        rooms = [dict(row) for row in cursor.fetchall()]

        # For building select dropdown
        cursor.execute("SELECT building_name FROM buildings ORDER BY building_name")
        buildings_list = [row["building_name"] for row in cursor.fetchall()]

    except Exception as e:
        flash(f"Error fetching rooms: {e}", "danger")
        buildings_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template("05_rooms.html", rooms=rooms, search=search,
                           building_filter=building_filter, status_filter=status_filter,
                           buildings_list=buildings_list)

# ===========================
# 5. ROOM ASSIGNMENTS MANAGEMENT
# ===========================

@app.route("/assignments")
def assignments():
    conn = get_db_connection()
    cursor = conn.cursor()
    assignments = []
    try:
        # role aware assignments
        if session.get('role') == 'landlord':
            cursor.execute("""
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date, 
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY ra.assignment_id
            """, (session.get('user_id'),))
        elif session.get('role') == 'student':
            cursor.execute("""
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date, 
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE ra.user_id = ?
                ORDER BY ra.assignment_id
            """, (session.get('user_id'),))
        else:
            cursor.execute("""
                SELECT ra.assignment_id, u.username, u.first_name, u.last_name,
                       r.room_number, b.building_name, ra.start_date, ra.end_date, 
                       ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                ORDER BY ra.assignment_id
            """)
        assignments = cursor.fetchall()
        converted = []
        for row in assignments:
            r = dict(row)            # convert Row object to dict
            r["monthly_rate"] = float(r["monthly_rate"])
            converted.append(r)
    except Exception as e:
        flash(f"Error fetching assignments: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("06_assignments.html", assignments=converted)

# ===========================
# 6. PAYMENTS MANAGEMENT
# ===========================

@app.route("/payments")
def payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    payments = []
    students = []
    buildings = []
    stats = {}
    
    # Get filter parameters
    student_filter = request.args.get('student_filter')
    building_filter = request.args.get('building_filter')
    method_filter = request.args.get('method_filter')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    try:
        # Base query with all needed joins
        base_query = """
            SELECT p.payment_id, u.username, u.first_name, u.last_name,
                   p.amount, p.payment_method, p.payment_date, 
                   p.receipt_number, p.payment_period_start, p.payment_period_end,
                   p.notes, r.room_number, b.building_name, ra.monthly_rate
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
            LEFT JOIN rooms r ON ra.room_id = r.room_id
            LEFT JOIN buildings b ON r.building_id = b.building_id
        """
        
        where_clauses = []
        params = []
        
        # Role-based filtering
        if session.get('role') == 'landlord':
            where_clauses.append("b.owner_id = ?")
            params.append(session.get('user_id'))
        elif session.get('role') == 'student':
            where_clauses.append("p.user_id = ?")
            params.append(session.get('user_id'))
        
        # Additional filters
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
        
        # Construct final query
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " ORDER BY p.payment_date DESC, p.payment_id DESC"
        
        cursor.execute(base_query, params)
        payments = cursor.fetchall()
        
        # Get statistics based on role
        if session.get('role') == 'admin':
            # Total collected
            cursor.execute("SELECT SUM(amount) as total FROM payments")
            row = cursor.fetchone()
            stats['total_collected'] = row['total'] if row['total'] else 0
            
            # This month
            cursor.execute("""
                SELECT SUM(amount) as total FROM payments 
                WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')
            """)
            row = cursor.fetchone()
            stats['month_collected'] = row['total'] if row['total'] else 0
            
            # Payment count
            cursor.execute("SELECT COUNT(*) as count FROM payments")
            row = cursor.fetchone()
            stats['payment_count'] = row['count']
            
            # Average payment
            cursor.execute("SELECT AVG(amount) as avg FROM payments")
            row = cursor.fetchone()
            stats['avg_payment'] = row['avg'] if row['avg'] else 0
            
        elif session.get('role') == 'landlord':
            # Total collected for landlord's buildings
            cursor.execute("""
                SELECT SUM(p.amount) as total FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
            """, (session.get('user_id'),))
            row = cursor.fetchone()
            stats['total_collected'] = row['total'] if row['total'] else 0
            
            # This month
            cursor.execute("""
                SELECT SUM(p.amount) as total FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ? AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            """, (session.get('user_id'),))
            row = cursor.fetchone()
            stats['month_collected'] = row['total'] if row['total'] else 0
            
            # Payment count
            cursor.execute("""
                SELECT COUNT(*) as count FROM payments p
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
            """, (session.get('user_id'),))
            row = cursor.fetchone()
            stats['payment_count'] = row['count']
            
        else:  # student
            # Total paid
            cursor.execute("SELECT SUM(amount) as total FROM payments WHERE user_id = ?", (session.get('user_id'),))
            row = cursor.fetchone()
            stats['total_paid'] = row['total'] if row['total'] else 0
            
            # Current balance (monthly_rate minus paid)
            cursor.execute("""
                SELECT SUM(ra.monthly_rate) as expected FROM room_assignments ra
                WHERE ra.user_id = ? AND ra.status = 'active'
            """, (session.get('user_id'),))
            row = cursor.fetchone()
            expected = row['expected'] if row['expected'] else 0
            stats['balance'] = expected - stats['total_paid']
            
            # Next due date
            cursor.execute("""
                SELECT MIN(end_date) as next_due FROM room_assignments
                WHERE user_id = ? AND status = 'active' AND end_date > date('now')
            """, (session.get('user_id'),))
            row = cursor.fetchone()
            stats['next_due'] = row['next_due'] if row and row['next_due'] else 'N/A'
        
        # Get students list for filter (admin/landlord)
        if session.get('role') in ['admin', 'landlord']:
            if session.get('role') == 'admin':
                cursor.execute("""
                    SELECT DISTINCT u.user_id, u.first_name, u.last_name 
                    FROM users u
                    WHERE u.role = 'student' AND u.is_active = 1
                    ORDER BY u.first_name, u.last_name
                """)
            else:
                cursor.execute("""
                    SELECT DISTINCT u.user_id, u.first_name, u.last_name 
                    FROM users u
                    JOIN room_assignments ra ON u.user_id = ra.user_id
                    JOIN rooms r ON ra.room_id = r.room_id
                    JOIN buildings b ON r.building_id = b.building_id
                    WHERE b.owner_id = ? AND u.is_active = 1
                    ORDER BY u.first_name, u.last_name
                """, (session.get('user_id'),))
            students = cursor.fetchall()
        
        # Get buildings list for filter (admin only)
        if session.get('role') == 'admin':
            cursor.execute("SELECT building_id, building_name FROM buildings WHERE is_active = 1 ORDER BY building_name")
            buildings = cursor.fetchall()
            
    except Exception as e:
        flash(f"Error fetching payments: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return render_template("07_payments.html", 
                         payments=payments, 
                         students=students, 
                         buildings=buildings,
                         stats=stats,
                         today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/payment", methods=["GET", "POST"])
@app.route("/payment/<int:payment_id>", methods=["GET", "POST"])
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
            cursor.execute("""
                INSERT INTO payments (user_id, amount, payment_method, payment_date, receipt_number)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, amount, payment_method, payment_date, receipt_number))
            conn.commit()
            flash("Payment recorded successfully!", "success")
            return redirect(url_for("payments"))
        except Exception as e:
            flash(f"Error recording payment: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get('role') == 'landlord':
            cursor.execute("""
                SELECT DISTINCT u.user_id, u.username, u.role, u.first_name, u.last_name
                FROM users u
                JOIN room_assignments ra ON u.user_id = ra.user_id
                JOIN rooms r ON ra.room_id = r.room_id
                JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ? AND u.is_active = 1
                ORDER BY u.first_name
            """, (session.get('user_id'),))
            users = cursor.fetchall()
        elif session.get('role') == 'student':
            cursor.execute("SELECT user_id, username, role, first_name, last_name FROM users WHERE user_id = ? AND is_active = 1", (session.get('user_id'),))
            users = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY first_name")
            users = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching users: {e}", "danger")
        users = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template("07_payment.html", users=users)

@app.route("/record_payment", methods=["POST"])
@role_required('admin', 'landlord')
def record_payment():
    user_id = request.form.get("user_id")
    assignment_id = request.form.get("assignment_id") or None
    amount = request.form.get("amount")
    payment_method = request.form.get("payment_method")
    payment_date = request.form.get("payment_date")
    receipt_number = request.form.get("receipt_number")
    payment_period_start = request.form.get("payment_period_start") or None
    payment_period_end = request.form.get("payment_period_end") or None
    notes = request.form.get("notes") or None
    
    # Validate inputs
    if not user_id or not amount or not payment_method or not payment_date:
        flash("Please fill in all required fields.", "warning")
        return redirect(url_for("payments"))
    
    # Auto-generate receipt number if not provided
    if not receipt_number:
        receipt_number = f"PMT-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp() * 1000) % 10000:04d}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Insert payment
        cursor.execute("""
            INSERT INTO payments (
                user_id, assignment_id, amount, payment_method, payment_date,
                payment_period_start, payment_period_end, receipt_number,
                recorded_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, assignment_id, amount, payment_method, payment_date,
              payment_period_start, payment_period_end, receipt_number,
              session.get('user_id'), notes))
        
        conn.commit()
        flash(f"Payment recorded successfully! Receipt: {receipt_number}", "success")
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            flash("Receipt number already exists. Please use a different one.", "danger")
        else:
            flash(f"Error recording payment: {e}", "danger")
    except Exception as e:
        flash(f"Error recording payment: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for("payments"))

@app.route("/api/assignments/<int:user_id>")
@role_required('admin', 'landlord')
def get_user_assignments(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get active assignments for the user
        cursor.execute("""
            SELECT ra.assignment_id, ra.monthly_rate, r.room_number, b.building_name
            FROM room_assignments ra
            LEFT JOIN rooms r ON ra.room_id = r.room_id
            LEFT JOIN buildings b ON r.building_id = b.building_id
            WHERE ra.user_id = ? AND ra.status = 'active'
            ORDER BY ra.start_date DESC
        """, (user_id,))
        
        assignments = cursor.fetchall()
        
        return jsonify({
            'assignments': [dict(a) for a in assignments]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/payment/<int:payment_id>/view")
def view_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
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
        """, (payment_id,))
        
        payment = cursor.fetchone()
        
        if not payment:
            flash("Payment not found.", "warning")
            return redirect(url_for("payments"))
        
        # Check permissions
        if session.get('role') == 'student' and payment['user_id'] != session.get('user_id'):
            flash("You don't have permission to view this payment.", "danger")
            return redirect(url_for("payments"))
        
        return render_template("view_payment.html", payment=payment)
        
    except Exception as e:
        flash(f"Error fetching payment: {e}", "danger")
        return redirect(url_for("payments"))
    finally:
        cursor.close()
        conn.close()

@app.route("/payment/<int:payment_id>/edit", methods=["GET", "POST"])
@role_required('admin')
def edit_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        amount = request.form.get("amount")
        payment_method = request.form.get("payment_method")
        payment_date = request.form.get("payment_date")
        notes = request.form.get("notes")
        
        try:
            cursor.execute("""
                UPDATE payments 
                SET amount = ?, payment_method = ?, payment_date = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = ?
            """, (amount, payment_method, payment_date, notes, payment_id))
            
            conn.commit()
            flash("Payment updated successfully!", "success")
            return redirect(url_for("payments"))
            
        except Exception as e:
            flash(f"Error updating payment: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    
    try:
        cursor.execute("""
            SELECT p.*, u.first_name, u.last_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.payment_id = ?
        """, (payment_id,))
        
        payment = cursor.fetchone()
        
        if not payment:
            flash("Payment not found.", "warning")
            return redirect(url_for("payments"))
        
        return render_template("edit_payment.html", payment=payment)
        
    except Exception as e:
        flash(f"Error fetching payment: {e}", "danger")
        return redirect(url_for("payments"))
    finally:
        cursor.close()
        conn.close()

@app.route("/delete_payment/<int:payment_id>", methods=["POST"])
@role_required('admin')
def delete_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM payments WHERE payment_id = ?", (payment_id,))
        conn.commit()
        flash("Payment deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting payment: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for("payments"))

# ===========================
# 7. REPORTS
# ===========================

@app.route("/reports")
def reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    reports = []
    try:
        cursor.execute("""
            SELECT report_id, report_type, report_title, generated_on, u.username
            FROM reports
            LEFT JOIN users u ON reports.generated_by = u.user_id
            ORDER BY report_id DESC
        """)
        reports = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching reports: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("08_reports.html", reports=reports)


@app.route('/export/payments')
@role_required('admin', 'landlord')
def export_payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get('role') == 'landlord':
            cursor.execute("""
                SELECT p.payment_id, u.username, u.first_name, u.last_name, p.amount, p.payment_method, p.payment_date, p.receipt_number
                FROM payments p
                LEFT JOIN users u ON p.user_id = u.user_id
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY p.payment_id DESC
            """, (session.get('user_id'),))
        else:
            cursor.execute("""
                SELECT p.payment_id, u.username, u.first_name, u.last_name, p.amount, p.payment_method, p.payment_date, p.receipt_number
                FROM payments p
                LEFT JOIN users u ON p.user_id = u.user_id
                ORDER BY p.payment_id DESC
            """)
        rows = cursor.fetchall()
        # CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['payment_id','username','first_name','last_name','amount','method','payment_date','receipt_number'])
        for r in rows:
            cw.writerow(r)
        output = si.getvalue()
        filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        flash(f'Error exporting payments: {e}', 'danger')
        return redirect(url_for('payments'))
    finally:
        cursor.close()
        conn.close()


@app.route('/export/assignments')
@role_required('admin', 'landlord')
def export_assignments():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get('role') == 'landlord':
            cursor.execute("""
                SELECT ra.assignment_id, u.username, r.room_number, b.building_name, ra.start_date, ra.end_date, ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY ra.assignment_id
            """, (session.get('user_id'),))
        else:
            cursor.execute("""
                SELECT ra.assignment_id, u.username, r.room_number, b.building_name, ra.start_date, ra.end_date, ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                ORDER BY ra.assignment_id
            """)
        rows = cursor.fetchall()
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['assignment_id','username','room_number','building_name','start_date','end_date','monthly_rate','status'])
        for r in rows:
            cw.writerow(r)
        output = si.getvalue()
        filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        flash(f'Error exporting assignments: {e}', 'danger')
        return redirect(url_for('assignments'))
    finally:
        cursor.close()
        conn.close()


@app.route('/export/reports')
@role_required('admin')
def export_reports():
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT report_id, report_type, report_title, generated_on, generated_by FROM reports ORDER BY report_id DESC')
            rows = cursor.fetchall()
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['report_id', 'report_type', 'report_title', 'generated_on', 'generated_by'])
            for r in rows:
                cw.writerow(r)
            filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
            return Response(si.getvalue(), mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename={filename}"})
        except Exception as e:
            flash(f'Error exporting reports: {e}', 'danger')
            return redirect(url_for('reports'))
        finally:
            cursor.close()
            conn.close()

@app.route('/debug_session')
def debug_session():
    return {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'session_keys': list(session.keys())
    }

#



# my added codes










# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    print("Starting Flask app on 0.0.0.0:5000")
    # Disable the auto-reloader to keep the server in a single process for debugging here
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
