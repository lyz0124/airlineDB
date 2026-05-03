# Airline DB

This is a course project for CSCI-SHU 213 Databases.

## Bonus functionalities

### Search enhancements

- [x] Airport and city in one single search box (Search airport code first, and fallback to city if not matched)
  - [x] Only allow free input of airports and cities for airline staff with admin permission when solely creating airports and cities
  - [x] For other cases, provide a **searchable** drop-down menu
- [x] Blur search on cities: case-insensitive, match by containing instead of equal

## TODO I

Customer dashboard:
- [x] In purchased flights panel, also enable blur search city search in `origin airport` field and `destination airport` field.
- [x] Add labels to the date range input boxes to indicate start date and end date
- [x] For the review spending, set the default view as a custom view with default arguments. i.e., merge the two views.

Booking Agents:
- [x] For comission and number of sold tickets, display both in past 30 days and over all of the time

Airline Staff:
- [x] Display analytics: tickets sold per month by year, and set the default year to display as the current year.
- [x] Display delay vs on-time statistics grouping by year instead of displaying last year's
- [x] Rank top destinations on number of tickets sold to that destination, isntead of flights to that destination
- [x] For all form fields where flight numbers are inputted, make the former airline field not editable, since the airline staff can only edit flights in their own airline. (The sql statement was correct, but the displayed form entry was editable)

## TODO II

Airline Staff dashboard:
- [x] Replace the add airplane and add airport box with a searchable list. When the search term is not matched, give the option to add an airplane or airport. List ten for each by default.
  - [x] If fail to add an airport or airplane, instead of only reporting error "fail to add”, report if it is because the entry already exists.
- [x] Arrange the airline staff analytics panel more clearly. Make it more readable. Indicate which components are only affected by the year filter, which are affected by both year and month filter, and which are not affected by any filter.

Register:
- [x] Change the airline field of the register form of airline staff to be a searchable dropdown menu.
- [x] If the booking agent ID is actually useless, remove that field.

## Repository Manifest

