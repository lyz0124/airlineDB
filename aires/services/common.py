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
