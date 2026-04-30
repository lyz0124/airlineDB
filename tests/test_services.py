from datetime import datetime, timedelta

from aires.services.common import add_location_filter, resolve_airport_code, staff_has_permission
from aires.services.public_service import validate_public_search
from aires.services.purchase_service import create_purchase
from aires.services.staff_service import build_flight_update_payload


class PurchaseCursor:
    def __init__(self, flight, customer_exists=True, next_ticket_id=42):
        self.flight = flight
        self.customer_exists = customer_exists
        self.next_ticket_id = next_ticket_id
        self.executed = []
        self._next_result = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "FROM flight f" in sql:
            self._next_result = self.flight
        elif "FROM customer" in sql:
            self._next_result = {"1": 1} if self.customer_exists else None
        elif "MAX(ticket_id)" in sql:
            self._next_result = {"next_id": self.next_ticket_id}
        else:
            self._next_result = None

    def fetchone(self):
        return self._next_result


class LocationCursor:
    def __init__(self):
        self.executed = []
        self.airports = {"jfk": "JFK", "nrt": "NRT", "pvg": "PVG", "sha": "SHA"}
        self._next_result = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "FROM airport" in sql and params:
            airport = self.airports.get(params[0].casefold())
            self._next_result = {"airport_name": airport} if airport else None
        else:
            self._next_result = None

    def fetchone(self):
        return self._next_result


def test_validate_public_search_accepts_airport_pair_and_date():
    error = validate_public_search(
        {
            "departure_airport": "JFK",
            "arrival_airport": "LAX",
            "departure_city": "",
            "arrival_city": "",
            "departure_date": "2027-05-01",
        }
    )

    assert error is None


def test_validate_public_search_rejects_bad_date():
    error = validate_public_search(
        {
            "departure_airport": "JFK",
            "arrival_airport": "LAX",
            "departure_city": "",
            "arrival_city": "",
            "departure_date": "05/01/2027",
        }
    )

    assert error == "Invalid date format. Please use YYYY-MM-DD."


def test_staff_has_permission_allows_both_roles():
    assert staff_has_permission("both", "admin") is True
    assert staff_has_permission("both", "operator") is True
    assert staff_has_permission("operator", "admin") is False


def test_resolve_airport_code_accepts_case_insensitive_airport_code():
    cursor = LocationCursor()

    assert resolve_airport_code(cursor, "pvg") == "PVG"


def test_add_location_filter_prefers_airport_code_over_city_fallback():
    cursor = LocationCursor()
    params = []

    sql = add_location_filter(cursor, "SELECT * FROM flight WHERE 1 = 1", params, "departure_airport", "airport_city", "sha")

    assert "departure_airport = %s" in sql
    assert params == ["SHA"]


def test_add_location_filter_falls_back_to_case_insensitive_city_contains():
    cursor = LocationCursor()
    params = []

    sql = add_location_filter(cursor, "SELECT * FROM flight WHERE 1 = 1", params, "departure_airport", "airport_city", "York")

    assert "LOWER(airport_city) LIKE %s" in sql
    assert params == ["%york%"]


def test_build_flight_update_payload_merges_existing_values():
    existing = {
        "flight_num": 100,
        "departure_airport": "JFK",
        "departure_time": datetime(2027, 1, 1, 9, 0),
        "arrival_airport": "LAX",
        "arrival_time": datetime(2027, 1, 1, 12, 0),
        "price": 250,
        "status": "upcoming",
        "airplane_id": 7,
    }
    form_data = {
        "new_flight_num": "101",
        "departure_airport": "",
        "departure_time": "",
        "arrival_airport": "",
        "arrival_time": "",
        "price": "300.50",
        "status": "delayed",
        "airplane_id": "",
    }

    payload, error = build_flight_update_payload(existing, form_data)

    assert error is None
    assert payload["flight_num"] == 101
    assert payload["departure_airport"] == "JFK"
    assert payload["price"] == 300.50
    assert payload["status"] == "delayed"


def test_build_flight_update_payload_rejects_arrival_before_departure():
    existing = {
        "flight_num": 100,
        "departure_airport": "JFK",
        "departure_time": datetime(2027, 1, 1, 9, 0),
        "arrival_airport": "LAX",
        "arrival_time": datetime(2027, 1, 1, 12, 0),
        "price": 250,
        "status": "upcoming",
        "airplane_id": 7,
    }
    form_data = {
        "new_flight_num": "",
        "departure_airport": "",
        "departure_time": "2027-01-01T13:00",
        "arrival_airport": "",
        "arrival_time": "",
        "price": "",
        "status": "",
        "airplane_id": "",
    }

    payload, error = build_flight_update_payload(existing, form_data)

    assert payload is None
    assert error == "Arrival time must be later than departure time."


def test_create_purchase_inserts_ticket_and_purchase_for_valid_future_flight():
    cursor = PurchaseCursor(
        {
            "departure_time": datetime.now() + timedelta(days=7),
            "arrival_time": datetime.now() + timedelta(days=7, hours=3),
            "price": 199.99,
            "status": "upcoming",
            "seat_capacity": 2,
            "sold_tickets": 1,
        },
        customer_exists=True,
        next_ticket_id=42,
    )

    success, message = create_purchase(cursor, "ada@example.com", "Delta", 100)

    assert success is True
    assert message == "Ticket purchased successfully. Ticket ID: 42"
    assert any("INSERT INTO ticket" in sql for sql, _ in cursor.executed)
    assert any("INSERT INTO purchases" in sql for sql, _ in cursor.executed)


def test_create_purchase_rejects_sold_out_flight():
    cursor = PurchaseCursor(
        {
            "departure_time": datetime.now() + timedelta(days=7),
            "arrival_time": datetime.now() + timedelta(days=7, hours=3),
            "price": 199.99,
            "status": "upcoming",
            "seat_capacity": 1,
            "sold_tickets": 1,
        }
    )

    success, message = create_purchase(cursor, "ada@example.com", "Delta", 100)

    assert success is False
    assert message == "This flight is sold out."
