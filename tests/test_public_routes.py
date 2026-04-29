def test_public_search_requires_departure_and_arrival(monkeypatch, client):
    captured = {}
    monkeypatch.setattr("aires.routes.public.get_conn", lambda: (_ for _ in ()).throw(AssertionError("no db")))
    monkeypatch.setattr(
        "aires.routes.public.render_public_page",
        lambda **context: captured.update(context) or "rendered",
    )

    response = client.post(
        "/public/search-flights",
        data={"departure_airport": "JFK"},
    )

    assert response.status_code == 200
    assert captured["search_submitted"] is True
    assert captured["search_message_type"] == "warning"
    assert captured["search_message"] == "Please provide either an arrival airport code or arrival city."


def test_public_flight_status_rejects_non_numeric_flight_number(monkeypatch, client):
    captured = {}
    monkeypatch.setattr("aires.routes.public.get_conn", lambda: (_ for _ in ()).throw(AssertionError("no db")))
    monkeypatch.setattr(
        "aires.routes.public.render_public_page",
        lambda **context: captured.update(context) or "rendered",
    )

    response = client.post(
        "/public/flight-status",
        data={"airline_name": "Delta", "flight_num": "abc"},
    )

    assert response.status_code == 200
    assert captured["status_submitted"] is True
    assert captured["status_message_type"] == "warning"
    assert captured["status_message"] == "Flight number must be a positive integer."
