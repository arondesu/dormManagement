from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("tenants", __name__)


@bp.route("/tenants")
@role_required("admin", "landlord")
def tenants():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT t.tenant_id, t.tenant_code, t.status, t.check_in_date, t.check_out_date,
                   t.emergency_contact_name, t.emergency_contact_phone,
                   u.user_id, u.username, u.first_name, u.last_name, u.email,
                   r.room_number, b.building_name
            FROM tenants t
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN room_assignments ra ON ra.user_id = t.user_id AND ra.status = 'active'
            LEFT JOIN rooms r ON r.room_id = ra.room_id
            LEFT JOIN buildings b ON b.building_id = r.building_id
            WHERE 1 = 1
        """
        params = []

        if session.get("role") == "landlord":
            query += " AND (b.owner_id = ? OR b.owner_id IS NULL)"
            params.append(session.get("user_id"))

        if search:
            like_search = f"%{search}%"
            query += " AND (u.first_name LIKE ? OR u.last_name LIKE ? OR u.username LIKE ? OR t.tenant_code LIKE ?)"
            params.extend([like_search, like_search, like_search, like_search])

        if status_filter and status_filter != "all":
            query += " AND t.status = ?"
            params.append(status_filter)

        query += " ORDER BY t.tenant_id DESC"

        cursor.execute(query, params)
        tenants_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading tenants: {error}", "danger")
        tenants_list = []
    finally:
        cursor.close()
        conn.close()

    return render_template("tenants/09_tenants.html", tenants=tenants_list, search=search, status_filter=status_filter)


@bp.route("/add_tenant", methods=["GET", "POST"])
@role_required("admin", "landlord")
def add_tenant():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        user_id = request.form.get("user_id") or None
        tenant_code = (request.form.get("tenant_code") or "").strip() or None
        emergency_contact_name = (request.form.get("emergency_contact_name") or "").strip() or None
        emergency_contact_phone = (request.form.get("emergency_contact_phone") or "").strip() or None
        guardian_name = (request.form.get("guardian_name") or "").strip() or None
        status = (request.form.get("status") or "active").strip().lower()
        check_in_date = request.form.get("check_in_date") or None
        check_out_date = request.form.get("check_out_date") or None
        notes = (request.form.get("notes") or "").strip() or None

        try:
            cursor.execute(
                """
                INSERT INTO tenants (
                    user_id, tenant_code, emergency_contact_name, emergency_contact_phone,
                    guardian_name, status, check_in_date, check_out_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    tenant_code,
                    emergency_contact_name,
                    emergency_contact_phone,
                    guardian_name,
                    status,
                    check_in_date,
                    check_out_date,
                    notes,
                ),
            )
            conn.commit()
            flash("Tenant added successfully!", "success")
            return redirect(url_for("tenants"))
        except Exception as error:
            flash(f"Error adding tenant: {error}", "danger")

    cursor.execute(
        """
        SELECT user_id, username, first_name, last_name, email
        FROM users
        WHERE role = 'student' AND is_active = 1
          AND user_id NOT IN (SELECT user_id FROM tenants WHERE user_id IS NOT NULL)
        ORDER BY first_name, last_name
        """
    )
    students = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("tenants/09_add_tenant.html", students=students)


@bp.route("/edit_tenant/<int:tenant_id>", methods=["GET", "POST"])
@role_required("admin", "landlord")
def edit_tenant(tenant_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,))
    tenant = cursor.fetchone()

    if not tenant:
        cursor.close()
        conn.close()
        flash("Tenant not found.", "warning")
        return redirect(url_for("tenants"))

    if request.method == "POST":
        user_id = request.form.get("user_id") or None
        tenant_code = (request.form.get("tenant_code") or "").strip() or None
        emergency_contact_name = (request.form.get("emergency_contact_name") or "").strip() or None
        emergency_contact_phone = (request.form.get("emergency_contact_phone") or "").strip() or None
        guardian_name = (request.form.get("guardian_name") or "").strip() or None
        status = (request.form.get("status") or "active").strip().lower()
        check_in_date = request.form.get("check_in_date") or None
        check_out_date = request.form.get("check_out_date") or None
        notes = (request.form.get("notes") or "").strip() or None

        try:
            cursor.execute(
                """
                UPDATE tenants
                SET user_id = ?, tenant_code = ?, emergency_contact_name = ?, emergency_contact_phone = ?,
                    guardian_name = ?, status = ?, check_in_date = ?, check_out_date = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ?
                """,
                (
                    user_id,
                    tenant_code,
                    emergency_contact_name,
                    emergency_contact_phone,
                    guardian_name,
                    status,
                    check_in_date,
                    check_out_date,
                    notes,
                    tenant_id,
                ),
            )
            conn.commit()
            flash("Tenant updated successfully!", "success")
            return redirect(url_for("tenants"))
        except Exception as error:
            flash(f"Error updating tenant: {error}", "danger")

    cursor.execute(
        """
        SELECT user_id, username, first_name, last_name, email
        FROM users
        WHERE role = 'student' AND is_active = 1
          AND (
                user_id = ?
                OR user_id NOT IN (SELECT user_id FROM tenants WHERE user_id IS NOT NULL AND tenant_id <> ?)
              )
        ORDER BY first_name, last_name
        """,
        (tenant["user_id"], tenant_id),
    )
    students = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("tenants/09_edit_tenant.html", tenant=tenant, students=students)


@bp.route("/delete_tenant/<int:tenant_id>", methods=["POST"])
@role_required("admin", "landlord")
def delete_tenant(tenant_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE beds SET occupied_by_tenant_id = NULL, is_available = 1 WHERE occupied_by_tenant_id = ?", (tenant_id,))
        cursor.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
        conn.commit()
        flash("Tenant deleted successfully!", "success")
    except Exception as error:
        flash(f"Error deleting tenant: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("tenants"))
