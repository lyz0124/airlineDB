from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

airline=Flask(__name__)
airline.secret_key="dev-secret-key"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "Airline_booking",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def split_name(full_name):
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], "N/A"
    return parts[0], " ".join(parts[1:])


def verify_password(stored_password, input_password):
    # Backward compatibility for old plaintext data in PRJ2 seed tables.
    return check_password_hash(stored_password, input_password) or stored_password == input_password

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
                    (email, name, password, building_name, street, city, state, phone_number,
                     passport_number, passport_expiration_date, passport_country, date_of_birth)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        username, name, password_hash, building_name, street, city, state, phone_number,
                        passport_number, passport_expiration_date, passport_country, date_of_birth
                    )
                )

            elif role == "booking_agent":
                booking_agent_id = request.form.get("booking_agent_id", "").strip()
                if not booking_agent_id:
                    flash("Booking Agent ID is required.")
                    return redirect(url_for("register_page"))

                cur.execute("SELECT 1 FROM booking_agent WHERE email = %s", (username,))
                if cur.fetchone():
                    flash("Booking agent email already exists.")
                    return redirect(url_for("register_page"))

                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name = 'booking_agent'
                      AND column_name = 'booking_agent_id'
                    """
                )
                has_agent_id_column = cur.fetchone() is not None

                if has_agent_id_column:
                    cur.execute(
                        """
                        INSERT INTO booking_agent (email, password, booking_agent_id)
                        VALUES (%s, %s, %s)
                        """,
                        (username, password_hash, booking_agent_id)
                    )
                else:
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
                if not airline_name:
                    flash("Airline name is required for staff.")
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
    if request.method == "GET":
        return render_template("login.html")

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
                    display_name = f'{user_row["first_name"]} {user_row["last_name"]}'

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


@airline.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        flash("Please login first.")
        return redirect(url_for("login_page"))
    return render_template(
        "dashboard.html",
        role=session["user_role"],
        user_id=session["user_id"],
        user_name=session["user_name"]
    )


@airline.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out.")
    return redirect(url_for("login_page"))
if __name__=="__main__":
    airline.run(debug=True)