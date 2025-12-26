# Accommo - Dormitory Management System

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-orange)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A modern, web-based dormitory management system built with Flask and SQLite. Designed for universities and dormitory administrators to efficiently manage buildings, rooms, tenants, and payments.

## 📋 Table of Contents

- [Features](#-features)
- [System Objectives](#-system-objectives)
- [Scope & Limitations](#-scope--limitations)
- [Technology Stack](#-technology-stack)
- [Database Schema](#-database-schema)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [User Roles](#-user-roles)
- [Development Guide](#-development-guide)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core Functionality
- **User Management**: Create and manage admin, landlord, and student accounts
- **Building Management**: Track multiple dormitory buildings with floor details
- **Room Management**: Monitor room availability, types, and pricing
- **Assignment Tracking**: Manage tenant-to-room assignments with contract periods
- **Payment Processing**: Record and track rent payments with multiple payment methods
- **Report Generation**: Generate occupancy and payment reports
- **Role-Based Access Control**: Different permissions for admins, landlords, and students

### User Interface
- Modern, responsive design using Bootstrap 5
- Clean, intuitive navigation
- Mobile-friendly layout
- Real-time form validation
- Flash message notifications

---

## 🎯 System Objectives

### Primary Objectives
1. **Streamline Dormitory Operations**: Automate manual processes for room assignments and payment tracking
2. **Centralized Data Management**: Maintain a single source of truth for all dormitory information
3. **Improve Transparency**: Provide clear visibility of room availability and payment status
4. **Reduce Administrative Overhead**: Minimize paperwork through digital record-keeping
5. **Support Multiple Stakeholders**: Serve administrators, landlords, and students with role-specific features

### Secondary Objectives
- Facilitate data-driven decision making through reports
- Ensure data integrity with relational database constraints
- Provide audit trails for all transactions
- Enable scalability for multiple buildings and properties

---

## 🔍 Scope & Limitations

### In Scope
✅ User authentication and authorization  
✅ Building and room inventory management  
✅ Room type categorization with pricing  
✅ Tenant assignment and contract tracking  
✅ Payment recording and history  
✅ Basic reporting (occupancy, payments)  
✅ Role-based access control (Admin, Landlord, Student)  
✅ CSV export functionality  
✅ SQLite database for data persistence  

### Out of Scope (Current Version)
❌ Mobile application  
❌ Online payment processing/gateway integration  
❌ Real-time chat or messaging system  
❌ Maintenance request tracking  
❌ Room inquiry/application system  
❌ Email notifications (SMTP configured but optional)  
❌ Advanced analytics and dashboards  
❌ Document management (contracts, IDs)  
❌ Multi-tenancy support  
❌ Automated rent reminders  

### Known Limitations
- **Single Database**: Uses SQLite (not recommended for high-concurrency production)
- **Local File Storage**: No cloud storage integration
- **Basic Reporting**: Limited to predefined report types
- **Manual Payment Entry**: No automatic payment reconciliation
- **No API**: Currently web-interface only
- **Limited Search**: Basic filtering, no full-text search

---

## 🛠️ Technology Stack

### Backend
- **Python 3.8+**: Core programming language
- **Flask 3.0.0**: Web framework
- **SQLite3**: Database engine
- **Werkzeug 3.0.1**: Password hashing and security

### Frontend
- **HTML5/CSS3**: Markup and styling
- **Bootstrap 5.3.2**: UI framework
- **Vanilla JavaScript**: Client-side interactivity

### Development Tools
- **python-dotenv**: Environment variable management
- **Git**: Version control

---

## 📊 Database Schema

### Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   USERS     │◄────────│  BUILDINGS   │────────►│    ROOMS    │
│             │ owns    │              │ has     │             │
│ - user_id   │         │ - building_id│         │ - room_id   │
│ - username  │         │ - owner_id   │         │ - building_id│
│ - role      │         │              │         │ - type_id   │
└─────────────┘         └──────────────┘         └─────────────┘
      │                                                  │
      │ has                                        has   │
      │                                                  │
      ▼                                                  ▼
┌──────────────────┐                          ┌─────────────┐
│ ROOM_ASSIGNMENTS │◄─────────────────────────│ ROOM_TYPES  │
│                  │                          │             │
│ - assignment_id  │                          │ - type_id   │
│ - user_id        │                          │ - type_name │
│ - room_id        │                          │ - base_rate │
└──────────────────┘                          └─────────────┘
      │
      │ has
      │
      ▼
┌─────────────┐
│  PAYMENTS   │
│             │
│ - payment_id│
│ - user_id   │
│ - assign_id │
└─────────────┘

┌─────────────┐
│   REPORTS   │
│             │
│ - report_id │
│ - generated │
└─────────────┘
```

### Tables Overview

#### users
Stores all system users (admins, landlords, students)
```sql
user_id         INTEGER PRIMARY KEY
username        VARCHAR(100) UNIQUE
password_hash   VARCHAR(255)
role            VARCHAR(20) -- 'admin', 'landlord', 'student'
first_name      VARCHAR(100)
last_name       VARCHAR(100)
email           VARCHAR(150) UNIQUE
phone           VARCHAR(30)
birth_date      DATE
is_active       BOOLEAN DEFAULT 1
created_at      DATETIME
updated_at      DATETIME
```

#### buildings
Dormitory buildings and properties
```sql
building_id     INTEGER PRIMARY KEY
building_name   VARCHAR(100)
address         VARCHAR(255)
total_floors    INTEGER
owner_id        INTEGER FK -> users(user_id)
is_active       BOOLEAN DEFAULT 1
created_at      DATETIME
updated_at      DATETIME
```

#### room_types
Room categories with pricing
```sql
type_id         INTEGER PRIMARY KEY
type_name       VARCHAR(50)
base_rate       DECIMAL(10,2)
capacity        INTEGER
description     TEXT
features        TEXT
is_active       BOOLEAN DEFAULT 1
created_at      DATETIME
updated_at      DATETIME
```

#### rooms
Individual room units
```sql
room_id         INTEGER PRIMARY KEY
building_id     INTEGER FK -> buildings(building_id)
type_id         INTEGER FK -> room_types(type_id)
room_number     VARCHAR(50)
floor_number    INTEGER
is_available    BOOLEAN DEFAULT 1
notes           TEXT
created_at      DATETIME
updated_at      DATETIME
```

#### room_assignments
Tenant-to-room assignments
```sql
assignment_id   INTEGER PRIMARY KEY
user_id         INTEGER FK -> users(user_id)
room_id         INTEGER FK -> rooms(room_id)
start_date      DATE
end_date        DATE
monthly_rate    DECIMAL(10,2)
status          VARCHAR(20) -- 'active', 'completed', 'cancelled', 'pending'
assigned_by     INTEGER FK -> users(user_id)
notes           TEXT
created_at      DATETIME
updated_at      DATETIME
```

#### payments
Rent payment records
```sql
payment_id              INTEGER PRIMARY KEY
user_id                 INTEGER FK -> users(user_id)
assignment_id           INTEGER FK -> room_assignments(assignment_id)
amount                  DECIMAL(10,2)
payment_method          VARCHAR(30)
payment_date            DATE
payment_period_start    DATE
payment_period_end      DATE
receipt_number          VARCHAR(100) UNIQUE
recorded_by             INTEGER FK -> users(user_id)
notes                   TEXT
created_at              DATETIME
updated_at              DATETIME
```

#### reports
Generated system reports
```sql
report_id       INTEGER PRIMARY KEY
generated_by    INTEGER FK -> users(user_id)
report_type     VARCHAR(50)
report_title    VARCHAR(200)
file_path       VARCHAR(500)
generated_on    DATETIME
```

---

## 🚀 Installation

### Prerequisites
```bash
Python 3.8 or higher
pip (Python package manager)
Git (optional)
```

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/accommo.git
cd accommo
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Copy .env.example to .env (or create new .env file)
cp .env.example .env

# Edit .env with your settings
# Minimum required: FLASK_SECRET_KEY
```

### Step 5: Initialize Database
```bash
# Create database schema
python -c "from db import init_db; init_db()"

# Seed with sample data
python seed_data.py
```

### Step 6: Run the Application
```bash
python app.py
```

Visit: `http://localhost:5000`

---

## 🎮 Usage

### Default Login Credentials

| Role     | Username   | Password      |
|----------|------------|---------------|
| Admin    | admin      | admin123      |
| Landlord | landlord1  | landlord123   |
| Student  | student1   | student123    |

**⚠️ Change default passwords in production!**

### Quick Start Guide

#### As Admin:
1. Log in with admin credentials
2. Add landlords via Users → Add User
3. Create buildings via Buildings → Add Building
4. View all system data and manage users

#### As Landlord:
1. Log in with landlord credentials
2. View your assigned buildings
3. Monitor room occupancy
4. Track tenant payments

#### As Student:
1. Register for an account
2. View available rooms
3. Check your room assignment
4. View payment history

---

## 📁 Project Structure

```
accommo/
├── app.py                      # Main Flask application
├── db.py                       # Database connection and schema
├── seed_data.py                # Sample data seeder
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
├── .gitignore                  # Git ignore rules
│
├── database/
│   ├── manager.db             # SQLite database file
│   ├── ERD.md                 # Entity Relationship Diagram (DELETE)
│   └── data_dictionary.md     # Data dictionary (DELETE)
│
├── templates/                  # HTML templates
│   ├── _base.html             # Base layout
│   ├── index.html             # Dashboard
│   ├── logIn.html             # Login page
│   ├── register.html          # Registration page
│   ├── 02_users.html          # Users list
│   ├── 02_add_user.html       # Add user form
│   ├── 02_edit_user.html      # Edit user form
│   ├── 03_buildings.html      # Buildings list
│   ├── 03_add_building.html   # Add building form
│   ├── 03_edit_building.html  # Edit building form
│   ├── 04_room_types.html     # Room types view
│   ├── 05_rooms.html          # Rooms list
│   ├── 06_assignments.html    # Assignments list
│   ├── 07_payment.html        # Payment form
│   ├── 07_payments.html       # Payments list (duplicate - consolidate)
│   └── 08_reports.html        # Reports list
│
├── static/                     # Static assets (optional)
│   ├── css/
│   └── js/
│
└── docs/                       # Documentation (optional)
    └── README.md              # This file
```

### Files to Delete
These files are now consolidated into this README:
- `database/ERD.md` ✂️
- `database/data_dictionary.md` ✂️
- `SYSTEM_STRUCTURE.md` ✂️
- `SETUP_SQLITE.md` ✂️
- `QUICK_REFERENCE.md` (if exists) ✂️
- `CHANGES.md` (if exists) ✂️

---

## 👥 User Roles

### 🔴 Admin
**Permissions:**
- Full system access
- User management (create, edit, delete)
- Building management (all buildings)
- Room management (all rooms)
- Assignment management (all assignments)
- Payment management (all payments)
- Report generation
- System configuration

**Typical Tasks:**
- Onboard new landlords
- Oversee all properties
- Generate system-wide reports
- Manage user accounts

### 🟡 Landlord
**Permissions:**
- View own buildings
- View rooms in own buildings
- View tenant assignments in own buildings
- View payments for own properties
- Export data for own properties

**Typical Tasks:**
- Monitor property occupancy
- Track rental income
- Review tenant information
- Export payment reports

### 🟢 Student
**Permissions:**
- View available rooms
- View own assignment
- View own payment history
- Update own profile

**Typical Tasks:**
- Browse available rooms
- Check room details
- View payment receipts
- Update contact information

---

## 🔧 Development Guide

### Adding New Features

#### 1. Adding a New Route
```python
# In app.py

@app.route('/your_route', methods=['GET', 'POST'])
@role_required('admin', 'landlord')  # Optional: restrict by role
def your_function():
    if request.method == 'POST':
        # Handle form submission
        data = request.form.get('field_name')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO table_name (field) VALUES (?)", (data,))
            conn.commit()
            flash('Success message', 'success')
            return redirect(url_for('your_route'))
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    # GET request - show form or data
    return render_template('your_template.html')
```

#### 2. Adding a Database Table
```python
# In db.py, add to init_db() function

cursor.execute("""
    CREATE TABLE IF NOT EXISTS your_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field_name VARCHAR(100),
        foreign_key INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (foreign_key) REFERENCES other_table(id)
    )
""")
```

#### 3. Creating a New Template
```html
<!-- templates/your_template.html -->
{% extends '_base.html' %}

{% block title %}Your Page Title{% endblock %}

{% block content %}
<div class="container-modern">
    <div class="page-header">
        <h1 class="page-title">Your Title</h1>
        <p class="page-subtitle">Your subtitle</p>
    </div>
    
    <!-- Your content here -->
</div>
{% endblock %}
```

#### 4. Adding Form Validation
```python
# In route handler
from functools import wraps

def validate_form(*required_fields):
    """Decorator to validate required form fields"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if request.method == 'POST':
                missing = [field for field in required_fields 
                          if not request.form.get(field)]
                if missing:
                    flash(f'Missing required fields: {", ".join(missing)}', 'danger')
                    return redirect(request.url)
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/example', methods=['GET', 'POST'])
@validate_form('username', 'email', 'password')
def example():
    # Form is already validated
    pass
```

### Database Query Patterns

#### SELECT with JOIN
```python
cursor.execute("""
    SELECT r.room_id, r.room_number, b.building_name, rt.type_name
    FROM rooms r
    LEFT JOIN buildings b ON r.building_id = b.building_id
    LEFT JOIN room_types rt ON r.type_id = rt.type_id
    WHERE r.is_available = ?
    ORDER BY r.room_number
""", (1,))
rows = [dict(row) for row in cursor.fetchall()]
```

#### INSERT with Error Handling
```python
try:
    cursor.execute("""
        INSERT INTO table_name (field1, field2)
        VALUES (?, ?)
    """, (value1, value2))
    conn.commit()
    flash('Record added successfully', 'success')
except sqlite3.IntegrityError:
    flash('Duplicate entry or constraint violation', 'danger')
except Exception as e:
    flash(f'Database error: {e}', 'danger')
```

#### UPDATE
```python
cursor.execute("""
    UPDATE table_name
    SET field1 = ?, field2 = ?
    WHERE id = ?
""", (value1, value2, record_id))
conn.commit()
```

#### DELETE with FK Check
```python
# Check for dependent records first
cursor.execute("SELECT COUNT(*) FROM child_table WHERE parent_id = ?", (record_id,))
if cursor.fetchone()[0] > 0:
    # Soft delete
    cursor.execute("UPDATE parent_table SET is_active = 0 WHERE id = ?", (record_id,))
    flash('Record deactivated (has dependent records)', 'warning')
else:
    # Hard delete
    cursor.execute("DELETE FROM parent_table WHERE id = ?", (record_id,))
    flash('Record deleted successfully', 'success')
```

### Role-Based Access Control

```python
from functools import wraps

def role_required(*allowed_roles):
    """Decorator to restrict routes by user role"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('login'))
            
            role = session.get('role')
            if role not in allowed_roles:
                flash('Permission denied', 'danger')
                return redirect(url_for('home'))
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Usage
@app.route('/admin_only')
@role_required('admin')
def admin_function():
    pass

@app.route('/landlord_admin')
@role_required('admin', 'landlord')
def landlord_admin_function():
    pass
```

### Frontend Guidelines

#### Modern Form Styling
```html
<form method="POST">
    <div class="form-group mb-3">
        <label class="form-label-modern">Field Label</label>
        <input type="text" name="field_name" class="form-control-modern" 
               placeholder="Enter value" required>
        <small style="color: var(--gray-600); font-size: 0.8125rem;">
            Help text here
        </small>
    </div>
    
    <div class="d-flex gap-2 justify-content-end">
        <a href="{{ url_for('cancel_route') }}" class="btn-secondary-modern">Cancel</a>
        <button type="submit" class="btn-primary-modern">Submit</button>
    </div>
</form>
```

#### Table Display
```html
<div class="card-modern">
    <table class="table-modern w-100">
        <thead>
            <tr>
                <th>Column 1</th>
                <th>Column 2</th>
                <th style="text-align: right;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.field }}</td>
                <td>{{ item.field2 }}</td>
                <td style="text-align: right;">
                    <div class="d-flex gap-2 justify-content-end">
                        <a href="{{ url_for('edit', id=item.id) }}" 
                           class="btn-secondary-modern" 
                           style="padding: 0.375rem 0.75rem; font-size: 0.875rem;">
                            Edit
                        </a>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Not Found
```bash
Error: no such table: users

Solution:
python -c "from db import init_db; init_db()"
python seed_data.py
```

#### 2. Login Fails
```bash
Issue: Correct credentials not working

Solutions:
1. Check database has users: sqlite3 database/manager.db "SELECT * FROM users;"
2. Reseed database: 
   rm database/manager.db
   python -c "from db import init_db; init_db()"
   python seed_data.py
3. Check password hashing in login route
```

#### 3. Import Errors
```bash
Error: ModuleNotFoundError: No module named 'flask'

Solution:
1. Activate virtual environment
2. pip install -r requirements.txt
```

#### 4. Port Already in Use
```bash
Error: Address already in use

Solution:
# Change port in app.py
app.run(debug=True, host="0.0.0.0", port=5001)  # Use different port
```

#### 5. Role Access Denied
```bash
Issue: Cannot access admin-only pages

Solution:
1. Check session: visit /debug_session
2. Verify role in database
3. Log out and log back in
```

### Debug Mode

Enable detailed error messages:
```python
# In .env
DEBUG=True
```

Check session data:
```bash
Visit: http://localhost:5000/debug_session
```

### Database Inspection

```bash
# Open SQLite database
sqlite3 database/manager.db

# Common commands
.tables                          # List all tables
.schema users                    # Show table schema
SELECT * FROM users LIMIT 5;    # View sample data
.quit                           # Exit
```

---

## 📝 Contributing

### How to Contribute

1. **Fork the Repository**
2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make Changes**
   - Follow existing code style
   - Add comments for complex logic
   - Update documentation if needed
4. **Test Thoroughly**
   - Test all CRUD operations
   - Check role-based permissions
   - Verify responsive design
5. **Commit Changes**
   ```bash
   git commit -m "Add: description of your changes"
   ```
6. **Push to Branch**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create Pull Request**

### Code Style Guidelines

- **Python**: Follow PEP 8
- **HTML**: 4-space indentation
- **CSS**: Use existing CSS variables
- **JavaScript**: ES6+ syntax

### Commit Message Format
```
Type: Brief description

Types:
- Add: New feature
- Fix: Bug fix
- Update: Modify existing feature
- Remove: Delete code/feature
- Docs: Documentation only
- Style: Formatting changes
- Refactor: Code restructuring

Example:
Add: CSV export for room assignments
Fix: Login validation for empty passwords
Update: Building form to include owner selection
```

---

## 🔒 Security Considerations

### Production Deployment Checklist

- [ ] Change default passwords
- [ ] Set strong `FLASK_SECRET_KEY`
- [ ] Disable `DEBUG` mode
- [ ] Use HTTPS
- [ ] Implement rate limiting
- [ ] Add CSRF protection
- [ ] Sanitize all user inputs
- [ ] Use environment variables for sensitive data
- [ ] Regular database backups
- [ ] Update dependencies regularly
- [ ] Implement logging and monitoring

### Password Security
```python
# Already implemented in app.py
from werkzeug.security import generate_password_hash, check_password_hash

# Hash password before storing
password_hash = generate_password_hash(password)

# Verify password
check_password_hash(stored_hash, input_password)
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Flask framework and community
- Bootstrap for UI components
- SQLite for database engine
- Contributors and testers

---

## 📞 Support

For issues, questions, or contributions:
- **Issues**: [GitHub Issues](https://github.com/yourusername/accommo/issues)
- **Email**: your.email@example.com
- **Documentation**: [Wiki](https://github.com/yourusername/accommo/wiki)

---

## 🗺️ Roadmap

### Version 2.0 (Planned)
- [ ] Advanced search and filtering
- [ ] Email notification system
- [ ] PDF report generation
- [ ] Maintenance request module
- [ ] Contract document management
- [ ] Payment gateway integration
- [ ] Mobile-responsive improvements

### Version 3.0 (Future)
- [ ] RESTful API
- [ ] Mobile app (iOS/Android)
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Calendar integration
- [ ] Automated rent reminders

---

**Last Updated**: December 2, 2025  
**Version**: 1.0.0  
**Status**: Production Ready ✅
