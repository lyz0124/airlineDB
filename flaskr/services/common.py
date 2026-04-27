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
