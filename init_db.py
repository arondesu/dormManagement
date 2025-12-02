import sqlite3

conn = sqlite3.connect("dorm.db")
c = conn.cursor()

# USERS TABLE
c.execute("""
          
    ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'student';

""")

# BUILDINGS TABLE
c.execute("""
CREATE TABLE IF NOT EXISTS buildings (
    building_id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_name TEXT,
    address TEXT,
    total_floors INTEGER,
    owner_id INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TEXT,
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);
""")

# ROOM TYPES
c.execute("""
CREATE TABLE IF NOT EXISTS room_types (
    type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT,
    base_rate REAL,
    capacity INTEGER,
    description TEXT,
    is_active INTEGER DEFAULT 1
);
""")

# ROOMS
c.execute("""
CREATE TABLE IF NOT EXISTS rooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT,
    floor_number INTEGER,
    building_id INTEGER,
    type_id INTEGER,
    is_available INTEGER DEFAULT 1,
    FOREIGN KEY (building_id) REFERENCES buildings(building_id),
    FOREIGN KEY (type_id) REFERENCES room_types(type_id)
);
""")

# ROOM ASSIGNMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS room_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    room_id INTEGER,
    start_date TEXT,
    end_date TEXT,
    monthly_rate REAL,
    status TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);
""")

# PAYMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    assignment_id INTEGER,
    amount REAL,
    payment_method TEXT,
    payment_date TEXT,
    receipt_number TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (assignment_id) REFERENCES room_assignments(assignment_id)
);
""")

# REPORTS
c.execute("""
CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT,
    report_title TEXT,
    generated_on TEXT,
    generated_by INTEGER,
    FOREIGN KEY (generated_by) REFERENCES users(user_id)
);
""")

conn.commit()
conn.close()

print("SQLite database initialized!")
