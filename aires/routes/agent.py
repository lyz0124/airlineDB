from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..decorators import role_required
from ..db import with_cursor
from ..services.dashboard_service import load_agent_dashboard
from ..services.purchase_service import create_purchase, is_agent_authorized

bp = Blueprint("agent", __name__, url_prefix="/agent")


@bp.route("/dashboard")
@role_required("booking_agent")
def agent_dashboard():
    user_id = session["user_id"]
    user_name = session["user_name"]
    context = {
        "role": "booking_agent",
        "user_id": user_id,
        "user_name": user_name,
        "agent_data": None,
    }

    try:
        with with_cursor() as cur:
            context["agent_data"] = load_agent_dashboard(cur, user_id, request.args)
    except Exception as e:
        print(f"[agent_dashboard][error] {e}")
        flash("Failed to load dashboard data.", "danger")

    return render_template("agent_dashboard.html", **context)


@bp.route("/purchase", methods=["POST"])
@role_required("booking_agent")
def agent_purchase():
    agent_email = session["user_id"]
    customer_email = request.form.get("customer_email", "").strip()
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not customer_email or not airline_name or not flight_num_text.isdigit():
        flash("Customer, airline, and numeric flight number are required.", "warning")
        return redirect(url_for("agent.agent_dashboard", tab="agent-search"))

    try:
        with with_cursor() as cur:
            if not is_agent_authorized(cur, agent_email, airline_name):
                flash("You are not authorized to sell tickets for this airline.", "danger")
                return redirect(url_for("agent.agent_dashboard", tab="agent-search"))

            success, message = create_purchase(
                cur,
                customer_email,
                airline_name,
                int(flight_num_text),
                booking_agent_email=agent_email,
            )
            if success:
                cur.connection.commit()
            else:
                cur.connection.rollback()
            flash(message, "success" if success else "danger")
    except Exception as e:
        print(f"[agent_purchase][error] {e}")
        flash("Purchase failed. Please try again.", "danger")
    return redirect(url_for("agent.agent_dashboard", tab="agent-search"))

