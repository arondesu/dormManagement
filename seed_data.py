"""
Seed script to populate the SQLite database with initial data.
Run this after initializing the database with db.init_db()
"""

import sqlite3
from werkzeug.security import generate_password_hash
from db import get_db_connection

def seed_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Insert Users
        print("Seeding users...")
        users_data = [
            ('admin', generate_password_hash('admin123'), 'admin', 'System', 'Admin', 'admin@accommo.com', '09123456789', '1990-01-01'),
            ('landlord1', generate_password_hash('landlord123'), 'landlord', 'John', 'Landlord', 'landlord@accommo.com', '09234567890', '1985-05-15'),
            ('student1', generate_password_hash('student123'), 'student', 'Maria', 'Santos', 'maria.santos@student.edu', '09345678901', '2002-03-20'),
            ('student2', generate_password_hash('student123'), 'student', 'Juan', 'Cruz', 'juan.cruz@student.edu', '09456789012', '2001-07-10'),
            ('student3', generate_password_hash('student123'), 'student', 'Ana', 'Reyes', 'ana.reyes@student.edu', '09567890123', '2003-11-25'),
        ]
        
        cursor.executemany("""
            INSERT INTO users (username, password_hash, role, first_name, last_name, email, phone, birth_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, users_data)
        
        # 2. Insert Buildings
        print("Seeding buildings...")
        buildings_data = [
            ('Dormitory A', 'UC Main Campus - Building A', 5, 2, 1),  # owner_id = 2 (landlord)
            ('Dormitory B', 'UC Main Campus - Building B', 4, 2, 1),
            ('Dormitory C', 'UC Main Campus - Building C', 3, 2, 1),
        ]
        
        cursor.executemany("""
            INSERT INTO buildings (building_name, address, total_floors, owner_id, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, buildings_data)
        
        # 3. Insert Room Types
        print("Seeding room types...")
        room_types_data = [
            ('Single', 5000.00, 1, 'Single occupancy room with bed, desk, and cabinet', 'Bed, Desk, Cabinet, Window', 1),
            ('Double', 3500.00, 2, 'Two-bed room shared by two students', '2 Beds, 2 Cabinets, Study Table, Window', 1),
            ('Suite', 8000.00, 2, 'Premium room with private bathroom', 'Private CR, Aircon, 2 Beds, Study Area, Balcony', 1),
        ]
        
        cursor.executemany("""
            INSERT INTO room_types (type_name, base_rate, capacity, description, features, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, room_types_data)
        
        # 4. Insert Rooms
        print("Seeding rooms...")
        rooms_data = [
            # Building 1 (Dormitory A)
            (1, 1, 'A101', 1, 0, 'Currently occupied - EXPIRED assignment (test scenario)'),
            (1, 2, 'A102', 1, 1, 'Good ventilation'),
            (1, 2, 'A103', 1, 0, 'Currently occupied'),
            (1, 3, 'A201', 2, 1, 'Premium suite room'),
            (1, 1, 'A202', 2, 1, 'Spacious single room'),
            
            # Building 2 (Dormitory B)
            (2, 2, 'B101', 1, 1, 'Shared room'),
            (2, 1, 'B102', 1, 1, 'Single room available'),
            (2, 2, 'B201', 2, 0, 'Currently occupied'),
            (2, 3, 'B202', 2, 1, 'Premium suite'),
            
            # Building 3 (Dormitory C)
            (3, 2, 'C101', 1, 1, 'Standard double'),
            (3, 2, 'C102', 1, 1, 'Standard double'),
            (3, 1, 'C201', 2, 1, 'Single with balcony'),
        ]
        
        cursor.executemany("""
            INSERT INTO rooms (building_id, type_id, room_number, floor_number, is_available, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rooms_data)
        
        # 5. Insert Room Assignments
        print("Seeding room assignments...")
        assignments_data = [
            (3, 3, '2025-01-01', '2025-12-31', 3500.00, 'active', 1, 'Initial assignment'),  # student1 -> A103
            (4, 8, '2025-02-01', '2025-12-31', 3500.00, 'active', 1, 'Mid-year assignment'),  # student2 -> B201
            
            # EXPIRED ASSIGNMENT SCENARIO (for testing expire_assignments feature)
            # John had Room 101 (A101) from Jan 1 - Nov 30, 2025
            # Today is Dec 13, 2025 - this should be auto-expired
            (5, 1, '2025-01-01', '2025-11-30', 5000.00, 'active', 1, 'EXPIRED - Should be completed'),  # student3 -> A101 (EXPIRED!)
        ]
        
        cursor.executemany("""
            INSERT INTO room_assignments (user_id, room_id, start_date, end_date, monthly_rate, status, assigned_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, assignments_data)
        
        # 6. Insert Payments
        print("Seeding payments...")
        payments_data = [
            (3, 1, 3500.00, 'cash', '2025-01-05', '2025-01-01', '2025-01-31', 'RCPT-001', 1, 'January payment'),
            (3, 1, 3500.00, 'bank_transfer', '2025-02-05', '2025-02-01', '2025-02-28', 'RCPT-002', 1, 'February payment'),
            (4, 2, 3500.00, 'cash', '2025-02-10', '2025-02-01', '2025-02-28', 'RCPT-003', 1, 'February payment'),
        ]
        
        cursor.executemany("""
            INSERT INTO payments (user_id, assignment_id, amount, payment_method, payment_date, payment_period_start, payment_period_end, receipt_number, recorded_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, payments_data)
        
        # 7. Insert Sample Reports
        print("Seeding reports...")
        reports_data = [
            (1, 'occupancy', 'January 2025 Occupancy Report', '/reports/occupancy_jan2025.pdf'),
            (1, 'payments', 'February 2025 Payment Summary', '/reports/payment_feb2025.pdf'),
            (1, 'user_summary', 'Active Users Report 2025', '/reports/users_2025.pdf'),
        ]
        
        cursor.executemany("""
            INSERT INTO reports (generated_by, report_type, report_title, file_path)
            VALUES (?, ?, ?, ?)
        """, reports_data)
        
        conn.commit()
        print("\n✓ Database seeded successfully!")
        print("\nDefault Login Credentials:")
        print("  Admin:    username=admin     password=admin123")
        print("  Landlord: username=landlord1 password=landlord123")
        print("  Student:  username=student1  password=student123")
        
    except sqlite3.IntegrityError as e:
        print(f"Error: {e}")
        print("Database might already be seeded. If you want to reseed, delete the database file first.")
        conn.rollback()
    except Exception as e:
        print(f"Unexpected error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_database()
