from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from datetime import datetime, timedelta, date

airline=Flask(__name__)
airline.secret_key="dev-secret-key"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "air_reservation",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def split_name(full_name):
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def verify_password(stored_password, input_password):
    # Backward compatibility for old plaintext data in PRJ2 seed tables.
    return check_password_hash(stored_password, input_password) or stored_password == input_password


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
        status_message_type=context.get("status_message_type", "info")
    )


def parse_date(date_string):
    if not date_string:
        return None
    return datetime.strptime(date_string, "%Y-%m-%d").date()


def parse_int(int_string):
    if not int_string:
        return None
    return int(int_string)


def require_login(role=None):
    if "user_role" not in session:
        flash("Please login first.")
        return None
    if role and session.get("user_role") != role:
        flash("Permission denied.")
        return None
    return session.get("user_id")


def get_staff_profile(cur, username):
    cur.execute(
        """
        SELECT username, airline_name, role, first_name, last_name
        FROM Airline_Staff
        WHERE username = %s
        """,
        (username,)
    )
    return cur.fetchone()


def staff_has_permission(staff_role, required):
    normalized = (staff_role or "").lower()
    if normalized == "both":
        return True
    return normalized == required


def get_next_ticket_id(cur):
    cur.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM Ticket")
    row = cur.fetchone()
    return row["next_id"]


def get_flight_capacity_and_price(cur, airline_name, flight_num):
    cur.execute(
        """
        SELECT
            f.airline_name,
            f.flight_num,
            f.departure_time,
            f.arrival_time,
            f.price,
            f.status,
            ap.seat_capacity,
            COUNT(t.ticket_id) AS sold_tickets
        FROM Flight f
        JOIN Airplane ap
          ON ap.airline_name = f.airline_name
         AND ap.airplane_id = f.airplane_id
        LEFT JOIN Ticket t
          ON t.airline_name = f.airline_name
         AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s
          AND f.flight_num = %s
        GROUP BY
            f.airline_name, f.flight_num, f.departure_time, f.arrival_time,
            f.price, f.status, ap.seat_capacity
        """,
        (airline_name, flight_num)
    )
    return cur.fetchone()


def is_agent_authorized(cur, agent_email, airline_name):
    cur.execute(
        """
        SELECT 1
        FROM agent_airline_authorization
        WHERE agent_email = %s
          AND airline_name = %s
        """,
        (agent_email, airline_name)
    )
    return cur.fetchone() is not None


