def extract_location(data, prefix):
    """Extract a location value from data, trying {prefix}_location, {prefix}_airport, then {prefix}_city."""
    return (
        data.get(f"{prefix}_location", "").strip()
        or data.get(f"{prefix}_airport", "").strip()
        or data.get(f"{prefix}_city", "").strip()
    )


def get_staff_profile(cur, username):
    cur.execute(
        """
        SELECT username, airline_name, role, first_name, last_name
        FROM airline_staff
        WHERE username = %s
        """,
        (username,),
    )
    return cur.fetchone()


def staff_has_permission(staff_role, required):
    normalized = (staff_role or "").lower()
    if normalized == "both":
        return True
    return normalized == required


def normalize_location_text(value):
    return " ".join((value or "").strip().split())


def _escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_location_options(cur):
    cur.execute(
        """
        SELECT airport_name, airport_city
        FROM airport
        ORDER BY airport_city, airport_name
        """
    )
    airports = cur.fetchall()
    cur.execute(
        """
        SELECT city_name
        FROM city
        ORDER BY city_name
        """
    )
    cities = cur.fetchall()
    return {
        "airports": airports,
        "cities": cities,
    }


def resolve_airport_code(cur, value):
    location = normalize_location_text(value)
    if not location:
        return None

    cur.execute(
        """
        SELECT airport_name
        FROM airport
        WHERE LOWER(airport_name) = LOWER(%s)
        LIMIT 1
        """,
        (location,),
    )
    row = cur.fetchone()
    return row["airport_name"] if row else None


def add_location_filter(cur, sql, params, airport_column, city_column, value):
    location = normalize_location_text(value)
    if not location:
        return sql

    airport_code = resolve_airport_code(cur, location)
    if airport_code:
        params.append(airport_code)
        return f"{sql} AND {airport_column} = %s"

    params.append(f"%{_escape_like(location.casefold())}%")
    return f"{sql} AND LOWER({city_column}) LIKE %s ESCAPE '\\\\'"


def require_staff_permission(cur, staff_user, required_role):
    """Check staff profile and permission. Returns (profile, None) if allowed, (None, error_message) if denied."""
    profile = get_staff_profile(cur, staff_user)
    if not profile or not staff_has_permission(profile.get("role"), required_role):
        return None, f"{required_role.title()} permission required."
    return profile, None


def get_airport_list(cur, limit=10, search=None):
    """Get a list of airports, optionally filtered by search term, limited by count."""
    if search:
        cur.execute(
            """
            SELECT airport_name, airport_city
            FROM airport
            WHERE airport_name LIKE %s OR airport_city LIKE %s
            ORDER BY airport_city, airport_name
            LIMIT %s
            """,
            (f"%{search}%", f"%{search}%", limit),
        )
    else:
        cur.execute(
            """
            SELECT airport_name, airport_city
            FROM airport
            ORDER BY airport_city, airport_name
            LIMIT %s
            """,
            (limit,),
        )
    return cur.fetchall()


def get_airplane_list(cur, airline_name, limit=10):
    """Get a list of airplanes for a given airline, limited by count."""
    cur.execute(
        """
        SELECT airplane_id, seat_capacity
        FROM airplane
        WHERE airline_name = %s
        ORDER BY airplane_id
        LIMIT %s
        """,
        (airline_name, limit),
    )
    return cur.fetchall()


def get_airline_list(cur):
    """Get a list of all distinct airline names from the flight table."""
    cur.execute(
        """
        SELECT DISTINCT airline_name
        FROM flight
        ORDER BY airline_name
        """
    )
    return [row["airline_name"] for row in cur.fetchall()]


def get_staff_members(cur, airline_name, search=None):
    """Get staff members for a given airline, optionally filtered by search term."""
    if search:
        cur.execute(
            """
            SELECT username, first_name, last_name, role, airline_name
            FROM airline_staff
            WHERE airline_name = %s
              AND (username LIKE %s OR first_name LIKE %s OR last_name LIKE %s)
            ORDER BY role, username
            """,
            (airline_name, f"%{search}%", f"%{search}%", f"%{search}%"),
        )
    else:
        cur.execute(
            """
            SELECT username, first_name, last_name, role, airline_name
            FROM airline_staff
            WHERE airline_name = %s
            ORDER BY role, username
            """,
            (airline_name,),
        )
    return cur.fetchall()


def update_staff_role(cur, username, new_role, airline_name):
    """Update a staff member's role. Only allows valid roles."""
    valid_roles = {"admin", "operator", "both"}
    if new_role not in valid_roles:
        return False, "Invalid role. Must be one of: admin, operator, both."

    cur.execute(
        """
        UPDATE airline_staff
        SET role = %s
        WHERE username = %s AND airline_name = %s
        """,
        (new_role, username, airline_name),
    )
    if cur.rowcount == 0:
        return False, "Staff member not found or not in your airline."
    return True, f"Role for {username} updated to {new_role}."
