from datetime import date, timedelta

from ..services.common import (
    add_location_filter,
    extract_location,
    get_airplane_list,
    get_airport_list,
    get_location_options,
    get_staff_members,
    get_staff_profile,
)
from ..utils import fill_monthly_series, month_labels_between, parse_date


def _extract_filters(args, field_prefix):
    """Extract and clean filter parameters from args for a given role."""
    return {
        "start_date": args.get(f"{field_prefix}start_date", "").strip(),
        "end_date": args.get(f"{field_prefix}end_date", "").strip(),
        "origin": args.get(f"{field_prefix}origin", "").strip(),
        "destination": args.get(f"{field_prefix}destination", "").strip(),
    }


def _apply_flight_filters(sql_base, params, filters):
    """Apply origin/destination filters to a flight query."""
    if filters["origin"]:
        sql_base += " AND f.departure_airport = %s"
        params.append(filters["origin"])
    if filters["destination"]:
        sql_base += " AND f.arrival_airport = %s"
        params.append(filters["destination"])
    return sql_base, params


def _calculate_remaining_seats(rows):
    """Add remaining_seats calculation to each row."""
    for row in rows:
        row["remaining_seats"] = int(row["seat_capacity"]) - int(row["sold_tickets"])
    return rows


def _get_top_destinations(cur, airline_name, year=None, time_range="3m", limit=5):
    """Get top destinations by ticket count."""
    if year is None:
        year = date.today().year

    if time_range == "3m":
        time_condition = "f.departure_time >= DATE_SUB(NOW(), INTERVAL 3 MONTH)"
        params = (airline_name, limit)
    else:
        time_condition = "YEAR(f.departure_time) = %s"
        params = (airline_name, year, limit)

    cur.execute(
        f"""
        SELECT
            f.arrival_airport,
            a.airport_city,
            COUNT(DISTINCT t.ticket_id) AS tickets_sold
        FROM flight f
        JOIN airport a ON a.airport_name = f.arrival_airport
        LEFT JOIN ticket t ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s
          AND {time_condition}
        GROUP BY f.arrival_airport, a.airport_city
        ORDER BY tickets_sold DESC
        LIMIT %s
        """,
        params,
    )
    return cur.fetchall()


def get_customer_purchased_filters(args):
    """Get purchased flight filter parameters for a customer."""
    return _extract_filters(args, "customer_")


def _get_purchased_flights(cur, field_name, field_value, filters, extra_select="", extra_where="", order_by="f.departure_time ASC"):
    """Generic function to get purchased flights filtered by any field (customer_email or booking_agent_email)."""
    sql = f"""
        SELECT
            p.purchase_date,
            {extra_select}
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
        WHERE p.{field_name} = %s
    """
    params = [field_value]

    if filters.get("start_date"):
        sql += " AND DATE(f.departure_time) >= %s"
        params.append(filters["start_date"])
    if filters.get("end_date"):
        sql += " AND DATE(f.departure_time) <= %s"
        params.append(filters["end_date"])

    sql, params = _apply_flight_filters(sql, params, filters)

    if extra_where:
        sql += extra_where
    sql += f" ORDER BY {order_by}"

    cur.execute(sql, tuple(params))
    return cur.fetchall()


def get_customer_purchased_flights(cur, customer_email, filters):
    """Get purchased flights for a customer."""
    extra_where = ""
    if not filters.get("start_date") and not filters.get("end_date"):
        extra_where = " AND f.departure_time >= NOW()"
    return _get_purchased_flights(
        cur, "customer_email", customer_email, filters,
        extra_select="f.status,",
        extra_where=extra_where,
        order_by="f.departure_time ASC",
    )


def get_customer_search_filters(args):
    """Get customer search filter parameters."""
    return {
        "departure_location": extract_location(args, "search_departure"),
        "arrival_location": extract_location(args, "search_arrival"),
        "departure_date": args.get("search_departure_date", "").strip(),
    }


def get_customer_search_results(cur, search_filters):
    """Get search results for a customer."""
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

    search_sql = add_location_filter(
        cur, search_sql, search_params, "f.departure_airport", "dep.airport_city", search_filters["departure_location"]
    )
    search_sql = add_location_filter(
        cur, search_sql, search_params, "f.arrival_airport", "arr.airport_city", search_filters["arrival_location"]
    )
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
    return _calculate_remaining_seats(search_results)


