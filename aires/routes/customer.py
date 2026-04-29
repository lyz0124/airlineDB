from flask import Blueprint, flash, redirect, request, session, url_for

from ..decorators import role_required
from ..db import get_conn
from ..services.purchase_service import create_purchase

bp = Blueprint("customer", __name__, url_prefix="/customer")


@bp.route("/purchase", methods=["POST"])
@role_required("customer")
def customer_purchase():
    customer_email = session["user_id"]
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not airline_name or not flight_num_text.isdigit():
        flash("Invalid airline or flight number.")
        return redirect(url_for("dashboard.dashboard", tab="customer-search"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            success, message = create_purchase(cur, customer_email, airline_name, int(flight_num_text))
            if success:
                conn.commit()
            else:
                conn.rollback()
            flash(message)
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[customer_purchase][error] {e}")
        flash("Purchase failed. Please try again.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="customer-search"))
