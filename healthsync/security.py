"""Authentication helpers: current user and role-based access decorator."""
from functools import wraps
from flask import abort, flash, g, redirect, request, session, url_for
from .db import q


def current_user():
    if "user" not in g:
        uid = session.get("uid")
        g.user = q("SELECT * FROM users WHERE id=? AND active=1", (uid,), one=True) if uid else None
    return g.user


def login_required(*roles):
    """Require a logged-in user, optionally restricted to the given roles."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login", next=request.path))
            if roles and user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator
