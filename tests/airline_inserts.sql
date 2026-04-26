-- Use the database
USE air_reservation;

-- 1. Populate 'city'
-- Must be first due to airport foreign key constraint
INSERT INTO `city` (`city_name`) VALUES 
('New York'),
('Shanghai'),
('London'),
('Dubai'),
('San Francisco'),
('Tokyo');

-- 2. Populate 'airline'
INSERT INTO `airline` (`airline_name`) VALUES 
('JetBlue'),
('China Eastern'),
('British Airways'),
('Emirates'),
('United');

-- 3. Populate 'airport'
INSERT INTO `airport` (`airport_name`, `airport_city`) VALUES 
('JFK', 'New York'),
('LGA', 'New York'),
('PVG', 'Shanghai'),
('LHR', 'London'),
('DXB', 'Dubai'),
('SFO', 'San Francisco'),
('HND', 'Tokyo');

-- 4. Populate 'airline_staff'
INSERT INTO `airline_staff` (`username`, `password`, `first_name`, `last_name`, `date_of_birth`, `airline_name`, `role`) VALUES 
('jsmith_jb', 'pass123', 'John', 'Smith', '1985-05-12', 'JetBlue', 'admin'),
('ywang_ce', 'cepass456', 'Yan', 'Wang', '1990-08-22', 'China Eastern', 'operator'),
('rwilson_ba', 'bapass789', 'Robert', 'Wilson', '1978-12-01', 'British Airways', 'both'),
('fali_em', 'dxbpass', 'Fatima', 'Ali', '1992-03-15', 'Emirates', 'admin');

-- 5. Populate 'airplane'
INSERT INTO `airplane` (`airline_name`, `airplane_id`, `seat_capacity`) VALUES 
('JetBlue', 101, 150),
('JetBlue', 102, 180),
('China Eastern', 201, 300),
('British Airways', 301, 250),
('Emirates', 401, 450),
('United', 501, 200);

-- 6. Populate 'booking_agent'
INSERT INTO `booking_agent` (`email`, `password`) VALUES 
('travel_pro@gmail.com', 'prosecure1'),
('cheap_flights@yahoo.com', 'cheapie99'),
('global_tours@outlook.com', 'worldtraveler');

-- 7. Populate 'agent_airline_authorization'
INSERT INTO `agent_airline_authorization` (`agent_email`, `airline_name`) VALUES 
('travel_pro@gmail.com', 'JetBlue'),
('travel_pro@gmail.com', 'United'),
('cheap_flights@yahoo.com', 'Emirates'),
('global_tours@outlook.com', 'British Airways');

-- 8. Populate 'customer'
INSERT INTO `customer` (`email`, `name`, `password`, `building_number`, `street`, `city`, `state`, `phone_number`, `passport_number`, `passport_expiration`, `passport_country`, `date_of_birth`) VALUES 
('alice.jones@gmail.com', 'Alice Jones', 'alicepass', '123', 'Main St', 'San Francisco', 'CA', '555-0101', 'AB1234567', '2030-01-01', 'USA', '1995-07-20'),
('bob.lee@163.com', 'Bob Lee', 'bobpass', '88', 'Nanjing Rd', 'Shanghai', 'SH', '13800138000', 'G98765432', '2028-11-15', 'China', '1988-02-14'),
('charlie.d@uk.co', 'Charlie Davis', 'charpass', '10', 'Baker St', 'London', 'UK', '44-20-7946-0958', 'P00099988', '2025-06-30', 'UK', '1975-11-30');

-- 9. Populate 'flight'
-- Dates are set for current/near future relative to typical database usage
INSERT INTO `flight` (`airline_name`, `flight_num`, `departure_airport`, `departure_time`, `arrival_airport`, `arrival_time`, `price`, `status`, `airplane_id`) VALUES 
('JetBlue', 50, 'JFK', '2024-05-01 08:00:00', 'SFO', '2024-05-01 11:30:00', 350.00, 'upcoming', 101),
('China Eastern', 202, 'PVG', '2024-05-02 14:00:00', 'HND', '2024-05-02 17:00:00', 450.00, 'upcoming', 201),
('Emirates', 1, 'DXB', '2024-05-03 23:30:00', 'LHR', '2024-05-04 04:30:00', 1200.00, 'upcoming', 401),
('British Airways', 77, 'LHR', '2024-04-10 10:00:00', 'JFK', '2024-04-10 13:00:00', 800.00, 'delayed', 301);

-- 10. Populate 'ticket'
INSERT INTO `ticket` (`ticket_id`, `airline_name`, `flight_num`) VALUES 
(10001, 'JetBlue', 50),
(10002, 'JetBlue', 50),
(20001, 'China Eastern', 202),
(40001, 'Emirates', 1),
(30001, 'British Airways', 77);

-- 11. Populate 'purchases'
INSERT INTO `purchases` (`ticket_id`, `customer_email`, `booking_agent_email`, `purchase_date`) VALUES 
(10001, 'alice.jones@gmail.com', NULL, '2024-04-01'),
(10002, 'bob.lee@163.com', 'travel_pro@gmail.com', '2024-04-05'),
(20001, 'bob.lee@163.com', NULL, '2024-04-10'),
(40001, 'charlie.d@uk.co', 'cheap_flights@yahoo.com', '2024-04-12');