def get_customer_custom_spending_data(cur, customer_email, start_date, end_date):
    """Get spending data for a customer within a custom date range."""
    custom_total = 0.0
    custom_labels = []
    custom_amounts = []
    custom_date_error = None

    if start_date and end_date:
        try:
            parsed_custom_start = parse_date(start_date)
            parsed_custom_end = parse_date(end_date)

            if parsed_custom_start > parsed_custom_end:
                custom_date_error = "Start date cannot be later than end date."
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(f.price), 0) AS total
                    FROM purchases p
                    JOIN ticket t ON t.ticket_id = p.ticket_id
                    JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
                    WHERE p.customer_email = %s
                    AND p.purchase_date BETWEEN %s AND %s
                    """,
                    (customer_email, start_date, end_date),
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
                    (customer_email, start_date, end_date),
                )
                custom_rows = cur.fetchall()
                custom_labels = month_labels_between(parsed_custom_start, parsed_custom_end)
                custom_amounts = fill_monthly_series(custom_rows, custom_labels, "amount")

        except ValueError:
            custom_date_error = "Invalid date format."

    return custom_total, custom_labels, custom_amounts, custom_date_error


def load_customer_dashboard(cur, customer_email, args):
    """Load all customer dashboard data."""
    # Load purchased flights data
    purchased_filters = get_customer_purchased_filters(args)
    purchased_flights = get_customer_purchased_flights(cur, customer_email, purchased_filters)

    # Load search results
    search_filters = get_customer_search_filters(args)
    search_results = get_customer_search_results(cur, search_filters)

    # Load custom spending data - defaults to past 12 months
    custom_start = args.get("spending_start_date", "").strip()
    custom_end = args.get("spending_end_date", "").strip()

    if not custom_start and not custom_end:
        custom_end = date.today().strftime("%Y-%m-%d")
        custom_start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    custom_total, custom_labels, custom_amounts, custom_date_error = get_customer_custom_spending_data(
        cur, customer_email, custom_start, custom_end
    )

    return {
        "purchased_filters": purchased_filters,
        "purchased_flights": purchased_flights,
        "search_filters": search_filters,
        "search_results": search_results,
        "location_options": get_location_options(cur),
        "spending": {
            "custom_start": custom_start,
            "custom_end": custom_end,
            "custom_total": custom_total,
            "custom_labels": custom_labels,
            "custom_amounts": custom_amounts,
            "custom_date_error": custom_date_error,
        },
    }


def get_agent_flight_filters(args):
    """Get flight filter parameters for a booking agent."""
    return _extract_filters(args, "agent_")


def get_agent_purchased_flights(cur, agent_email, flight_filters):
    """Get flights sold by a booking agent."""
    return _get_purchased_flights(
        cur, "booking_agent_email", agent_email, flight_filters,
        extra_select="p.customer_email,",
        order_by="p.purchase_date DESC",
    )


def get_agent_authorized_airlines(cur, agent_email):
    """Get airlines authorized for a booking agent."""
    cur.execute(
        """
        SELECT airline_name
        FROM agent_airline_authorization
        WHERE agent_email = %s
        ORDER BY airline_name
        """,
        (agent_email,),
    )
    return [row["airline_name"] for row in cur.fetchall()]


def get_agent_search_filters(args):
    """Get search filter parameters for a booking agent."""
    return {
        "airline_name": args.get("agent_search_airline", "").strip(),
        "departure_date": args.get("agent_search_date", "").strip(),
    }


def get_agent_sale_flights(cur, agent_email, search_filters):
    """Get flights available for a booking agent to sell."""
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
    return _calculate_remaining_seats(sale_flights)


def _get_commission_stats(cur, agent_email, extra_where=""):
    """Get commission statistics for a booking agent with an optional extra WHERE clause."""
    cur.execute(
        f"""
        SELECT
            COALESCE(SUM(f.price * 0.1), 0) AS commission_total,
            COALESCE(AVG(f.price * 0.1), 0) AS avg_commission,
            COUNT(*) AS tickets_sold
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE p.booking_agent_email = %s
          {extra_where}
        """,
        (agent_email,),
    )
    return cur.fetchone()


def get_agent_commission_stats(cur, agent_email):
    """Get commission statistics for a booking agent (last 30 days + all time)."""
    last_30_stats = _get_commission_stats(
        cur, agent_email, "AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    )
    all_time_stats = _get_commission_stats(cur, agent_email)
    return {
        "last_30": last_30_stats,
        "all_time": all_time_stats,
    }


def _get_top_customers(cur, agent_email, metric="tickets"):
    """Get top 5 customers for a booking agent, ranked by ticket count or commission."""
    if metric == "commission":
        cur.execute(
            """
            SELECT
                p.customer_email,
                COALESCE(SUM(f.price * 0.1), 0) AS value
            FROM purchases p
            JOIN ticket t ON t.ticket_id = p.ticket_id
            JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE p.booking_agent_email = %s
              AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
            GROUP BY p.customer_email
            ORDER BY value DESC
            LIMIT 5
            """,
            (agent_email,),
        )
    else:
        cur.execute(
            """
            SELECT
                p.customer_email,
                COUNT(*) AS value
            FROM purchases p
            WHERE p.booking_agent_email = %s
              AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY p.customer_email
            ORDER BY value DESC
            LIMIT 5
            """,
            (agent_email,),
        )
    return cur.fetchall()


def load_agent_dashboard(cur, agent_email, args):
    """Load all booking agent dashboard data."""
    flight_filters = get_agent_flight_filters(args)
    purchased_rows = get_agent_purchased_flights(cur, agent_email, flight_filters)

    authorized_airlines = get_agent_authorized_airlines(cur, agent_email)

    search_filters = get_agent_search_filters(args)
    sale_flights = get_agent_sale_flights(cur, agent_email, search_filters)

    commission_stats = get_agent_commission_stats(cur, agent_email)
    top_tickets = _get_top_customers(cur, agent_email, "tickets")
    top_commission = _get_top_customers(cur, agent_email, "commission")

    return {
        "flight_filters": flight_filters,
        "purchased_rows": purchased_rows,
        "authorized_airlines": authorized_airlines,
        "search_filters": search_filters,
        "sale_flights": sale_flights,
        "commission_stats": commission_stats,
        "top_tickets_labels": [row["customer_email"] for row in top_tickets],
        "top_tickets_values": [int(row["value"]) for row in top_tickets],
        "top_commission_labels": [row["customer_email"] for row in top_commission],
        "top_commission_values": [float(row["value"]) for row in top_commission],
        "location_options": get_location_options(cur),
    }


def get_staff_profile_and_info(cur, staff_user):
    """Get staff profile and related info."""
    profile = get_staff_profile(cur, staff_user)
    if not profile:
        return None, None, None, None, None

    airline_name = profile["airline_name"]
    staff_role = (profile.get("role") or "admin").lower()
    default_start = date.today()
    default_end = date.today() + timedelta(days=30)

    return profile, airline_name, staff_role, default_start, default_end


def get_staff_flight_filters(args, default_start, default_end):
    """Get flight filter parameters for staff."""
    return {
        "start_date": args.get("staff_start_date", default_start.strftime("%Y-%m-%d")).strip(),
        "end_date": args.get("staff_end_date", default_end.strftime("%Y-%m-%d")).strip(),
        "origin": args.get("staff_origin", "").strip(),
        "destination": args.get("staff_destination", "").strip(),
    }


def get_staff_flights(cur, airline_name, flight_filters):
    """Get flights for the staff's airline."""
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

    flights_sql, flights_params = _apply_flight_filters(flights_sql, flights_params, flight_filters)

    flights_sql += " ORDER BY f.departure_time ASC"
    cur.execute(flights_sql, tuple(flights_params))
    return cur.fetchall()


