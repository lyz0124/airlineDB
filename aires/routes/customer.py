from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..decorators import role_required
from ..db import with_cursor
from ..services.dashboard_service import load_customer_dashboard
from ..services.purchase_service import cancel_purchase, create_purchase

bp = Blueprint("customer", __name__, url_prefix="/customer")


@bp.route("/dashboard")
@role_required("customer")
def customer_dashboard():
    user_id = session["user_id"]
    user_name = session["user_name"]
    context = {
        "role": "customer",
        "user_id": user_id,
        "user_name": user_name,
        "customer_data": None,
    }

    try:
        with with_cursor() as cur:
            context["customer_data"] = load_customer_dashboard(cur, user_id, request.args)
    except Exception as e:
        print(f"[customer_dashboard][error] {e}")
        flash("Failed to load dashboard data.", "danger")

    return render_template("customer_dashboard.html", **context)


@bp.route("/purchase", methods=["POST"])
@role_required("customer")
def customer_purchase():
    customer_email = session["user_id"]
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not airline_name or not flight_num_text.isdigit():
        flash("Invalid airline or flight number.", "warning")
        return redirect(url_for("customer.customer_dashboard", tab="customer-search"))

    try:
        with with_cursor() as cur:
            success, message = create_purchase(cur, customer_email, airline_name, int(flight_num_text))
            if success:
                cur.connection.commit()
            else:
                cur.connection.rollback()
            flash(message, "success" if success else "danger")
    except Exception as e:
        print(f"[customer_purchase][error] {e}")
        flash("Purchase failed. Please try again.", "danger")
    return redirect(url_for("customer.customer_dashboard", tab="customer-search"))


@bp.route("/cancel", methods=["POST"])
@role_required("customer")
def customer_cancel():
    customer_email = session["user_id"]
    ticket_id_text = request.form.get("ticket_id", "").strip()
    if not ticket_id_text.isdigit():
        flash("Invalid ticket ID.", "warning")
        return redirect(url_for("customer.customer_dashboard"))

    try:
        with with_cursor() as cur:
            success, message = cancel_purchase(cur, int(ticket_id_text), customer_email)
            if success:
                cur.connection.commit()
            else:
                cur.connection.rollback()
            flash(message, "success" if success else "danger")
    except Exception as e:
        print(f"[customer_cancel][error] {e}")
        flash("Cancellation failed. Please try again.", "danger")
    return redirect(url_for("customer.customer_dashboard"))