def create_purchase(cur, customer_email, airline_name, flight_num, booking_agent_email=None):
    flight = get_flight_capacity_and_price(cur, airline_name, flight_num)
    if not flight:
        return False, "Flight does not exist."

    if flight["departure_time"] <= datetime.now():
        return False, "Only future flights can be purchased."

    if flight["status"] != "upcoming":
        return False, "Only upcoming flights can be purchased."

    if flight["sold_tickets"] >= flight["seat_capacity"]:
        return False, "This flight is sold out."

    cur.execute("SELECT 1 FROM Customer WHERE email = %s", (customer_email,))
    if not cur.fetchone():
        return False, "Customer does not exist."

    # Pricing is enforced server-side by always reading current price from DB.
    if float(flight["price"]) <= 0:
        return False, "Invalid flight pricing configuration."

    ticket_id = get_next_ticket_id(cur)
    cur.execute(
        """
        INSERT INTO Ticket (ticket_id, airline_name, flight_num)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, airline_name, flight_num)
    )
    cur.execute(
        """
        INSERT INTO Purchases (ticket_id, customer_email, booking_agent_email, purchase_date)
        VALUES (%s, %s, %s, CURDATE())
        """,
        (ticket_id, customer_email, booking_agent_email)
    )
    return True, f"Ticket purchased successfully. Ticket ID: {ticket_id}"


def month_labels_between(start_date, end_date):
    labels = []
    cursor = date(start_date.year, start_date.month, 1)
    limit = date(end_date.year, end_date.month, 1)
    while cursor <= limit:
        labels.append(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return labels


def fill_monthly_series(rows, labels, value_key):
    mapping = {row["month"]: float(row[value_key]) for row in rows}
    return [mapping.get(label, 0.0) for label in labels]

@airline.route("/")
def home():
    if "user_role" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@airline.route("/register", methods=["GET","POST"])
def register_page():
    if request.method == "GET":
        return render_template("register.html")

    role = request.form.get("role", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()

    if role not in {"customer", "booking_agent", "airline_staff"}:
        flash("Invalid role.")
        return redirect(url_for("register_page"))
    if not username or not password or not name:
        flash("Role, username, password and name are required.")
        return redirect(url_for("register_page"))

    password_hash = generate_password_hash(password)
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
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
                    flash("Customer requires passport number, passport expiration date and date of birth.")
                    return redirect(url_for("register_page"))

                cur.execute("SELECT 1 FROM Customer WHERE email = %s", (username,))
                if cur.fetchone():
                    flash("Customer email already exists.")
                    return redirect(url_for("register_page"))

                cur.execute(
                    """
                    INSERT INTO Customer
                    (email, name, password, building_number, street, city, state, phone_number,
                     passport_number, passport_expiration, passport_country, date_of_birth)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        username, name, password_hash, building_name, street, city, state, phone_number,
                        passport_number, passport_expiration_date, passport_country, date_of_birth
                    )
                )

            elif role == "booking_agent":
                cur.execute("SELECT 1 FROM booking_agent WHERE email = %s", (username,))
                if cur.fetchone():
                    flash("Booking agent email already exists.")
                    return redirect(url_for("register_page"))

                cur.execute(
                    """
                    INSERT INTO booking_agent (email, password)
                    VALUES (%s, %s)
                    """,
                    (username, password_hash)
                )

            else:
                airline_name = request.form.get("airline_name", "").strip()
                staff_dob = request.form.get("staff_dob", "").strip()
                if not airline_name or not staff_dob:
                    flash("Airline name and date of birth are required for staff.")
                    return redirect(url_for("register_page"))

                first_name, last_name = split_name(name)

                cur.execute("SELECT 1 FROM Airline_Staff WHERE username = %s", (username,))
                if cur.fetchone():
                    flash("Staff username already exists.")
                    return redirect(url_for("register_page"))

                cur.execute(
                    """
                    INSERT INTO Airline_Staff
                    (username, password, first_name, last_name, date_of_birth, airline_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (username, password_hash, first_name, last_name, staff_dob or None, airline_name)
                )

            conn.commit()
            flash("Registration successful.")
            return redirect(url_for("register_page"))

    except pymysql.MySQLError as e:
        if conn:
            conn.rollback()
        print(f"[register][db_error] {e}")
        flash("Registration failed. Please try again.")
        return redirect(url_for("register_page"))
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[register][unexpected_error] {e}")
        flash("Registration failed. Please try again.")
        return redirect(url_for("register_page"))
    finally:
        if conn:
            conn.close()


@airline.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method != "POST":
        return render_public_page()

    role = request.form.get("role", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if role not in {"customer", "booking_agent", "airline_staff"}:
        flash("Invalid role.")
        return redirect(url_for("login_page"))
    if not username or not password:
        flash("Role, username and password are required.")
        return redirect(url_for("login_page"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            user_row = None
            display_name = username

            if role == "customer":
                cur.execute(
                    "SELECT email, name, password FROM Customer WHERE email = %s",
                    (username,)
                )
                user_row = cur.fetchone()
                if user_row:
                    display_name = user_row["name"]
            elif role == "booking_agent":
                cur.execute(
                    "SELECT email, password FROM booking_agent WHERE email = %s",
                    (username,)
                )
                user_row = cur.fetchone()
            else:
                cur.execute(
                    """
                    SELECT username, password, first_name, last_name
                    FROM Airline_Staff
                    WHERE username = %s
                    """,
                    (username,)
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

            if not user_row:
                flash("Invalid username or password.")
                return redirect(url_for("login_page"))

            if not verify_password(user_row["password"], password):
                flash("Invalid username or password.")
                return redirect(url_for("login_page"))

            session["user_role"] = role
            session["user_id"] = username
            session["user_name"] = display_name

            flash("Login successful.")
            return redirect(url_for("dashboard"))

    except pymysql.MySQLError as e:
        print(f"[login][db_error] {e}")
        flash("Login failed. Please try again.")
        return redirect(url_for("login_page"))
    except Exception as e:
        print(f"[login][unexpected_error] {e}")
        flash("Login failed. Please try again.")
        return redirect(url_for("login_page"))
    finally:
        if conn:
            conn.close()


@airline.route("/public/search-flights", methods=["POST"])
def public_search_flights():
    search_form = {
        "departure_airport": request.form.get("departure_airport", "").strip(),
        "arrival_airport": request.form.get("arrival_airport", "").strip(),
        "departure_city": request.form.get("departure_city", "").strip(),
        "arrival_city": request.form.get("arrival_city", "").strip(),
        "departure_date": request.form.get("departure_date", "").strip(),
    }

    if not any(search_form.values()):
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message="Please provide at least one search condition.",
            search_message_type="warning"
        )

    if not (search_form["departure_airport"] or search_form["departure_city"]):
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message="Please provide either a departure airport code or departure city.",
            search_message_type="warning"
        )

    if not (search_form["arrival_airport"] or search_form["arrival_city"]):
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message="Please provide either an arrival airport code or arrival city.",
            search_message_type="warning"
        )

    departure_date = search_form["departure_date"]
    if departure_date:
        try:
            datetime.strptime(departure_date, "%Y-%m-%d")
        except ValueError:
            return render_public_page(
                search_form=search_form,
                search_submitted=True,
                search_message="Invalid date format. Please use YYYY-MM-DD.",
                search_message_type="warning"
            )

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            sql = """
                SELECT
                    f.airline_name,
                    f.flight_num,
                    f.departure_airport,
                    dep.airport_city AS departure_city,
                    f.departure_time,
                    f.arrival_airport,
                    arr.airport_city AS arrival_city,
                    f.arrival_time,
                    f.price,
                    f.status
                FROM Flight f
                JOIN Airport dep ON dep.airport_name = f.departure_airport
                JOIN Airport arr ON arr.airport_name = f.arrival_airport
                WHERE f.departure_time >= NOW()
            """
            params = []

            if search_form["departure_airport"]:
                sql += " AND f.departure_airport = %s"
                params.append(search_form["departure_airport"])
            elif search_form["departure_city"]:
                sql += " AND dep.airport_city = %s"
                params.append(search_form["departure_city"])

            if search_form["arrival_airport"]:
                sql += " AND f.arrival_airport = %s"
                params.append(search_form["arrival_airport"])
            elif search_form["arrival_city"]:
                sql += " AND arr.airport_city = %s"
                params.append(search_form["arrival_city"])
            if departure_date:
                sql += " AND DATE(f.departure_time) = %s"
                params.append(departure_date)

            sql += " ORDER BY f.departure_time ASC LIMIT 200"
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

        message = None
        message_type = "info"
        if not rows:
            message = "No upcoming flights match your conditions."
        return render_public_page(
            search_form=search_form,
            search_results=rows,
            search_submitted=True,
            search_message=message,
            search_message_type=message_type
        )
    except pymysql.MySQLError as e:
        print(f"[public_search_flights][db_error] {e}")
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message="Flight search failed. Please try again.",
            search_message_type="danger"
        )
    except Exception as e:
        print(f"[public_search_flights][unexpected_error] {e}")
        return render_public_page(
            search_form=search_form,
            search_submitted=True,
            search_message="Flight search failed. Please try again.",
            search_message_type="danger"
        )
    finally:
        if conn:
            conn.close()


@airline.route("/public/flight-status", methods=["POST"])
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
            status_message_type="warning"
        )
    if not status_form["flight_num"].isdigit():
        return render_public_page(
            status_form=status_form,
            status_submitted=True,
            status_message="Flight number must be a positive integer.",
            status_message_type="warning"
        )

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    airline_name,
                    flight_num,
                    status,
                    departure_airport,
                    departure_time,
                    arrival_airport,
                    arrival_time
                FROM Flight
                WHERE airline_name = %s
                  AND flight_num = %s
                  AND status = 'in-progress'
                """,
                (status_form["airline_name"], int(status_form["flight_num"]))
            )
            row = cur.fetchone()

        message = None
        message_type = "info"
        if not row:
            message = "No in-progress flight found for this airline and flight number."
        return render_public_page(
            status_form=status_form,
            status_result=row,
            status_submitted=True,
            status_message=message,
            status_message_type=message_type
        )
    except pymysql.MySQLError as e:
        print(f"[public_flight_status][db_error] {e}")
        return render_public_page(
            status_form=status_form,
            status_submitted=True,
            status_message="Status lookup failed. Please try again.",
            status_message_type="danger"
        )
    except Exception as e:
        print(f"[public_flight_status][unexpected_error] {e}")
        return render_public_page(
            status_form=status_form,
            status_submitted=True,
            status_message="Status lookup failed. Please try again.",
            status_message_type="danger"
        )
    finally:
        if conn:
            conn.close()


