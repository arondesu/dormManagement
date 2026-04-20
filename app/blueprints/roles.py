from flask import Blueprint, flash, render_template

from db import get_db_connection

from .common import role_required


bp = Blueprint("roles", __name__)


@bp.route("/roles")
@role_required("admin")
def roles():
    conn = get_db_connection()
    cursor = conn.cursor()

    roles_list = []
    try:
        cursor.execute("SELECT role_id, role_name FROM roles ORDER BY role_name")
        roles_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading roles: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template("roles/14_roles.html", roles=roles_list)