def get_staff_passengers_for_flight(cur, airline_name, flight_num):
    """Get passenger list for a specific flight."""
    passengers = []
    if flight_num.isdigit():
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
            (airline_name, int(flight_num)),
        )
        passengers = cur.fetchall()
    return passengers


def get_staff_customer_flights(cur, customer_email, airline_name):
    """Get flights for a specific customer."""
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
    return customer_flights


def get_staff_top_agents(cur, airline_name, args):
    """Get top booking agents ranking."""
    selected_year = args.get("staff_year", str(date.today().year)).strip()
    selected_month = args.get("staff_month", str(date.today().month)).strip()

    rank_raw = args.get("staff_agent_rank_by", "tickets").strip().lower()
    staff_agent_rank_by = rank_raw if rank_raw in ("tickets", "commission") else "tickets"
    top_agents_order_by = (
        "ticket_count DESC, commission_total DESC"
        if staff_agent_rank_by == "tickets"
        else "commission_total DESC, ticket_count DESC"
    )

    cur.execute(
        f"""
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
        ORDER BY {top_agents_order_by}
        LIMIT 5
        """,
        (airline_name, selected_year, selected_month),
    )
    return cur.fetchall()


def get_most_frequent_customer(cur, airline_name):
    """Get the most frequent customer."""
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
    return cur.fetchone()