def load_customer_dashboard(cur, customer_email, args):
    purchased_filters = {
        "start_date": args.get("customer_start_date", "").strip(),
        "end_date": args.get("customer_end_date", "").strip(),
        "origin": args.get("customer_origin", "").strip(),
        "destination": args.get("customer_destination", "").strip(),
    }

    purchased_sql = """
        SELECT
            p.purchase_date,
            t.ticket_id,
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            f.arrival_airport,
            f.departure_time,
            f.arrival_time,
            f.status,
            f.price
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.customer_email = %s
    """
    purchased_params = [customer_email]

    if purchased_filters["start_date"]:
        purchased_sql += " AND DATE(f.departure_time) >= %s"
        purchased_params.append(purchased_filters["start_date"])
    if purchased_filters["end_date"]:
        purchased_sql += " AND DATE(f.departure_time) <= %s"
        purchased_params.append(purchased_filters["end_date"])
    if purchased_filters["origin"]:
        purchased_sql += " AND f.departure_airport = %s"
        purchased_params.append(purchased_filters["origin"])
    if purchased_filters["destination"]:
        purchased_sql += " AND f.arrival_airport = %s"
        purchased_params.append(purchased_filters["destination"])
    if not purchased_filters["start_date"] and not purchased_filters["end_date"]:
        purchased_sql += " AND f.departure_time >= NOW()"

    purchased_sql += " ORDER BY f.departure_time ASC"
    cur.execute(purchased_sql, tuple(purchased_params))
    purchased_flights = cur.fetchall()

    search_filters = {
        "departure_airport": args.get("search_departure_airport", "").strip(),
        "arrival_airport": args.get("search_arrival_airport", "").strip(),
        "departure_city": args.get("search_departure_city", "").strip(),
        "arrival_city": args.get("search_arrival_city", "").strip(),
        "departure_date": args.get("search_departure_date", "").strip(),
    }

    search_sql = """
        SELECT
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            dep.airport_city AS departure_city,
            f.departure_time,
            f.arrival_airport,
            arr.airport_city AS arrival_city,
            f.arrival_time,
            f.price,
            f.status,
            ap.seat_capacity,
            COUNT(t.ticket_id) AS sold_tickets
        FROM Flight f
        JOIN Airport dep ON dep.airport_name = f.departure_airport
        JOIN Airport arr ON arr.airport_name = f.arrival_airport
        JOIN Airplane ap ON ap.airline_name = f.airline_name AND ap.airplane_id = f.airplane_id
        LEFT JOIN Ticket t ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.departure_time >= NOW()
          AND f.status = 'upcoming'
    """
    search_params = []

    if search_filters["departure_airport"]:
        search_sql += " AND f.departure_airport = %s"
        search_params.append(search_filters["departure_airport"])
    if search_filters["arrival_airport"]:
        search_sql += " AND f.arrival_airport = %s"
        search_params.append(search_filters["arrival_airport"])
    if search_filters["departure_city"]:
        search_sql += " AND dep.airport_city = %s"
        search_params.append(search_filters["departure_city"])
    if search_filters["arrival_city"]:
        search_sql += " AND arr.airport_city = %s"
        search_params.append(search_filters["arrival_city"])
    if search_filters["departure_date"]:
        search_sql += " AND DATE(f.departure_time) = %s"
        search_params.append(search_filters["departure_date"])

    search_sql += """
        GROUP BY
            f.airline_name, f.flight_num, f.departure_airport, dep.airport_city,
            f.departure_time, f.arrival_airport, arr.airport_city, f.arrival_time,
            f.price, f.status, ap.seat_capacity
        ORDER BY f.departure_time ASC
        LIMIT 200
    """
    cur.execute(search_sql, tuple(search_params))
    search_results = cur.fetchall()
    for row in search_results:
        row["remaining_seats"] = int(row["seat_capacity"]) - int(row["sold_tickets"])

    cur.execute(
        """
        SELECT COALESCE(SUM(f.price), 0) AS total_spending_12m
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.customer_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        """,
        (customer_email,)
    )
    total_12m = float(cur.fetchone()["total_spending_12m"])

    cur.execute(
        """
        SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month, COALESCE(SUM(f.price), 0) AS amount
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.customer_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
        ORDER BY month
        """,
        (customer_email,)
    )
    last_6_rows = cur.fetchall()
    six_month_start = (date.today().replace(day=1) - timedelta(days=150)).replace(day=1)
    six_month_labels = month_labels_between(six_month_start, date.today())
    last_6_amounts = fill_monthly_series(last_6_rows, six_month_labels, "amount")

    custom_start = args.get("spending_start_date", "").strip()
    custom_end = args.get("spending_end_date", "").strip()
    custom_total = 0.0
    custom_labels = []
    custom_amounts = []

    if custom_start and custom_end:
        cur.execute(
            """
            SELECT COALESCE(SUM(f.price), 0) AS total
            FROM Purchases p
            JOIN Ticket t ON t.ticket_id = p.ticket_id
            JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND p.purchase_date BETWEEN %s AND %s
            """,
            (customer_email, custom_start, custom_end)
        )
        custom_total = float(cur.fetchone()["total"])

        cur.execute(
            """
            SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month, COALESCE(SUM(f.price), 0) AS amount
            FROM Purchases p
            JOIN Ticket t ON t.ticket_id = p.ticket_id
            JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND p.purchase_date BETWEEN %s AND %s
            GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
            ORDER BY month
            """,
            (customer_email, custom_start, custom_end)
        )
        custom_rows = cur.fetchall()
        try:
            parsed_custom_start = parse_date(custom_start)
            parsed_custom_end = parse_date(custom_end)
            if parsed_custom_start <= parsed_custom_end:
                custom_labels = month_labels_between(parsed_custom_start, parsed_custom_end)
                custom_amounts = fill_monthly_series(custom_rows, custom_labels, "amount")
        except ValueError:
            custom_labels = []
            custom_amounts = []

    return {
        "purchased_filters": purchased_filters,
        "purchased_flights": purchased_flights,
        "search_filters": search_filters,
        "search_results": search_results,
        "spending": {
            "total_12m": total_12m,
            "six_month_labels": six_month_labels,
            "six_month_amounts": last_6_amounts,
            "custom_start": custom_start,
            "custom_end": custom_end,
            "custom_total": custom_total,
            "custom_labels": custom_labels,
            "custom_amounts": custom_amounts,
        }
    }


