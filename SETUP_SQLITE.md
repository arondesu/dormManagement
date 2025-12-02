# Accommo: Dormitory Management System - SQLite Setup Guide

## 🎯 Overview
This guide will help you migrate from MySQL to SQLite and fix all alignment issues with the project scope document.

---

## 📋 Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for version control)

---

## 🚀 Step-by-Step Setup

### Step 1: Update Dependencies

Create/Update `requirements.txt`:
```txt
Flask==3.0.0
python-dotenv==1.0.0
Werkzeug==3.0.1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### Step 2: Replace Database Files

1. **Replace `db.py`** with the new SQLite version (see artifact `db_sqlite`)
2. **Update `.env`** file with SQLite configuration (see artifact `sqlite_env`)
3. **Create `seed_data.py`** for sample data (see artifact `seed_data_sqlite`)

### Step 3: Update app.py for SQLite

**Global Find & Replace in `app.py`:**

1. **Remove `dictionary=True`:**
   ```python
   # FIND:
   cursor = conn.cursor(dictionary=True)
   
   # REPLACE WITH:
   cursor = conn.cursor()
   ```

2. **Change parameter placeholders:**
   ```python
   # FIND: %s
   # REPLACE WITH: ?
   ```

3. **Convert query results to dictionaries:**
   ```python
   # After fetchall() or fetchone(), wrap in dict():
   
   # For single row:
   user = cursor.fetchone()
   if user:
       user = dict(user)
   
   # For multiple rows:
   users = [dict(row) for row in cursor.fetchall()]
   ```

### Step 4: Initialize Database

Run these commands in order:

```bash
# 1. Initialize database schema
python -c "from db import init_db; init_db()"

# 2. Seed with sample data
python seed_data.py
```

You should see:
```
Database initialized successfully!
Seeding users...
Seeding buildings...
Seeding room types...
Seeding rooms...
Seeding room assignments...
Seeding payments...
Seeding reports...

✓ Database seeded successfully!

Default Login Credentials:
  Admin:    username=admin     password=admin123
  Landlord: username=landlord1 password=landlord123
  Student:  username=student1  password=student123
```

### Step 5: Run the Application

```bash
python app.py
```

Visit: `http://localhost:5000`

---

## 🔧 Key Fixes Applied

### 1. Database Alignment
- ✅ Removed `room_inquiries` table (out of scope)
- ✅ Fixed `owner_id` in buildings table
- ✅ Ensured all tables match data dictionary exactly

### 2. SQLite Compatibility
- ✅ Changed parameter placeholders from `%s` to `?`
- ✅ Removed MySQL-specific `dictionary=True` cursor option
- ✅ Added proper row-to-dict conversion
- ✅ Used SQLite data types (INTEGER, TEXT, REAL, BLOB)

### 3. Scope Compliance
- ✅ Removed out-of-scope features:
  - Mobile app references
  - Online application system
  - Chat/messaging features
  - Maintenance request system
- ✅ Kept only in-scope features per PDF

### 4. Data Dictionary Compliance
All tables now exactly match the data dictionary:
- `users` - User authentication and profiles
- `buildings` - Dormitory buildings
- `room_types` - Room categories with pricing
- `rooms` - Individual room units
- `room_assignments` - Student-to-room mapping
- `payments` - Rent payment tracking
- `reports` - Generated system reports

---

## 🗂️ File Structure

```
dormManagement-1/
├── app.py                 # Main Flask application (UPDATED)
├── db.py                  # SQLite database connection (NEW)
├── seed_data.py           # Database seeding script (NEW)
├── .env                   # Environment variables (UPDATED)
├── requirements.txt       # Python dependencies (UPDATED)
├── database/
│   ├── manager.db        # SQLite database file (AUTO-CREATED)
│   ├── ERD.md            # Entity Relationship Diagram
│   └── data_dictionary.md # Data dictionary documentation
├── static/
│   ├── css/
│   └── js/
└── templates/
    ├── 01_index.html
    ├── 02_*.html         # User management
    ├── 03_*.html         # Building management
    ├── 04_*.html         # Room types
    ├── 05_*.html         # Rooms
    ├── 06_*.html         # Assignments
    ├── 07_*.html         # Payments
    ├── 08_*.html         # Reports
    ├── logIn.html
    ├── register.html
    └── _*.html           # Partials
```

---

Default Login Credentials:
  Admin:    username=admin     password=admin123
  Landlord: username=landlord1 password=landlord123
  Student:  username=student1  password=student123

---

## 🐛 Common Issues & Solutions

### Issue 1: "no such table" error
**Solution:** Run database initialization:
```bash
python -c "from db import init_db; init_db()"
```

### Issue 2: "Incorrect number of bindings"
**Solution:** Check that all `%s` are replaced with `?` in SQL queries

### Issue 3: "Row object has no attribute 'keys'"
**Solution:** Convert rows to dicts:
```python
users = [dict(row) for row in cursor.fetchall()]
```

### Issue 4: Login fails with correct credentials
**Solution:** Reseed the database:
```bash
# Delete old database
rm database/manager.db

# Reinitialize
python -c "from db import init_db; init_db()"
python seed_data.py
```

---

## 📊 Database Location

SQLite database is stored at: `database/manager.db`

To reset database:
```bash
rm database/manager.db
python -c "from db import init_db; init_db()"
python seed_data.py
```

---

## 🔍 Verifying Setup

1. **Check database exists:**
   ```bash
   ls -la database/manager.db
   ```

2. **Query database:**
   ```bash
   sqlite3 database/manager.db "SELECT COUNT(*) FROM users;"
   # Should return: 5
   ```

3. **Test login:**
   - Visit http://localhost:5000/login
   - Use admin/admin123
   - Should redirect to dashboard

---

## 📖 Additional Documentation

- **Project Scope:** See `_Accommo_ Dormitory Information and Management System.pdf`
- **System Structure:** See `SYSTEM_STRUCTURE.md`
- **Quick Reference:** See `QUICK_REFERENCE.md`
- **Changes Log:** See `CHANGES.md`

---

## 🎓 Next Steps

1. ✅ Complete SQLite migration
2. ✅ Test all CRUD operations
3. ⏳ Implement search/filter features
4. ⏳ Add form validation
5. ⏳ Generate PDF reports
6. ⏳ Add authentication middleware
7. ⏳ Deploy to production

---

## 💡 Tips

- **Backup regularly:** `cp database/manager.db database/manager.db.backup`
- **Use DB Browser for SQLite** for visual database inspection
- **Enable foreign keys:** Already enabled in `db.py`
- **Check logs:** Look at Flask console output for errors

---

## 📞 Support

For issues:
1. Check this guide first
2. Review error messages carefully
3. Verify all steps were completed
4. Check Python and Flask versions

---

**Last Updated:** December 2, 2025
**Version:** 2.0 (SQLite Migration)
