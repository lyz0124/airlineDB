from datetime import datetime


def validate_public_search(search_form):
    if not any(search_form.values()):
        return "Please provide at least one search condition."
    if not (search_form["departure_airport"] or search_form["departure_city"]):
        return "Please provide either a departure airport code or departure city."
    if not (search_form["arrival_airport"] or search_form["arrival_city"]):
        return "Please provide either an arrival airport code or arrival city."

    departure_date = search_form["departure_date"]
    if departure_date:
        try:
            datetime.strptime(departure_date, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD."
    return None


def search_public_flights(cur, search_form):
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
        FROM flight f
        JOIN airport dep ON dep.airport_name = f.departure_airport
        JOIN airport arr ON arr.airport_name = f.arrival_airport
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

    if search_form["departure_date"]:
        sql += " AND DATE(f.departure_time) = %s"
        params.append(search_form["departure_date"])

    sql += " ORDER BY f.departure_time ASC LIMIT 200"
    cur.execute(sql, tuple(params))
    return cur.fetchall()


def get_public_flight_status(cur, airline_name, flight_num):
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
        FROM flight
        WHERE airline_name = %s
          AND flight_num = %s
          AND status = 'in-progress'
        """,
        (airline_name, flight_num),
    )
    return cur.fetchone()
