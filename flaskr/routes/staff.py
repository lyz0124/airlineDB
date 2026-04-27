from datetime import datetime

from flask import Blueprint, flash, redirect, request, session, url_for

import pymysql

from ..decorators import role_required
from ..db import get_conn
from ..services.common import get_staff_profile, staff_has_permission
from ..services.staff_service import build_flight_update_payload

bp = Blueprint("staff", __name__, url_prefix="/staff")


@bp.route("/add-airport", methods=["POST"])
@role_required("airline_staff")
def staff_add_airport():
    staff_user = session["user_id"]
    airport_name = request.form.get("airport_name", "").strip()
    airport_city = request.form.get("airport_city", "").strip()
    if not airport_name or not airport_city:
        flash("Airport name and city are required.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))
            cur.execute("INSERT IGNORE INTO city (city_name) VALUES (%s)", (airport_city,))
            cur.execute(
                """
                INSERT INTO airport (airport_name, airport_city)
                VALUES (%s, %s)
                """,
                (airport_name, airport_city),
            )
            conn.commit()
            flash("Airport added successfully.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_add_airport][error] {e}")
        flash("Failed to add airport.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-admin"))


@bp.route("/add-airplane", methods=["POST"])
@role_required("airline_staff")
def staff_add_airplane():
    staff_user = session["user_id"]
    airplane_id_text = request.form.get("airplane_id", "").strip()
    seat_capacity_text = request.form.get("seat_capacity", "").strip()
    if not airplane_id_text.isdigit() or not seat_capacity_text.isdigit():
        flash("Airplane ID and seat capacity must be integers.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT INTO airplane (airline_name, airplane_id, seat_capacity)
                VALUES (%s, %s, %s)
                """,
                (profile["airline_name"], int(airplane_id_text), int(seat_capacity_text)),
            )
            conn.commit()
            flash("Airplane added successfully.")
    except pymysql.IntegrityError as e:
        if conn:
            conn.rollback()
        print(f"[staff_add_airplane][integrity_error] {e}")
        flash("Failed to add airplane: duplicate airplane ID for this airline.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_add_airplane][error] {e}")
        flash("Failed to add airplane.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-admin"))


@bp.route("/create-flight", methods=["POST"])
@role_required("airline_staff")
def staff_create_flight():
    staff_user = session["user_id"]
    flight_num_text = request.form.get("flight_num", "").strip()
    departure_airport = request.form.get("departure_airport", "").strip()
    departure_time = request.form.get("departure_time", "").strip()
    arrival_airport = request.form.get("arrival_airport", "").strip()
    arrival_time = request.form.get("arrival_time", "").strip()
    price_text = request.form.get("price", "").strip()
    status = request.form.get("status", "upcoming").strip()
    airplane_id_text = request.form.get("airplane_id", "").strip()

    if not flight_num_text.isdigit() or not airplane_id_text.isdigit():
        flash("Flight number is required and airplane ID must be an integer.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    try:
        dep_dt = datetime.strptime(departure_time, "%Y-%m-%dT%H:%M")
        arr_dt = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M")
        if arr_dt <= dep_dt:
            flash("Arrival time must be later than departure time.")
            return redirect(url_for("dashboard.dashboard", tab="staff-admin"))
        price_value = float(price_text)
        if price_value <= 0:
            flash("Price must be positive.")
            return redirect(url_for("dashboard.dashboard", tab="staff-admin"))
    except ValueError:
        flash("Invalid datetime or price format.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT INTO flight
                (airline_name, flight_num, departure_airport, departure_time,
                 arrival_airport, arrival_time, price, status, airplane_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    profile["airline_name"],
                    int(flight_num_text),
                    departure_airport,
                    dep_dt,
                    arrival_airport,
                    arr_dt,
                    price_value,
                    status,
                    int(airplane_id_text),
                ),
            )
            conn.commit()
            flash("Flight created successfully.")
    except pymysql.IntegrityError as e:
        if conn:
            conn.rollback()
        print(f"[staff_create_flight][integrity_error] {e}")
        flash("Failed to create flight: check duplicate flight number, airplane ID, and airport codes.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_create_flight][error] {e}")
        flash("Failed to create flight.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-admin"))


@bp.route("/edit-flight", methods=["POST"])
@role_required("airline_staff")
def staff_edit_flight():
    staff_user = session["user_id"]
    airline_name = request.form.get("airline_name", "").strip()
    flight_num = request.form.get("flight_num", "").strip()
    form_data = {
        "new_flight_num": request.form.get("new_flight_num", "").strip(),
        "departure_airport": request.form.get("departure_airport", "").strip(),
        "departure_time": request.form.get("departure_time", "").strip(),
        "arrival_airport": request.form.get("arrival_airport", "").strip(),
        "arrival_time": request.form.get("arrival_time", "").strip(),
        "price": request.form.get("price", "").strip(),
        "status": request.form.get("status", "").strip(),
        "airplane_id": request.form.get("airplane_id", "").strip(),
    }

    if not airline_name or not flight_num:
        flash("Airline and current flight number are required.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))
    if not flight_num.isdigit():
        flash("Current flight number must be an integer.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))
            if airline_name != profile["airline_name"]:
                flash("You can only edit flights for your airline.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute(
                """
                SELECT airline_name, flight_num, departure_airport, departure_time,
                       arrival_airport, arrival_time, price, status, airplane_id
                FROM flight
                WHERE airline_name = %s AND flight_num = %s
                """,
                (airline_name, int(flight_num)),
            )
            existing = cur.fetchone()
            if not existing:
                flash("Flight not found.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            update_payload, error_message = build_flight_update_payload(existing, form_data)
            if error_message:
                flash(error_message)
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute(
                """
                UPDATE flight
                SET flight_num = %s,
                    departure_airport = %s,
                    departure_time = %s,
                    arrival_airport = %s,
                    arrival_time = %s,
                    price = %s,
                    status = %s,
                    airplane_id = %s
                WHERE airline_name = %s AND flight_num = %s
                """,
                (
                    update_payload["flight_num"],
                    update_payload["departure_airport"],
                    update_payload["departure_time"],
                    update_payload["arrival_airport"],
                    update_payload["arrival_time"],
                    update_payload["price"],
                    update_payload["status"],
                    update_payload["airplane_id"],
                    airline_name,
                    int(flight_num),
                ),
            )
            conn.commit()
            flash("Flight updated successfully.")
    except ValueError:
        if conn:
            conn.rollback()
        flash("Invalid format for datetime, price, or airplane ID.")
    except pymysql.IntegrityError as e:
        if conn:
            conn.rollback()
        print(f"[staff_edit_flight][integrity_error] {e}")
        flash("Failed to edit flight: check flight number uniqueness, airport code, and airplane ID.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_edit_flight][error] {e}")
        flash("Failed to edit flight.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-admin"))


@bp.route("/authorize-agent", methods=["POST"])
@role_required("airline_staff")
def staff_authorize_agent():
    staff_user = session["user_id"]
    agent_email = request.form.get("agent_email", "").strip()
    if not agent_email:
        flash("Agent email is required.")
        return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute("SELECT 1 FROM booking_agent WHERE email = %s", (agent_email,))
            if not cur.fetchone():
                flash("Booking agent does not exist.")
                return redirect(url_for("dashboard.dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT IGNORE INTO agent_airline_authorization (agent_email, airline_name)
                VALUES (%s, %s)
                """,
                (agent_email, profile["airline_name"]),
            )
            conn.commit()
            flash("Agent authorized for this airline.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_authorize_agent][error] {e}")
        flash("Failed to authorize agent.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-admin"))


@bp.route("/update-flight-status", methods=["POST"])
@role_required("airline_staff")
def staff_update_flight_status():
    staff_user = session["user_id"]
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    status = request.form.get("status", "").strip()
    if not flight_num_text.isdigit() or status not in {"upcoming", "in-progress", "delayed"}:
        flash("Invalid input for status update.")
        return redirect(url_for("dashboard.dashboard", tab="staff-operator"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "operator"):
                flash("Operator permission required.")
                return redirect(url_for("dashboard.dashboard", tab="staff-operator"))

            if airline_name != profile["airline_name"]:
                flash("You can only update flights for your airline.")
                return redirect(url_for("dashboard.dashboard", tab="staff-operator"))

            cur.execute(
                """
                UPDATE flight
                SET status = %s
                WHERE airline_name = %s AND flight_num = %s
                """,
                (status, airline_name, int(flight_num_text)),
            )
            if cur.rowcount == 0:
                flash("Flight not found.")
                return redirect(url_for("dashboard.dashboard", tab="staff-operator"))

            conn.commit()
            flash("Flight status updated.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[staff_update_flight_status][error] {e}")
        flash("Failed to update status.")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("dashboard.dashboard", tab="staff-operator"))