def load_agent_dashboard(cur, agent_email, args):
    flight_filters = {
        "start_date": args.get("agent_start_date", "").strip(),
        "end_date": args.get("agent_end_date", "").strip(),
        "origin": args.get("agent_origin", "").strip(),
        "destination": args.get("agent_destination", "").strip(),
    }

    purchased_sql = """
        SELECT
            p.purchase_date,
            p.customer_email,
            t.ticket_id,
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            f.arrival_airport,
            f.departure_time,
            f.arrival_time,
            f.price
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
    """
    purchased_params = [agent_email]
    if flight_filters["start_date"]:
        purchased_sql += " AND DATE(f.departure_time) >= %s"
        purchased_params.append(flight_filters["start_date"])
    if flight_filters["end_date"]:
        purchased_sql += " AND DATE(f.departure_time) <= %s"
        purchased_params.append(flight_filters["end_date"])
    if flight_filters["origin"]:
        purchased_sql += " AND f.departure_airport = %s"
        purchased_params.append(flight_filters["origin"])
    if flight_filters["destination"]:
        purchased_sql += " AND f.arrival_airport = %s"
        purchased_params.append(flight_filters["destination"])
    purchased_sql += " ORDER BY p.purchase_date DESC"
    cur.execute(purchased_sql, tuple(purchased_params))
    purchased_rows = cur.fetchall()

    cur.execute(
        """
        SELECT airline_name
        FROM agent_airline_authorization
        WHERE agent_email = %s
        ORDER BY airline_name
        """,
        (agent_email,)
    )
    authorized_airlines = [row["airline_name"] for row in cur.fetchall()]

    search_filters = {
        "airline_name": args.get("agent_search_airline", "").strip(),
        "departure_date": args.get("agent_search_date", "").strip(),
    }

    search_sql = """
        SELECT
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            f.arrival_airport,
            f.departure_time,
            f.arrival_time,
            f.price,
            ap.seat_capacity,
            COUNT(t.ticket_id) AS sold_tickets
        FROM Flight f
        JOIN agent_airline_authorization aa ON aa.airline_name = f.airline_name
        JOIN Airplane ap ON ap.airline_name = f.airline_name AND ap.airplane_id = f.airplane_id
        LEFT JOIN Ticket t ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE aa.agent_email = %s
          AND f.departure_time >= NOW()
          AND f.status = 'upcoming'
    """
    search_params = [agent_email]
    if search_filters["airline_name"]:
        search_sql += " AND f.airline_name = %s"
        search_params.append(search_filters["airline_name"])
    if search_filters["departure_date"]:
        search_sql += " AND DATE(f.departure_time) = %s"
        search_params.append(search_filters["departure_date"])
    search_sql += """
        GROUP BY
            f.airline_name, f.flight_num, f.departure_airport, f.arrival_airport,
            f.departure_time, f.arrival_time, f.price, ap.seat_capacity
        ORDER BY f.departure_time ASC
    """
    cur.execute(search_sql, tuple(search_params))
    sale_flights = cur.fetchall()
    for row in sale_flights:
        row["remaining_seats"] = int(row["seat_capacity"]) - int(row["sold_tickets"])

    cur.execute(
        """
        SELECT
            COALESCE(SUM(f.price * 0.1), 0) AS commission_total,
            COALESCE(AVG(f.price * 0.1), 0) AS avg_commission,
            COUNT(*) AS tickets_sold
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """,
        (agent_email,)
    )
    commission_stats = cur.fetchone()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COUNT(*) AS ticket_count
        FROM Purchases p
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 5
        """,
        (agent_email,)
    )
    top_tickets = cur.fetchall()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COALESCE(SUM(f.price * 0.1), 0) AS commission
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY commission DESC
        LIMIT 5
        """,
        (agent_email,)
    )
    top_commission = cur.fetchall()

    return {
        "flight_filters": flight_filters,
        "purchased_rows": purchased_rows,
        "authorized_airlines": authorized_airlines,
        "search_filters": search_filters,
        "sale_flights": sale_flights,
        "commission_stats": commission_stats,
        "top_tickets_labels": [row["customer_email"] for row in top_tickets],
        "top_tickets_values": [int(row["ticket_count"]) for row in top_tickets],
        "top_commission_labels": [row["customer_email"] for row in top_commission],
        "top_commission_values": [float(row["commission"]) for row in top_commission],
    }


