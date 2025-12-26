
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """
    Create and return a SQLite database connection.
    Returns a connection with row_factory set to sqlite3.Row for dictionary-like access.
    """
    db_path = os.getenv('DB_PATH', 'database/manager.db')
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def init_db():
    """
    Initialize the database with all required tables.
    Run this once to set up the database schema.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'student', 'landlord')),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            phone VARCHAR(30),
            birth_date DATE,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create buildings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            building_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name VARCHAR(100) NOT NULL,
            address VARCHAR(255),
            total_floors INTEGER,
            owner_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE SET NULL
        )
    """)
    
    # Create room_types table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_types (
            type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name VARCHAR(50) NOT NULL,
            base_rate DECIMAL(10,2) NOT NULL,
            capacity INTEGER NOT NULL,
            description TEXT,
            features TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create rooms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER,
            type_id INTEGER,
            room_number VARCHAR(50) NOT NULL,
            floor_number INTEGER,
            is_available BOOLEAN DEFAULT 1,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE SET NULL,
            FOREIGN KEY (type_id) REFERENCES room_types(type_id) ON DELETE SET NULL
        )
    """)
    
    # Create room_assignments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            room_id INTEGER,
            start_date DATE,
            end_date DATE,
            monthly_rate DECIMAL(10,2),
            status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled', 'pending')),
            assigned_by INTEGER,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (assigned_by) REFERENCES users(user_id)
        )
    """)
    
    # Create payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            assignment_id INTEGER,
            amount DECIMAL(10,2),
            payment_method VARCHAR(30),
            payment_date DATE,
            payment_period_start DATE,
            payment_period_end DATE,
            receipt_number VARCHAR(100) UNIQUE,
            recorded_by INTEGER,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (assignment_id) REFERENCES room_assignments(assignment_id),
            FOREIGN KEY (recorded_by) REFERENCES users(user_id)
        )
    """)
    
    # Create reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_by INTEGER,
            report_type VARCHAR(50),
            report_title VARCHAR(200),
            file_path VARCHAR(500),
            generated_on DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (generated_by) REFERENCES users(user_id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()