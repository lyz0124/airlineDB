from flask import Blueprint, flash, redirect, request, session, url_for

from ..decorators import role_required
from ..db import get_conn
from ..services.purchase_service import create_purchase, is_agent_authorized

bp = Blueprint("agent", __name__, url_prefix="/agent")


@bp.route("/purchase", methods=["POST"])
@role_required("booking_agent")
def agent_purchase():
    agent_email = session["user_id"]
    customer_email = request.form.get("customer_email", "").strip()
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not customer_email or not airline_name or not flight_num_text.isdigit():
        flash("Customer, airline, and numeric flight number are required.")
        return redirect(url_for("dashboard.dashboard", tab="agent-search"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if not is_agent_authorized(cur, agent_email, airline_name):
                flash("You are not authorized to sell tickets for this airline.")
                return redirect(url_for("dashboard.dashboard", tab="agent-search"))

            success, message = create_purchase(
                cur,
                customer_email,
                airline_name,
                int(flight_num_text),
                booking_agent_email=agent_email,
            )
            if success:
                conn.commit()
            else:
                conn.rollback()
            flash(message)
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[agent_purchase][error] {e}")
        flash("Purchase failed. Please try again.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="agent-search"))
