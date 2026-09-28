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
manager_or_admin = role_required("admin", "manager", "super_admin")  # Phase 13: super admin sees all
content_manager_required = role_required("admin", "manager", "faculty", "content_manager")  # Phase 13


def permission_required(module, action):
    """Phase 9 (§18.3): enforce the granular permission matrix.

    Checks the DB-backed role × module × action matrix (seeded with
    defaults that mirror the legacy role checks). Falls back to built-in
    defaults before the matrix is seeded. Admins always pass.
    """
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            from .operations import has_permission  # lazy: avoid import cycle
            if not has_permission(current_user, module, action):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
