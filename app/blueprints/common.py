from functools import wraps

from flask import flash, redirect, session, url_for


def role_required(*allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            role = session.get("role")
            if not role or role not in allowed_roles:
                flash("Permission denied: insufficient role.", "danger")
                return redirect(url_for("home"))
            return func(*args, **kwargs)

        return wrapped

    return decorator
