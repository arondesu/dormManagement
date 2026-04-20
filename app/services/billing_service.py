from datetime import date


def derive_invoice_status(total_amount, amount_paid, due_date=None, force_status=None):
    if force_status in {"draft", "cancelled"}:
        return force_status

    total_value = float(total_amount or 0)
    paid_value = float(amount_paid or 0)

    if paid_value <= 0:
        if due_date and str(due_date) < str(date.today()):
            return "overdue"
        return "unpaid"

    if paid_value < total_value:
        if due_date and str(due_date) < str(date.today()):
            return "overdue"
        return "partial"

    return "paid"


def refresh_invoice_status(connection, invoice_id, force_status=None):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT total_amount, amount_paid, due_date, status
        FROM invoices
        WHERE invoice_id = ?
        """,
        (invoice_id,),
    )
    invoice = cursor.fetchone()
    if not invoice:
        return None

    next_status = derive_invoice_status(
        total_amount=invoice["total_amount"],
        amount_paid=invoice["amount_paid"],
        due_date=invoice["due_date"],
        force_status=force_status,
    )
    cursor.execute(
        "UPDATE invoices SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE invoice_id = ?",
        (next_status, invoice_id),
    )
    return next_status


def remove_payment_allocations(connection, payment_id):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT invoice_id, allocated_amount FROM payment_allocations WHERE payment_id = ?",
        (payment_id,),
    )
    allocations = cursor.fetchall()

    for allocation in allocations:
        cursor.execute(
            """
            UPDATE invoices
            SET amount_paid = CASE
                WHEN amount_paid - ? < 0 THEN 0
                ELSE amount_paid - ?
            END,
            updated_at = CURRENT_TIMESTAMP
            WHERE invoice_id = ?
            """,
            (allocation["allocated_amount"], allocation["allocated_amount"], allocation["invoice_id"]),
        )
        refresh_invoice_status(connection, allocation["invoice_id"])

    cursor.execute("DELETE FROM payment_allocations WHERE payment_id = ?", (payment_id,))


def allocate_payment_to_invoices(connection, payment_id, user_id, payment_amount, preferred_invoice_id=None):
    cursor = connection.cursor()
    remaining = float(payment_amount or 0)

    if remaining <= 0:
        return []

    invoice_rows = []

    if preferred_invoice_id:
        cursor.execute(
            """
            SELECT invoice_id, total_amount, amount_paid, due_date
            FROM invoices
            WHERE invoice_id = ?
            """,
            (preferred_invoice_id,),
        )
        preferred = cursor.fetchone()
        if preferred:
            invoice_rows.append(preferred)

    cursor.execute(
        """
        SELECT i.invoice_id, i.total_amount, i.amount_paid, i.due_date
        FROM invoices i
        LEFT JOIN tenants t ON t.tenant_id = i.tenant_id
        WHERE t.user_id = ?
          AND i.status NOT IN ('paid', 'cancelled', 'draft')
        ORDER BY i.due_date ASC, i.invoice_id ASC
        """,
        (user_id,),
    )

    existing_ids = {row["invoice_id"] for row in invoice_rows}
    for invoice in cursor.fetchall():
        if invoice["invoice_id"] not in existing_ids:
            invoice_rows.append(invoice)

    allocations = []

    for invoice in invoice_rows:
        if remaining <= 0:
            break

        open_balance = float(invoice["total_amount"] or 0) - float(invoice["amount_paid"] or 0)
        if open_balance <= 0:
            continue

        allocate_amount = min(remaining, open_balance)

        cursor.execute(
            """
            INSERT INTO payment_allocations (payment_id, invoice_id, allocated_amount)
            VALUES (?, ?, ?)
            """,
            (payment_id, invoice["invoice_id"], allocate_amount),
        )

        cursor.execute(
            """
            UPDATE invoices
            SET amount_paid = amount_paid + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE invoice_id = ?
            """,
            (allocate_amount, invoice["invoice_id"]),
        )

        refresh_invoice_status(connection, invoice["invoice_id"])

        allocations.append(
            {
                "invoice_id": invoice["invoice_id"],
                "allocated_amount": allocate_amount,
            }
        )
        remaining -= allocate_amount

    return allocations


def generate_monthly_invoices(connection, issue_date, due_date, actor_user_id=None, owner_user_id=None):
    cursor = connection.cursor()

    query = """
        SELECT ra.assignment_id, ra.monthly_rate, ra.user_id,
               r.room_number, b.building_name,
               t.tenant_id
        FROM room_assignments ra
        JOIN rooms r ON r.room_id = ra.room_id
        JOIN buildings b ON b.building_id = r.building_id
        LEFT JOIN tenants t ON t.user_id = ra.user_id
        WHERE ra.status = 'active'
    """
    params = []

    if owner_user_id:
        query += " AND b.owner_id = ?"
        params.append(owner_user_id)

    cursor.execute(query, params)
    active_assignments = cursor.fetchall()

    generated = 0
    skipped = 0

    for assignment in active_assignments:
        tenant_id = assignment["tenant_id"]
        assignment_id = assignment["assignment_id"]
        monthly_rate = float(assignment["monthly_rate"] or 0)

        invoice_number = f"INV-{issue_date.replace('-', '')}-{assignment_id}"

        cursor.execute("SELECT invoice_id FROM invoices WHERE invoice_number = ?", (invoice_number,))
        existing = cursor.fetchone()
        if existing:
            skipped += 1
            continue

        cursor.execute(
            """
            INSERT INTO invoices (
                tenant_id, assignment_id, invoice_number, issue_date, due_date,
                subtotal, late_fee, total_amount, amount_paid, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, 'unpaid', ?)
            """,
            (
                tenant_id,
                assignment_id,
                invoice_number,
                issue_date,
                due_date,
                monthly_rate,
                monthly_rate,
                f"Auto-generated for {assignment['building_name']} Room {assignment['room_number']}",
            ),
        )
        generated += 1

    return {"generated": generated, "skipped": skipped, "total": len(active_assignments)}