- **Top-level**: `pyproject.toml` (project metadata), `README.md` (this file).
- **Package: aires/**: Flask application package and helpers.
  - [aires/__init__.py](aires/__init__.py): App factory and blueprint registration.
  - [aires/db.py](aires/db.py): Database connection helpers and context managers (`with_db`, `with_cursor`).
  - [aires/utils.py](aires/utils.py): Small utility helpers (parsing, formatting).
  - [aires/decorators.py](aires/decorators.py): Route decorators (e.g., `role_required`).
  - [aires/airline_DDL.sql](aires/airline_DDL.sql): Database schema used by the project.
  - [aires/airline.py](aires/airline.py): (project-specific helper/runner; app entrypoints).

- **Routes (user-facing endpoints)**
  - [aires/routes/public.py](aires/routes/public.py): Public search and flight status pages and handlers.
  - [aires/routes/auth.py](aires/routes/auth.py): Registration, login, logout handlers.
  - [aires/routes/customer.py](aires/routes/customer.py): Customer dashboard, purchase and cancel endpoints.
  - [aires/routes/staff.py](aires/routes/staff.py): Airline staff dashboard and admin actions (add airport/airplane, create/edit flights).
  - [aires/routes/agent.py](aires/routes/agent.py): Booking agent pages (authorization, purchases) — user-facing agent flows.
  - [aires/routes/dashboard.py](aires/routes/dashboard.py): Dashboard route orchestration.

- **Services (business logic interacting with DB)**
  - [aires/services/public_service.py](aires/services/public_service.py): `search_public_flights`, `get_public_flight_status` (SQL for public queries).
  - [aires/services/common.py](aires/services/common.py): Shared DB helper functions (resolve_airport_code, get_airport_list, get_airline_list, get_staff_profile).
  - [aires/services/dashboard_service.py](aires/services/dashboard_service.py): Dashboard queries for staff/customer (flights, purchases, analytics).
  - [aires/services/purchase_service.py](aires/services/purchase_service.py): Purchase lifecycle (`create_purchase`, `cancel_purchase`, ticket id generation).
  - [aires/services/staff_service.py](aires/services/staff_service.py): Staff helper logic for flight updates.

- **Templates**: HTML pages used by routes (login/register/staff/customer dashboards).
  - [aires/templates/login.html](aires/templates/login.html)
  - [aires/templates/register.html](aires/templates/register.html)
  - [aires/templates/staff_dashboard.html](aires/templates/staff_dashboard.html)
  - [aires/templates/customer_dashboard.html](aires/templates/customer_dashboard.html)
  - [aires/templates/agent_dashboard.html](aires/templates/agent_dashboard.html)

- **Tests and fixtures**
  - [tests/conftest.py](tests/conftest.py): Test fixtures and setup.
  - [tests/test_public_routes.py](tests/test_public_routes.py): Tests for public endpoints.
  - [tests/test_auth_routes.py](tests/test_auth_routes.py): Tests for auth flows.
  - [tests/test_services.py](tests/test_services.py): Unit tests for services.
  - [tests/airline_inserts.sql](tests/airline_inserts.sql): Test seed data inserts.


## Feature → Database Query Mapping (short)

- **Public: Search upcoming flights**
  - Handler: [aires/routes/public.py](aires/routes/public.py)::`public_search_flights`
  - Service: [aires/services/public_service.py](aires/services/public_service.py)::`search_public_flights`
  - Key SQL: SELECT from `flight` JOIN `airport` (dep/arr) WHERE `f.departure_time >= NOW()` plus location filters added by `add_location_filter` (which resolves airport code or uses `LOWER(city) LIKE %s`).

- **Public: In-progress flight status lookup**
  - Handler: [aires/routes/public.py](aires/routes/public.py)::`public_flight_status`
  - Service: [aires/services/public_service.py](aires/services/public_service.py)::`get_public_flight_status`
  - Key SQL: SELECT ... FROM `flight` WHERE `airline_name = %s AND flight_num = %s AND status = 'in-progress'`.

- **Register (customer / booking agent / airline staff)**
  - Handler: [aires/routes/auth.py](aires/routes/auth.py)::`register_page` (POST)
  - Key SQL: INSERT into `customer` or `booking_agent` or `airline_staff` (see route); pre-checks use SELECT 1 FROM corresponding table to detect duplicates.

- **Login**
  - Handler: [aires/routes/auth.py](aires/routes/auth.py)::`login_page`
  - Key SQL: SELECT email/password FROM `customer` OR `booking_agent` OR SELECT username/password FROM `airline_staff` to validate credentials.

- **Customer: Dashboard — search & purchased flights**
  - Handler: [aires/routes/customer.py](aires/routes/customer.py)::`customer_dashboard` calls `load_customer_dashboard` in [aires/services/dashboard_service.py](aires/services/dashboard_service.py).
  - Services used include `get_customer_search_results` (SELECT from `flight` JOIN `airport` JOIN `airplane` LEFT JOIN `ticket`) and `get_customer_purchased_flights` (SELECT from `purchases` JOIN `ticket` JOIN `flight`).

- **Customer: Purchase ticket**
  - Handler: [aires/routes/customer.py](aires/routes/customer.py)::`customer_purchase`
  - Service: [aires/services/purchase_service.py](aires/services/purchase_service.py)::`create_purchase`
  - Key SQL: SELECT flight capacity/price (JOIN `flight`, `airplane`, LEFT JOIN `ticket` to count sold tickets), SELECT customer existence FROM `customer`, INSERT into `ticket`, INSERT into `purchases`.

- **Customer: Cancel purchase**
  - Handler: [aires/routes/customer.py](aires/routes/customer.py)::`customer_cancel`
  - Service: [aires/services/purchase_service.py](aires/services/purchase_service.py)::`cancel_purchase`
  - Key SQL: SELECT purchase + flight info JOINing `purchases`, `ticket`, `flight` to check timing; DELETE FROM `purchases` and DELETE FROM `ticket` when allowed.

- **Airline Staff: Dashboard (flights list, passengers, customer trips, analytics)**
  - Handler: [aires/routes/staff.py](aires/routes/staff.py)::`staff_dashboard` calls `load_staff_dashboard` in [aires/services/dashboard_service.py](aires/services/dashboard_service.py).
  - Queries: staff dashboards aggregate flights and purchases (SELECTs on `flight`, JOIN `airport`, LEFT JOIN `ticket`, JOIN `airplane`), top destinations (`COUNT(DISTINCT t.ticket_id)` grouped by arrival airport), and other analytics (monthly sums using `purchases` JOIN `ticket` JOIN `flight`).

- **Airline Staff: Add airport / add airplane / create & edit flight**
  - Handler: [aires/routes/staff.py](aires/routes/staff.py)::`staff_add_airport`, `staff_add_airplane`, `staff_create_flight`, `staff_edit_flight`.
  - Key SQL examples: INSERT INTO `city` / INSERT INTO `airport`; INSERT INTO `airplane`; INSERT INTO `flight`; UPDATE `flight` (edit flow uses payload prepared by staff service).

- **Shared helpers**
  - [aires/services/common.py](aires/services/common.py) provides `resolve_airport_code` (SELECT airport_name FROM `airport` WHERE LOWER(airport_name) = LOWER(%s)), `get_airport_list`, `get_airline_list`, and `get_staff_profile` (SELECT from `airline_staff`). These are used across routes for validation and dropdowns.
