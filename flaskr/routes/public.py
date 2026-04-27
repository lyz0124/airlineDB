from flask import Blueprint, render_template, request

import pymysql

from ..db import get_conn
from ..services.public_service import (
    get_public_flight_status,
    search_public_flights,
    validate_public_search,
)

bp = Blueprint("public", __name__, url_prefix="/public")


def render_public_page(**context):
    return render_template(
        "login.html",
        search_form=context.get("search_form", {}),
        search_results=context.get("search_results", []),
        search_submitted=context.get("search_submitted", False),
        search_message=context.get("search_message"),
        search_message_type=context.get("search_message_type", "info"),
        status_form=context.get("status_form", {}),
        status_result=context.get("status_result"),
        status_submitted=context.get("status_submitted", False),
        status_message=context.get("status_message"),
        status_message_type=context.get("status_message_type", "info"),
    )


@bp.route("/search-flights", methods=["POST"])
def public_search_flights():
    search_form = {
        "departure_airport": request.form.get("departure_airport", "").strip(),
        "arrival_airport": request.form.get("arrival_airport", "").strip(),
        "departure_city": request.form.get("departure_city", "").strip(),
        "arrival_city": request.form.get("arrival_city", "").strip(),
        "departure_date": request.form.get("departure_date", "").strip(),
    }

    error_message = validate_public_search(search_form)
    if error_message:
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message=error_message,
            search_message_type="warning",
        )

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            rows = search_public_flights(cur, search_form)

        return render_public_page(
            search_form=search_form,
            search_results=rows,
            search_submitted=True,
            search_message=None if rows else "No upcoming flights match your conditions.",
            search_message_type="info",
        )
    except pymysql.MySQLError as e:
        print(f"[public_search_flights][db_error] {e}")
    except Exception as e:
        print(f"[public_search_flights][unexpected_error] {e}")
    finally:
        if conn:
            conn.close()

    return render_public_page(
        search_form=search_form,
        search_submitted=True,
        search_message="Flight search failed. Please try again.",
        search_message_type="danger",
    )


@bp.route("/flight-status", methods=["POST"])
def public_flight_status():
    status_form = {
        "airline_name": request.form.get("airline_name", "").strip(),
        "flight_num": request.form.get("flight_num", "").strip(),
    }

    if not status_form["airline_name"] or not status_form["flight_num"]:
        return render_public_page(
            status_form=status_form,
            status_submitted=True,
            status_message="Airline and flight number are required.",
            status_message_type="warning",
        )
    if not status_form["flight_num"].isdigit():
        return render_public_page(
            status_form=status_form,
            status_submitted=True,
            status_message="Flight number must be a positive integer.",
            status_message_type="warning",
        )

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            row = get_public_flight_status(cur, status_form["airline_name"], int(status_form["flight_num"]))

        return render_public_page(
            status_form=status_form,
            status_result=row,
            status_submitted=True,
            status_message=None if row else "No in-progress flight found for this airline and flight number.",
            status_message_type="info",
        )
    except pymysql.MySQLError as e:
        print(f"[public_flight_status][db_error] {e}")
    except Exception as e:
        print(f"[public_flight_status][unexpected_error] {e}")
    finally:
        if conn:
            conn.close()

    return render_public_page(
        status_form=status_form,
        status_submitted=True,
        status_message="Status lookup failed. Please try again.",
        status_message_type="danger",
    )
