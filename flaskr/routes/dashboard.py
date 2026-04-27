from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..decorators import role_required
from ..db import get_conn
from ..services.dashboard_service import (
    load_agent_dashboard,
    load_customer_dashboard,
    load_staff_dashboard,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@role_required()
def dashboard():
    role = session["user_role"]
    user_id = session["user_id"]
    user_name = session["user_name"]
    tab = request.args.get("tab", "").strip()
    context = {
        "role": role,
        "user_id": user_id,
        "user_name": user_name,
        "tab": tab,
        "customer_data": None,
        "agent_data": None,
        "staff_data": None,
    }

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if role == "customer":
                context["customer_data"] = load_customer_dashboard(cur, user_id, request.args)
            elif role == "booking_agent":
                context["agent_data"] = load_agent_dashboard(cur, user_id, request.args)
            elif role == "airline_staff":
                context["staff_data"] = load_staff_dashboard(cur, user_id, request.args)
    except Exception as e:
        print(f"[dashboard][error] {e}")
        flash("Failed to load dashboard data.")
    finally:
        if conn:
            conn.close()

    return render_template("dashboard.html", **context)
