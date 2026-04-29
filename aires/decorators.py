from functools import wraps

from flask import flash, redirect, session, url_for


def role_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_role" not in session:
                flash("Please login first.")
                return redirect(url_for("auth.login_page"))
            if role and session.get("user_role") != role:
                flash("Permission denied.")
                return redirect(url_for("dashboard.dashboard"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator
