import json


def log_audit_event(connection, actor_user_id, action, entity_type, entity_id=None, details=None):
    cursor = connection.cursor()
    details_text = json.dumps(details) if details is not None else None
    cursor.execute(
        """
        INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor_user_id, action, entity_type, entity_id, details_text),
    )
