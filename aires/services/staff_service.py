from datetime import datetime


def build_flight_update_payload(existing, form_data):
    new_flight_num = form_data["new_flight_num"]
    departure_airport = form_data["departure_airport"]
    departure_time_text = form_data["departure_time"]
    arrival_airport = form_data["arrival_airport"]
    arrival_time_text = form_data["arrival_time"]
    price_text = form_data["price"]
    status = form_data["status"]
    airplane_id_text = form_data["airplane_id"]

    if new_flight_num and not new_flight_num.isdigit():
        return None, "New flight number must be an integer."

    target_flight_num = int(new_flight_num) if new_flight_num else int(existing["flight_num"])
    target_departure_airport = departure_airport or existing["departure_airport"]
    target_arrival_airport = arrival_airport or existing["arrival_airport"]
    target_status = status or existing["status"]
    target_airplane_id = int(airplane_id_text) if airplane_id_text else int(existing["airplane_id"])
    target_price = float(price_text) if price_text else float(existing["price"])
    if target_price <= 0:
        return None, "Price must be positive."

    target_departure_time = existing["departure_time"]
    target_arrival_time = existing["arrival_time"]
    if departure_time_text:
        target_departure_time = datetime.strptime(departure_time_text, "%Y-%m-%dT%H:%M")
    if arrival_time_text:
        target_arrival_time = datetime.strptime(arrival_time_text, "%Y-%m-%dT%H:%M")
    if target_arrival_time <= target_departure_time:
        return None, "Arrival time must be later than departure time."
    if target_status not in {"upcoming", "in-progress", "delayed"}:
        return None, "Invalid status."

    return {
        "flight_num": target_flight_num,
        "departure_airport": target_departure_airport,
        "departure_time": target_departure_time,
        "arrival_airport": target_arrival_airport,
        "arrival_time": target_arrival_time,
        "price": target_price,
        "status": target_status,
        "airplane_id": target_airplane_id,
    }, None
