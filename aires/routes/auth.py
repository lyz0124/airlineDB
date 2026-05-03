from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

import pymysql

from ..db import with_cursor
from ..utils import split_name, verify_password
from ..services.common import get_airline_list

bp = Blueprint("auth", __name__)


@bp.route("/")
def home():
    if "user_role" in session:
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login_page"))


@bp.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        airline_list = []
        try:
            with with_cursor() as cur:
                airline_list = get_airline_list(cur)
        except Exception as e:
            print(f"[register][airline_list_error] {e}")
        return render_template("register.html", airline_list=airline_list)

    role = request.form.get("role", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()

    if role not in {"customer", "booking_agent", "airline_staff"}:
        flash("Invalid role.", "danger")
        return redirect(url_for("auth.register_page"))
    if not username or not password or not name:
        flash("Role, username, password and name are required.", "warning")
        return redirect(url_for("auth.register_page"))

    password_hash = generate_password_hash(password)
    try:
        with with_cursor() as cur:
            if role == "customer":
                passport_number = request.form.get("passport_number", "").strip()
                passport_expiration_date = request.form.get("passport_expiration_date", "").strip()
                date_of_birth = request.form.get("date_of_birth", "").strip()
                building_name = request.form.get("building_name", "").strip()
                street = request.form.get("street", "").strip()
                city = request.form.get("city", "").strip()
                state = request.form.get("state", "").strip()
                phone_number = request.form.get("phone_number", "").strip()
                passport_country = request.form.get("passport_country", "").strip()

                if not passport_number or not passport_expiration_date or not date_of_birth:
                    flash(
                        "Customer requires passport number, passport expiration date and date of birth.",
                        "warning",
                    )
                    return redirect(url_for("auth.register_page"))

                cur.execute("SELECT 1 FROM customer WHERE email = %s", (username,))
                if cur.fetchone():
                    flash("Customer email already exists.", "danger")
                    return redirect(url_for("auth.register_page"))

                cur.execute(
                    """
                    INSERT INTO customer
                    (email, name, password, building_number, street, city, state, phone_number,
                     passport_number, passport_expiration, passport_country, date_of_birth)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        username,
                        name,
                        password_hash,
                        building_name,
                        street,
                        city,
                        state,
                        phone_number,
                        passport_number,
                        passport_expiration_date,
                        passport_country,
                        date_of_birth,
                    ),
                )

            elif role == "booking_agent":
                cur.execute("SELECT 1 FROM booking_agent WHERE email = %s", (username,))
                if cur.fetchone():
                    flash("Booking agent email already exists.", "danger")
                    return redirect(url_for("auth.register_page"))

                cur.execute(
                    """
                    INSERT INTO booking_agent (email, password)
                    VALUES (%s, %s)
                    """,
                    (username, password_hash),
                )

            else:
                airline_name = request.form.get("airline_name", "").strip()
                staff_dob = request.form.get("staff_dob", "").strip()
                if not airline_name or not staff_dob:
                    flash("Airline name and date of birth are required for staff.", "warning")
                    return redirect(url_for("auth.register_page"))

                first_name, last_name = split_name(name)

                cur.execute("SELECT 1 FROM airline_staff WHERE username = %s", (username,))
                if cur.fetchone():
                    flash("Staff username already exists.", "danger")
                    return redirect(url_for("auth.register_page"))

                cur.execute(
                    """
                    INSERT INTO airline_staff
                    (username, password, first_name, last_name, date_of_birth, airline_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (username, password_hash, first_name, last_name, staff_dob or None, airline_name),
                )

            cur.connection.commit()
            flash("Registration successful.", "success")
            return redirect(url_for("auth.register_page"))

    except pymysql.MySQLError as e:
        print(f"[register][db_error] {e}")
        flash("Registration failed. Please try again.", "danger")
        return redirect(url_for("auth.register_page"))
    except Exception as e:
        print(f"[register][unexpected_error] {e}")
        flash("Registration failed. Please try again.", "danger")
        return redirect(url_for("auth.register_page"))


@bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method != "POST":
        from .public import render_public_page

        return render_public_page()

    role = request.form.get("role", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if role not in {"customer", "booking_agent", "airline_staff"}:
        flash("Invalid role.", "danger")
        return redirect(url_for("auth.login_page"))
    if not username or not password:
        flash("Role, username and password are required.", "warning")
        return redirect(url_for("auth.login_page"))

    try:
        with with_cursor() as cur:
            user_row = None
            display_name = username

            if role == "customer":
                cur.execute("SELECT email, name, password FROM customer WHERE email = %s", (username,))
                user_row = cur.fetchone()
                if user_row:
                    display_name = user_row["name"]
            elif role == "booking_agent":
                cur.execute("SELECT email, password FROM booking_agent WHERE email = %s", (username,))
                user_row = cur.fetchone()
            else:
                cur.execute(
                    """
                    SELECT username, password, first_name, last_name
                    FROM airline_staff
                    WHERE username = %s
                    """,
                    (username,),
                )
                user_row = cur.fetchone()
                if user_row:
                    first_name = (user_row.get("first_name") or "").strip()
                    last_name = (user_row.get("last_name") or "").strip()
                    name_parts = []
                    if first_name and first_name.upper() != "N/A":
                        name_parts.append(first_name)
                    if last_name and last_name.upper() != "N/A":
                        name_parts.append(last_name)
                    display_name = " ".join(name_parts) or username

            if not user_row or not verify_password(user_row["password"], password):
                flash("Invalid username or password.", "danger")
                return redirect(url_for("auth.login_page"))

            session["user_role"] = role
            session["user_id"] = username
            session["user_name"] = display_name

            flash("Login successful.", "success")
            return redirect(url_for("dashboard.dashboard"))

    except pymysql.MySQLError as e:
        print(f"[login][db_error] {e}")
        flash("Login failed. Please try again.", "danger")
        return redirect(url_for("auth.login_page"))
    except Exception as e:
        print(f"[login][unexpected_error] {e}")
        flash("Login failed. Please try again.", "danger")
        return redirect(url_for("auth.login_page"))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("auth.login_page"))
