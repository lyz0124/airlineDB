from datetime import datetime


def get_next_ticket_id(cur):
    cur.execute("SELECT COALESCE(MAX(ticket_id), 0) + 1 AS next_id FROM ticket")
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
        FROM flight f
        JOIN airplane ap
          ON ap.airline_name = f.airline_name
         AND ap.airplane_id = f.airplane_id
        LEFT JOIN ticket t
          ON t.airline_name = f.airline_name
         AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s
          AND f.flight_num = %s
        GROUP BY
            f.airline_name, f.flight_num, f.departure_time, f.arrival_time,
            f.price, f.status, ap.seat_capacity
        """,
        (airline_name, flight_num),
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
        (agent_email, airline_name),
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

    cur.execute("SELECT 1 FROM customer WHERE email = %s", (customer_email,))
    if not cur.fetchone():
        return False, "Customer does not exist."

    if float(flight["price"]) <= 0:
        return False, "Invalid flight pricing configuration."

    ticket_id = get_next_ticket_id(cur)
    cur.execute(
        """
        INSERT INTO ticket (ticket_id, airline_name, flight_num)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, airline_name, flight_num),
    )
    cur.execute(
        """
        INSERT INTO purchases (ticket_id, customer_email, booking_agent_email, purchase_date)
        VALUES (%s, %s, %s, CURDATE())
        """,
        (ticket_id, customer_email, booking_agent_email),
    )
    return True, f"Ticket purchased successfully. Ticket ID: {ticket_id}"
