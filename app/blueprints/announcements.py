from flask import Blueprint, flash, render_template

from db import get_db_connection

from .common import role_required


bp = Blueprint("announcements", __name__)


@bp.route("/announcements")
@role_required("admin", "landlord", "student")
def announcements():
    conn = get_db_connection()
    cursor = conn.cursor()

    announcements_list = []
    try:
        cursor.execute(
            """
            SELECT a.announcement_id, a.title, a.message, a.created_at,
                   u.first_name AS posted_by_first_name,
                   u.last_name AS posted_by_last_name
            FROM announcements a
            LEFT JOIN users u ON a.posted_by = u.user_id
            ORDER BY a.created_at DESC, a.announcement_id DESC
            """
        )
        announcements_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error loading announcements: {error}", "danger")
    finally:
        cursor.close()
        conn.close()

    return render_template("announcements/13_announcements.html", announcements=announcements_list)