def get_tickets_by_month(cur, airline_name, year=None):
    """Get ticket counts grouped by month."""
    if year is None:
        year = date.today().year

    cur.execute(
        """
        SELECT
            DATE_FORMAT(p.purchase_date, '%%Y-%%m') AS month,
            COUNT(*) AS tickets
        FROM purchases p
        JOIN ticket t ON t.ticket_id = p.ticket_id
        JOIN flight f ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        WHERE f.airline_name = %s
          AND YEAR(p.purchase_date) = %s
        GROUP BY DATE_FORMAT(p.purchase_date, '%%Y-%%m')
        ORDER BY month
        """,
        (airline_name, year),
    )
    tickets_by_month_rows = cur.fetchall()
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    yearly_labels = month_labels_between(start_date, end_date)
    tickets_by_month_values = fill_monthly_series(tickets_by_month_rows, yearly_labels, "tickets")
    return tickets_by_month_values, yearly_labels


def get_flight_performance_stats(cur, airline_name, year=None):
    """Get flight performance stats (on-time rate)."""
    if year is None:
        year = date.today().year

    cur.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'delayed' THEN 1 ELSE 0 END) AS delayed_count,
            SUM(CASE WHEN status <> 'delayed' THEN 1 ELSE 0 END) AS on_time_count
        FROM flight
        WHERE airline_name = %s
          AND YEAR(departure_time) = %s
        """,
        (airline_name, year),
    )
    delay_stats = cur.fetchone()

    top_destinations_3m = _get_top_destinations(cur, airline_name, year, "3m", 5)
    top_destinations_1y = _get_top_destinations(cur, airline_name, year, "1y", 5)

    return delay_stats, top_destinations_3m, top_destinations_1y


def load_staff_dashboard(cur, staff_user, args):
    """Load all staff dashboard data."""
    profile, airline_name, staff_role, default_start, default_end = get_staff_profile_and_info(cur, staff_user)
    if not profile:
        return None

    flight_filters = get_staff_flight_filters(args, default_start, default_end)
    flights = get_staff_flights(cur, airline_name, flight_filters)

    passenger_query_flight = args.get("passenger_flight_num", "").strip()
    passengers = get_staff_passengers_for_flight(cur, airline_name, passenger_query_flight)

    customer_email = args.get("staff_customer_email", "").strip()
    customer_flights = get_staff_customer_flights(cur, customer_email, airline_name)

    top_agents = get_staff_top_agents(cur, airline_name, args)
    most_frequent_customer = get_most_frequent_customer(cur, airline_name)

    selected_year = args.get("staff_year", str(date.today().year)).strip()
    selected_month = args.get("staff_month", str(date.today().month)).strip()
    rank_raw = args.get("staff_agent_rank_by", "tickets").strip().lower()
    staff_agent_rank_by = rank_raw if rank_raw in ("tickets", "commission") else "tickets"

    tickets_by_month_values, yearly_labels = get_tickets_by_month(cur, airline_name, int(selected_year))
    delay_stats, top_destinations_3m, top_destinations_1y = get_flight_performance_stats(cur, airline_name, int(selected_year))

    return {
        "profile": profile,
        "staff_role": staff_role,
        "airline_name": airline_name,
        "flight_filters": flight_filters,
        "flights": flights,
        "location_options": get_location_options(cur),
        "passenger_query_airline": airline_name,
        "passenger_query_flight": passenger_query_flight,
        "passengers": passengers,
        "staff_customer_email": customer_email,
        "customer_flights": customer_flights,
        "selected_year": selected_year,
        "selected_month": selected_month,
        "staff_agent_rank_by": staff_agent_rank_by,
        "top_agents": top_agents,
        "most_frequent_customer": most_frequent_customer,
        "tickets_by_month_labels": yearly_labels,
        "tickets_by_month_values": tickets_by_month_values,
        "delay_stats": delay_stats,
        "top_destinations_3m": top_destinations_3m,
        "top_destinations_1y": top_destinations_1y,
        "airport_list": get_airport_list(cur, 10),
        "airplane_list": get_airplane_list(cur, airline_name, 10),
        "staff_members": get_staff_members(cur, airline_name, args.get("staff_search", "").strip() or None),
    }
