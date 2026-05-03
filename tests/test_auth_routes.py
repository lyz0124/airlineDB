from werkzeug.security import generate_password_hash

from tests.conftest import FakeConnection


def test_home_redirects_to_login_when_logged_out(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_home_redirects_to_dashboard_when_logged_in(client):
    with client.session_transaction() as session:
        session["user_role"] = "customer"
        session["user_id"] = "ada@example.com"
        session["user_name"] = "Ada"

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_rejects_missing_credentials(client):
    response = client.post(
        "/login",
        data={"role": "customer", "username": "", "password": ""},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_customer_login_sets_session_and_redirects(monkeypatch, client):
    connection = FakeConnection(
        [
            {
                "email": "ada@example.com",
                "name": "Ada Lovelace",
                "password": generate_password_hash("correct-password"),
            }
        ]
    )
    monkeypatch.setattr("aires.db.get_conn", lambda: connection)

    response = client.post(
        "/login",
        data={
            "role": "customer",
            "username": "ada@example.com",
            "password": "correct-password",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert connection.closed is True
    with client.session_transaction() as session:
        assert session["user_role"] == "customer"
        assert session["user_id"] == "ada@example.com"
        assert session["user_name"] == "Ada Lovelace"


def test_login_rejects_bad_password(monkeypatch, client):
    connection = FakeConnection(
        [
            {
                "email": "ada@example.com",
                "name": "Ada Lovelace",
                "password": generate_password_hash("correct-password"),
            }
        ]
    )
    monkeypatch.setattr("aires.db.get_conn", lambda: connection)

    response = client.post(
        "/login",
        data={
            "role": "customer",
            "username": "ada@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert connection.closed is True


def test_customer_registration_inserts_and_commits(monkeypatch, client):
    connection = FakeConnection([None])
    monkeypatch.setattr("aires.db.get_conn", lambda: connection)

    response = client.post(
        "/register",
        data={
            "role": "customer",
            "username": "new@example.com",
            "password": "secret",
            "name": "New Customer",
            "passport_number": "P12345",
            "passport_expiration_date": "2030-01-01",
            "date_of_birth": "1990-01-01",
            "building_name": "1",
            "street": "Main St",
            "city": "New York",
            "state": "NY",
            "phone_number": "5551234567",
            "passport_country": "USA",
        },
    )

    executed_sql = " ".join(sql for sql, _ in connection.cursor_obj.executed)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/register")
    assert "INSERT INTO customer" in executed_sql
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
