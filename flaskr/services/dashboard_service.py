from datetime import date, timedelta

from ..services.common import get_staff_profile
from ..utils import fill_monthly_series, month_labels_between, parse_date


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
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
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
        FROM flight f
        JOIN airport dep ON dep.airport_name = f.departure_airport
        JOIN airport arr ON arr.airport_name = f.arrival_airport
        JOIN airplane ap ON ap.airline_name = f.airline_name AND ap.airplane_id = f.airplane_id
        LEFT JOIN ticket t ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
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
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.customer_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        """,
        (customer_email,),
    )
    total_12m = float(cur.fetchone()["total_spending_12m"])

    cur.execute(
        """
        SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month, COALESCE(SUM(f.price), 0) AS amount
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.customer_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
        ORDER BY month
        """,
        (customer_email,),
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
            FROM purchases p
            JOIN ticket t ON t.ticket_id = p.ticket_id
            JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND p.purchase_date BETWEEN %s AND %s
            """,
            (customer_email, custom_start, custom_end),
        )
        custom_total = float(cur.fetchone()["total"])

        cur.execute(
            """
            SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month, COALESCE(SUM(f.price), 0) AS amount
            FROM purchases p
            JOIN ticket t ON t.ticket_id = p.ticket_id
            JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND p.purchase_date BETWEEN %s AND %s
            GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
            ORDER BY month
            """,
            (customer_email, custom_start, custom_end),
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
        },
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
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
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
        (agent_email,),
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
        FROM flight f
        JOIN agent_airline_authorization aa ON aa.airline_name = f.airline_name
        JOIN airplane ap ON ap.airline_name = f.airline_name AND ap.airplane_id = f.airplane_id
        LEFT JOIN ticket t ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
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
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """,
        (agent_email,),
    )
    commission_stats = cur.fetchone()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COUNT(*) AS ticket_count
        FROM purchases p
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 5
        """,
        (agent_email,),
    )
    top_tickets = cur.fetchall()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COALESCE(SUM(f.price * 0.1), 0) AS commission
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY commission DESC
        LIMIT 5
        """,
        (agent_email,),
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
        FROM flight f
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
            FROM purchases p
            JOIN ticket t ON t.ticket_id = p.ticket_id
            JOIN customer c ON c.email = p.customer_email
            WHERE t.airline_name = %s
              AND t.flight_num = %s
            ORDER BY p.purchase_date DESC
            """,
            (passenger_query_airline, passenger_query_flight),
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
            FROM purchases p
            JOIN ticket t ON t.ticket_id = p.ticket_id
            JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.customer_email = %s
              AND f.airline_name = %s
            ORDER BY f.departure_time DESC
            """,
            (customer_email, airline_name),
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
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.booking_agent_email IS NOT NULL
          AND YEAR(p.purchase_date) = %s
          AND MONTH(p.purchase_date) = %s
        GROUP BY p.booking_agent_email
        ORDER BY ticket_count DESC, commission_total DESC
        LIMIT 5
        """,
        (airline_name, selected_year, selected_month),
    )
    top_agents = cur.fetchall()

    cur.execute(
        """
        SELECT
            p.customer_email,
            COUNT(*) AS ticket_count
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 1
        """,
        (airline_name,),
    )
    most_frequent_customer = cur.fetchone()

    cur.execute(
        """
        SELECT
            DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month,
            COUNT(*) AS tickets
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
        GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
        ORDER BY month
        """,
        (airline_name,),
    )
    tickets_by_month_rows = cur.fetchall()
    yearly_labels = month_labels_between((date.today() - timedelta(days=365)).replace(day=1), date.today())
    tickets_by_month_values = fill_monthly_series(tickets_by_month_rows, yearly_labels, "tickets")

    cur.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'delayed' THEN 1 ELSE 0 END) AS delayed_count,
            SUM(CASE WHEN status <> 'delayed' THEN 1 ELSE 0 END) AS on_time_count
        FROM flight
        WHERE airline_name = %s
          AND departure_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        """,
        (airline_name,),
    )
    delay_stats = cur.fetchone()

    cur.execute(
        """
        SELECT
            f.arrival_airport,
            a.airport_city,
            COUNT(*) AS flight_count
        FROM flight f
        JOIN airport a ON a.airport_name = f.arrival_airport
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
        GROUP BY f.arrival_airport, a.airport_city
        ORDER BY flight_count DESC
        LIMIT 5
        """,
        (airline_name,),
    )
    top_destinations_3m = cur.fetchall()

    cur.execute(
        """
        SELECT
            f.arrival_airport,
            a.airport_city,
            COUNT(*) AS flight_count
        FROM flight f
        JOIN airport a ON a.airport_name = f.arrival_airport
        WHERE f.airline_name = %s
          AND f.departure_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY f.arrival_airport, a.airport_city
        ORDER BY flight_count DESC
        LIMIT 5
        """,
        (airline_name,),
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