def load_staff_dashboard(cur, staff_user, args):
    profile = get_staff_profile(cur, staff_user)
    if not profile:
        return None

    airline_name = profile["airline_name"]
    staff_role = (profile.get("role") or "admin").lower()
    default_start = date.today()
    default_end = date.today() + timedelta(days=30)

    flight_filters = {
        "start_date": args.get("staff_start_date", default_start.strftime("%Y-%m-%d")).strip(),
        "end_date": args.get("staff_end_date", default_end.strftime("%Y-%m-%d")).strip(),
        "origin": args.get("staff_origin", "").strip(),
        "destination": args.get("staff_destination", "").strip(),
    }

    flights_sql = """
        SELECT
            f.airline_name,
            f.flight_num,
            f.departure_airport,
            f.arrival_airport,
            f.departure_time,
            f.arrival_time,
            f.status,
            f.price
        FROM Flight f
        WHERE f.airline_name = %s
          AND DATE(f.departure_time) BETWEEN %s AND %s
    """
    flights_params = [airline_name, flight_filters["start_date"], flight_filters["end_date"]]
    if flight_filters["origin"]:
        flights_sql += " AND f.departure_airport = %s"
        flights_params.append(flight_filters["origin"])
    if flight_filters["destination"]:
        flights_sql += " AND f.arrival_airport = %s"
        flights_params.append(flight_filters["destination"])
    flights_sql += " ORDER BY f.departure_time ASC"
    cur.execute(flights_sql, tuple(flights_params))
    flights = cur.fetchall()

    passenger_query_airline = args.get("passenger_airline_name", airline_name).strip()
    passenger_query_flight = args.get("passenger_flight_num", "").strip()
    passengers = []
    if passenger_query_flight:
        cur.execute(
            """
            SELECT
                c.email,
                c.name,
                p.purchase_date
            FROM Purchases p
            JOIN Ticket t ON t.ticket_id = p.ticket_id
            JOIN Customer c ON c.email = p.customer_email
            WHERE t.airline_name = %s
              AND t.flight_num = %s
            ORDER BY p.purchase_date DESC
            """,
            (passenger_query_airline, passenger_query_flight)
        )
        passengers = cur.fetchall()

    customer_email = args.get("staff_customer_email", "").strip()
    customer_flights = []
    if customer_email:
        cur.execute(
            """
            SELECT
                p.purchase_date,
                f.airline_name,
                f.flight_num,
                f.departure_airport,
                f.arrival_airport,
                f.departure_time,
                f.arrival_time,
                f.status
            FROM Purchases p
            JOIN Ticket t ON t.ticket_id = p.ticket_id
            JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND f.airline_name = %s
            ORDER BY f.departure_time DESC
            """,
            (customer_email, airline_name)
        )
        customer_flights = cur.fetchall()

    selected_year = args.get("staff_year", str(date.today().year)).strip()
    selected_month = args.get("staff_month", str(date.today().month)).strip()

    cur.execute(
        """
        SELECT
            p.booking_agent_email AS agent_email,
            COUNT(*) AS ticket_count,
            COALESCE(SUM(f.price * 0.1), 0) AS commission_total
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.booking_agent_email IS NOT NULL
          AND YEAR(p.purchase_date) = %s
          AND MONTH(p.purchase_date) = %s
        GROUP BY p.booking_agent_email
        ORDER BY ticket_count DESC, commission_total DESC
        LIMIT 5
        """,
        (airline_name, selected_year, selected_month)
    )
    top_agents = cur.fetchall()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COUNT(*) AS ticket_count
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 1
        """,
        (airline_name,)
    )
    most_frequent_customer = cur.fetchone()

    cur.execute(
        """
        SELECT
            DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month,
            COUNT(*) AS tickets
        FROM Purchases p
        JOIN Ticket t ON t.ticket_id = p.ticket_id
        JOIN Flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
        ORDER BY month
        """,
        (airline_name,)
    )
    tickets_by_month_rows = cur.fetchall()
    yearly_labels = month_labels_between((date.today() - timedelta(days=365)).replace(day=1), date.today())
    tickets_by_month_values = fill_monthly_series(tickets_by_month_rows, yearly_labels, "tickets")

    cur.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'delayed' THEN 1 ELSE 0 END) AS delayed_count,
            SUM(CASE WHEN status <> 'delayed' THEN 1 ELSE 0 END) AS on_time_count
        FROM Flight
        WHERE airline_name = %s
          AND departure_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        """,
        (airline_name,)
    )
    delay_stats = cur.fetchone()

    cur.execute(
        """
        SELECT
            f.arrival_airport,
            a.airport_city,
            COUNT(*) AS flight_count
        FROM Flight f
        JOIN Airport a ON a.airport_name = f.arrival_airport
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
        GROUP BY f.arrival_airport, a.airport_city
        ORDER BY flight_count DESC
        LIMIT 5
        """,
        (airline_name,)
    )
    top_destinations_3m = cur.fetchall()

    cur.execute(
        """
        SELECT
            f.arrival_airport,
            a.airport_city,
            COUNT(*) AS flight_count
        FROM Flight f
        JOIN Airport a ON a.airport_name = f.arrival_airport
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY f.arrival_airport, a.airport_city
        ORDER BY flight_count DESC
        LIMIT 5
        """,
        (airline_name,)
    )
    top_destinations_1y = cur.fetchall()

    return {
        "profile": profile,
        "staff_role": staff_role,
        "airline_name": airline_name,
        "flight_filters": flight_filters,
        "flights": flights,
        "passenger_query_airline": passenger_query_airline,
        "passenger_query_flight": passenger_query_flight,
        "passengers": passengers,
        "staff_customer_email": customer_email,
        "customer_flights": customer_flights,
        "selected_year": selected_year,
        "selected_month": selected_month,
        "top_agents": top_agents,
        "most_frequent_customer": most_frequent_customer,
        "tickets_by_month_labels": yearly_labels,
        "tickets_by_month_values": tickets_by_month_values,
        "delay_stats": delay_stats,
        "top_destinations_3m": top_destinations_3m,
        "top_destinations_1y": top_destinations_1y,
    }


