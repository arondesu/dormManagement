import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, Response, flash, redirect, render_template, session, url_for

from db import get_db_connection

from .common import role_required


bp = Blueprint("reports", __name__)


@bp.route("/reports")
def reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    reports_list = []
    try:
        cursor.execute(
            """
            SELECT report_id, report_type, report_title, generated_on, u.username
            FROM reports
            LEFT JOIN users u ON reports.generated_by = u.user_id
            ORDER BY report_id DESC
        """
        )
        reports_list = cursor.fetchall()
    except Exception as error:
        flash(f"Error fetching reports: {error}", "danger")
    finally:
        cursor.close()
        conn.close()
    return render_template("reports/08_reports.html", reports=reports_list)


@bp.route("/export/payments")
@role_required("admin", "landlord")
def export_payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get("role") == "landlord":
            cursor.execute(
                """
                SELECT p.payment_id, u.username, u.first_name, u.last_name, p.amount, p.payment_method, p.payment_date, p.receipt_number
                FROM payments p
                LEFT JOIN users u ON p.user_id = u.user_id
                LEFT JOIN room_assignments ra ON p.assignment_id = ra.assignment_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY p.payment_id DESC
            """,
                (session.get("user_id"),),
            )
        else:
            cursor.execute(
                """
                SELECT p.payment_id, u.username, u.first_name, u.last_name, p.amount, p.payment_method, p.payment_date, p.receipt_number
                FROM payments p
                LEFT JOIN users u ON p.user_id = u.user_id
                ORDER BY p.payment_id DESC
            """
            )
        rows = cursor.fetchall()
        string_io = StringIO()
        csv_writer = csv.writer(string_io)
        csv_writer.writerow(["payment_id", "username", "first_name", "last_name", "amount", "method", "payment_date", "receipt_number"])
        for row in rows:
            csv_writer.writerow(row)
        output = string_io.getvalue()
        filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as error:
        flash(f"Error exporting payments: {error}", "danger")
        return redirect(url_for("payments"))
    finally:
        cursor.close()
        conn.close()


@bp.route("/export/assignments")
@role_required("admin", "landlord")
def export_assignments():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if session.get("role") == "landlord":
            cursor.execute(
                """
                SELECT ra.assignment_id, u.username, r.room_number, b.building_name, ra.start_date, ra.end_date, ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                WHERE b.owner_id = ?
                ORDER BY ra.assignment_id
            """,
                (session.get("user_id"),),
            )
        else:
            cursor.execute(
                """
                SELECT ra.assignment_id, u.username, r.room_number, b.building_name, ra.start_date, ra.end_date, ra.monthly_rate, ra.status
                FROM room_assignments ra
                LEFT JOIN users u ON ra.user_id = u.user_id
                LEFT JOIN rooms r ON ra.room_id = r.room_id
                LEFT JOIN buildings b ON r.building_id = b.building_id
                ORDER BY ra.assignment_id
            """
            )
        rows = cursor.fetchall()
        string_io = StringIO()
        csv_writer = csv.writer(string_io)
        csv_writer.writerow(["assignment_id", "username", "room_number", "building_name", "start_date", "end_date", "monthly_rate", "status"])
        for row in rows:
            csv_writer.writerow(row)
        output = string_io.getvalue()
        filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as error:
        flash(f"Error exporting assignments: {error}", "danger")
        return redirect(url_for("assignments"))
    finally:
        cursor.close()
        conn.close()


@bp.route("/export/reports")
@role_required("admin")
def export_reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT report_id, report_type, report_title, generated_on, generated_by FROM reports ORDER BY report_id DESC")
        rows = cursor.fetchall()
        string_io = StringIO()
        csv_writer = csv.writer(string_io)
        csv_writer.writerow(["report_id", "report_type", "report_title", "generated_on", "generated_by"])
        for row in rows:
            csv_writer.writerow(row)
        filename = f"payments_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        return Response(
            string_io.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"},
        )
    except Exception as error:
        flash(f"Error exporting reports: {error}", "danger")
        return redirect(url_for("reports"))
    finally:
        cursor.close()
        conn.close()


@bp.route("/debug_session")
def debug_session():
    return {
        "user_id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
        "session_keys": list(session.keys()),
    }
