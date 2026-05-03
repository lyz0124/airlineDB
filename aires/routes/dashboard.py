from flask import Blueprint, redirect, session, url_for

from ..decorators import role_required

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@role_required()
def dashboard():
    role = session["user_role"]
    if role == "customer":
        return redirect(url_for("customer.customer_dashboard"))
    elif role == "booking_agent":
        return redirect(url_for("agent.agent_dashboard"))
    elif role == "airline_staff":
        return redirect(url_for("staff.staff_dashboard"))
    return redirect(url_for("public.public_index"))

