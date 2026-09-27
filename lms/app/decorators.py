"""Role-based access helpers."""
from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


admin_required = role_required("admin")
manager_or_admin = role_required("admin", "manager")
content_manager_required = role_required("admin", "manager", "faculty")