@airline.route("/customer/purchase", methods=["POST"])
def customer_purchase():
    customer_email = require_login("customer")
    if not customer_email:
        return redirect(url_for("login_page"))

    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not airline_name or not flight_num_text.isdigit():
        flash("Invalid airline or flight number.")
        return redirect(url_for("dashboard", tab="customer-search"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            success, message = create_purchase(cur, customer_email, airline_name, int(flight_num_text))
            if success:
                conn.commit()
                flash(message)
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
    return redirect(url_for("dashboard", tab="customer-search"))


@airline.route("/agent/purchase", methods=["POST"])
def agent_purchase():
    agent_email = require_login("booking_agent")
    if not agent_email:
        return redirect(url_for("login_page"))

    customer_email = request.form.get("customer_email", "").strip()
    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    if not customer_email or not airline_name or not flight_num_text.isdigit():
        flash("Customer, airline, and numeric flight number are required.")
        return redirect(url_for("dashboard", tab="agent-search"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if not is_agent_authorized(cur, agent_email, airline_name):
                flash("You are not authorized to sell tickets for this airline.")
                return redirect(url_for("dashboard", tab="agent-search"))

            success, message = create_purchase(
                cur,
                customer_email,
                airline_name,
                int(flight_num_text),
                booking_agent_email=agent_email
            )
            if success:
                conn.commit()
                flash(message)
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
    return redirect(url_for("dashboard", tab="agent-search"))


@airline.route("/staff/add-airport", methods=["POST"])
def staff_add_airport():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

    airport_name = request.form.get("airport_name", "").strip()
    airport_city = request.form.get("airport_city", "").strip()
    if not airport_name or not airport_city:
        flash("Airport name and city are required.")
        return redirect(url_for("dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard", tab="staff-admin"))
            cur.execute("INSERT IGNORE INTO City (city_name) VALUES (%s)", (airport_city,))
            cur.execute(
                """
                INSERT INTO Airport (airport_name, airport_city)
                VALUES (%s, %s)
                """,
                (airport_name, airport_city)
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
    return redirect(url_for("dashboard", tab="staff-admin"))


@airline.route("/staff/add-airplane", methods=["POST"])
def staff_add_airplane():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

    airplane_id_text = request.form.get("airplane_id", "").strip()
    seat_capacity_text = request.form.get("seat_capacity", "").strip()
    if not airplane_id_text.isdigit() or not seat_capacity_text.isdigit():
        flash("Airplane ID and seat capacity must be integers.")
        return redirect(url_for("dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT INTO airplane (airline_name, airplane_id, seat_capacity)
                VALUES (%s, %s, %s)
                """,
                (profile["airline_name"], int(airplane_id_text), int(seat_capacity_text))
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
    return redirect(url_for("dashboard", tab="staff-admin"))


@airline.route("/staff/create-flight", methods=["POST"])
def staff_create_flight():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

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
        return redirect(url_for("dashboard", tab="staff-admin"))

    try:
        dep_dt = datetime.strptime(departure_time, "%Y-%m-%dT%H:%M")
        arr_dt = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M")
        if arr_dt <= dep_dt:
            flash("Arrival time must be later than departure time.")
            return redirect(url_for("dashboard", tab="staff-admin"))
        price_value = float(price_text)
        if price_value <= 0:
            flash("Price must be positive.")
            return redirect(url_for("dashboard", tab="staff-admin"))
    except ValueError:
        flash("Invalid datetime or price format.")
        return redirect(url_for("dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT INTO Flight
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
                    int(airplane_id_text)
                )
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
    return redirect(url_for("dashboard", tab="staff-admin"))


@airline.route("/staff/edit-flight", methods=["POST"])
def staff_edit_flight():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

    airline_name = request.form.get("airline_name", "").strip()
    flight_num = request.form.get("flight_num", "").strip()
    new_flight_num = request.form.get("new_flight_num", "").strip()
    departure_airport = request.form.get("departure_airport", "").strip()
    departure_time_text = request.form.get("departure_time", "").strip()
    arrival_airport = request.form.get("arrival_airport", "").strip()
    arrival_time_text = request.form.get("arrival_time", "").strip()
    price_text = request.form.get("price", "").strip()
    status = request.form.get("status", "").strip()
    airplane_id_text = request.form.get("airplane_id", "").strip()

    if not airline_name or not flight_num:
        flash("Airline and current flight number are required.")
        return redirect(url_for("dashboard", tab="staff-admin"))
    if not flight_num.isdigit():
        flash("Current flight number must be an integer.")
        return redirect(url_for("dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard", tab="staff-admin"))
            if airline_name != profile["airline_name"]:
                flash("You can only edit flights for your airline.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute(
                """
                SELECT airline_name, flight_num, departure_airport, departure_time,
                       arrival_airport, arrival_time, price, status, airplane_id
                FROM Flight
                WHERE airline_name = %s AND flight_num = %s
                """,
                (airline_name, int(flight_num))
            )
            existing = cur.fetchone()
            if not existing:
                flash("Flight not found.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            if new_flight_num and not new_flight_num.isdigit():
                flash("New flight number must be an integer.")
                return redirect(url_for("dashboard", tab="staff-admin"))
            target_flight_num = int(new_flight_num) if new_flight_num else int(existing["flight_num"])
            target_departure_airport = departure_airport or existing["departure_airport"]
            target_arrival_airport = arrival_airport or existing["arrival_airport"]
            target_status = status or existing["status"]
            target_airplane_id = int(airplane_id_text) if airplane_id_text else int(existing["airplane_id"])
            target_price = float(price_text) if price_text else float(existing["price"])
            if target_price <= 0:
                flash("Price must be positive.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            target_departure_time = existing["departure_time"]
            target_arrival_time = existing["arrival_time"]
            if departure_time_text:
                target_departure_time = datetime.strptime(departure_time_text, "%Y-%m-%dT%H:%M")
            if arrival_time_text:
                target_arrival_time = datetime.strptime(arrival_time_text, "%Y-%m-%dT%H:%M")
            if target_arrival_time <= target_departure_time:
                flash("Arrival time must be later than departure time.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            if target_status not in {"upcoming", "in-progress", "delayed"}:
                flash("Invalid status.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute(
                """
                UPDATE Flight
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
                    target_flight_num,
                    target_departure_airport,
                    target_departure_time,
                    target_arrival_airport,
                    target_arrival_time,
                    target_price,
                    target_status,
                    target_airplane_id,
                    airline_name,
                    int(flight_num)
                )
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
    return redirect(url_for("dashboard", tab="staff-admin"))


@airline.route("/staff/authorize-agent", methods=["POST"])
def staff_authorize_agent():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

    agent_email = request.form.get("agent_email", "").strip()
    if not agent_email:
        flash("Agent email is required.")
        return redirect(url_for("dashboard", tab="staff-admin"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "admin"):
                flash("Admin permission required.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute("SELECT 1 FROM booking_agent WHERE email = %s", (agent_email,))
            if not cur.fetchone():
                flash("Booking agent does not exist.")
                return redirect(url_for("dashboard", tab="staff-admin"))

            cur.execute(
                """
                INSERT IGNORE INTO agent_airline_authorization (agent_email, airline_name)
                VALUES (%s, %s)
                """,
                (agent_email, profile["airline_name"])
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
    return redirect(url_for("dashboard", tab="staff-admin"))


@airline.route("/staff/update-flight-status", methods=["POST"])
def staff_update_flight_status():
    staff_user = require_login("airline_staff")
    if not staff_user:
        return redirect(url_for("login_page"))

    airline_name = request.form.get("airline_name", "").strip()
    flight_num_text = request.form.get("flight_num", "").strip()
    status = request.form.get("status", "").strip()
    if not flight_num_text.isdigit() or status not in {"upcoming", "in-progress", "delayed"}:
        flash("Invalid input for status update.")
        return redirect(url_for("dashboard", tab="staff-operator"))

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            profile = get_staff_profile(cur, staff_user)
            if not profile or not staff_has_permission(profile.get("role"), "operator"):
                flash("Operator permission required.")
                return redirect(url_for("dashboard", tab="staff-operator"))

            if airline_name != profile["airline_name"]:
                flash("You can only update flights for your airline.")
                return redirect(url_for("dashboard", tab="staff-operator"))

            cur.execute(
                """
                UPDATE Flight
                SET status = %s
                WHERE airline_name = %s AND flight_num = %s
                """,
                (status, airline_name, int(flight_num_text))
            )
            if cur.rowcount == 0:
                flash("Flight not found.")
                return redirect(url_for("dashboard", tab="staff-operator"))

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
    return redirect(url_for("dashboard", tab="staff-operator"))


@airline.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        flash("Please login first.")
        return redirect(url_for("login_page"))

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


@airline.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out.")
    return redirect(url_for("login_page"))
if __name__=="__main__":
    airline.run(debug=True)