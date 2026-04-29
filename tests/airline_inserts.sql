USE `air_reservation`;
-- airline_inserts.sql
-- 目标数据库: air_reservation

SET FOREIGN_KEY_CHECKS = 0;

-- 1. 清除现有数据
TRUNCATE TABLE `purchases`;
TRUNCATE TABLE `ticket`;
TRUNCATE TABLE `flight`;
TRUNCATE TABLE `airplane`;
TRUNCATE TABLE `airline_staff`;
TRUNCATE TABLE `agent_airline_authorization`;
TRUNCATE TABLE `booking_agent`;
TRUNCATE TABLE `customer`;
TRUNCATE TABLE `airport`;
TRUNCATE TABLE `city`;
TRUNCATE TABLE `airline`;

SET FOREIGN_KEY_CHECKS = 1;

-- 2. 插入航空公司
INSERT INTO `airline` (`airline_name`) VALUES 
('East'), 
('South'), 
('North');

-- 3. 插入城市
INSERT INTO `city` (`city_name`) VALUES 
('New York'), 
('Tokyo'), 
('Shanghai');

-- 4. 插入机场 (上海有两个)
INSERT INTO `airport` (`airport_name`, `airport_city`) VALUES 
('JFK', 'New York'),
('NRT', 'Tokyo'),
('PVG', 'Shanghai'),
('SHA', 'Shanghai');

-- 5. 插入飞机 (每家公司分配几架飞机)
INSERT INTO `airplane` (`airline_name`, `airplane_id`, `seat_capacity`) VALUES 
('East', 101, 200),
('East', 102, 200),
('South', 201, 150),
('North', 301, 300);

-- 6. 插入航班 (覆盖 2026年 4-5月 前、中、后)
-- 每个航线对确保至少 8 个航班
INSERT INTO `flight` (`airline_name`, `flight_num`, `departure_airport`, `departure_time`, `arrival_airport`, `arrival_time`, `price`, `status`, `airplane_id`) VALUES 
-- 纽约 <-> 上海 (PVG)
('East', 1001, 'JFK', '2026-03-15 08:00:00', 'PVG', '2026-03-16 11:00:00', 1200, 'upcoming', 101),
('East', 1002, 'PVG', '2026-03-20 14:00:00', 'JFK', '2026-03-21 17:00:00', 1150, 'upcoming', 101),
('North', 3001, 'JFK', '2026-04-10 09:00:00', 'PVG', '2026-04-11 12:00:00', 1300, 'upcoming', 301),
('North', 3002, 'PVG', '2026-04-15 22:00:00', 'JFK', '2026-04-16 23:00:00', 1250, 'upcoming', 301),
('East', 1003, 'JFK', '2026-05-05 10:00:00', 'PVG', '2026-05-06 13:00:00', 1400, 'upcoming', 102),
('East', 1004, 'PVG', '2026-05-12 10:00:00', 'JFK', '2026-05-13 13:00:00', 1350, 'upcoming', 102),
('North', 3003, 'JFK', '2026-06-01 08:00:00', 'PVG', '2026-06-02 11:00:00', 1100, 'upcoming', 301),
('North', 3004, 'PVG', '2026-06-10 14:00:00', 'JFK', '2026-06-11 17:00:00', 1050, 'upcoming', 301),

-- 东京 <-> 上海 (SHA)
('South', 2001, 'NRT', '2026-03-10 09:00:00', 'SHA', '2026-03-10 12:00:00', 500, 'upcoming', 201),
('South', 2002, 'SHA', '2026-03-12 15:00:00', 'NRT', '2026-03-12 18:00:00', 480, 'upcoming', 201),
('East', 1005, 'NRT', '2026-04-20 10:00:00', 'SHA', '2026-04-20 13:00:00', 550, 'upcoming', 101),
('East', 1006, 'SHA', '2026-04-25 14:00:00', 'NRT', '2026-04-25 17:00:00', 520, 'upcoming', 101),
('South', 2003, 'NRT', '2026-05-15 08:00:00', 'SHA', '2026-05-15 11:00:00', 600, 'upcoming', 201),
('South', 2004, 'SHA', '2026-05-20 20:00:00', 'NRT', '2026-05-20 23:00:00', 580, 'upcoming', 201),
('East', 1007, 'NRT', '2026-06-05 09:00:00', 'SHA', '2026-06-05 12:00:00', 450, 'upcoming', 102),
('East', 1008, 'SHA', '2026-06-12 15:00:00', 'NRT', '2026-06-12 18:00:00', 430, 'upcoming', 102),

-- 纽约 <-> 东京
('North', 3005, 'JFK', '2026-03-01 10:00:00', 'NRT', '2026-03-02 14:00:00', 1500, 'upcoming', 301),
('North', 3006, 'NRT', '2026-03-05 10:00:00', 'JFK', '2026-03-06 14:00:00', 1450, 'upcoming', 301),
('South', 2005, 'JFK', '2026-04-01 22:00:00', 'NRT', '2026-04-02 02:00:00', 1600, 'upcoming', 201),
('South', 2006, 'NRT', '2026-04-05 22:00:00', 'JFK', '2026-04-06 02:00:00', 1550, 'upcoming', 201),
('North', 3007, 'JFK', '2026-05-10 11:00:00', 'NRT', '2026-05-11 15:00:00', 1700, 'upcoming', 301),
('North', 3008, 'NRT', '2026-05-15 11:00:00', 'JFK', '2026-05-16 15:00:00', 1650, 'upcoming', 301),
('South', 2007, 'JFK', '2026-06-20 08:00:00', 'NRT', '2026-06-21 12:00:00', 1400, 'upcoming', 201),
('South', 2008, 'NRT', '2026-06-25 08:00:00', 'JFK', '2026-06-26 12:00:00', 1350, 'upcoming', 201);

-- 7. 插入用户 (客户)
INSERT INTO `customer` (`email`, `name`, `password`, `building_number`, `street`, `city`, `state`, `phone_number`, `passport_number`, `passport_expiration`, `passport_country`, `date_of_birth`) VALUES 
('alice@example.com', 'Alice Smith', 'pass123', '123', 'Broadway', 'New York', 'NY', '1234567890', 'P12345', '2030-01-01', 'USA', '1990-05-15'),
('bob@example.com', 'Bob Wang', 'bob888', '8', 'Nanjing Rd', 'Shanghai', 'Shanghai', '0987654321', 'E98765', '2028-10-20', 'China', '1985-11-20');

-- 8. 插入票据 (为部分航班生成票据)
INSERT INTO `ticket` (`ticket_id`, `airline_name`, `flight_num`) VALUES 
(50001, 'East', 1001),
(50002, 'South', 2001),
(50003, 'North', 3001),
(50004, 'East', 1003);

-- 9. 插入购买记录
INSERT INTO `purchases` (`ticket_id`, `customer_email`, `booking_agent_email`, `purchase_date`) VALUES 
(50001, 'alice@example.com', NULL, '2026-02-10'),
(50002, 'bob@example.com', NULL, '2026-02-15'),
(50003, 'alice@example.com', NULL, '2026-03-01'),
(50004, 'bob@example.com', NULL, '2026-04-01');

-- 10. 插入员工
INSERT INTO `airline_staff` VALUES ('admin_user', 'pass1', 'John', 'D', '1990-01-01', 'East', 'admin');
INSERT INTO `airline_staff` VALUES ('op_user', 'pass2', 'Jane', 'S', '1992-05-05', 'South', 'operator');
INSERT INTO `airline_staff` VALUES ('both_user', 'pass3', 'Mike', 'L', '1988-10-10', 'North', 'both');

-- --------------------------------------------------------
-- 追加：插入代理商数据
-- --------------------------------------------------------

-- 1. 插入代理商
INSERT INTO `booking_agent` (`email`, `password`) VALUES 
('agent_007@travel.com', 'agentpass123'),
('super_trip@agency.com', 'trippass456');

-- 2. 为代理商添加航空公司授权 (根据 DDL 要求)
-- 授权 agent_007 代理 East 航空，super_trip 代理 North 航空
INSERT INTO `agent_airline_authorization` (`agent_email`, `airline_name`) VALUES 
('agent_007@travel.com', 'East'),
('super_trip@agency.com', 'North');

-- 3. 插入新的机票用于代理购买
INSERT INTO `ticket` (`ticket_id`, `airline_name`, `flight_num`) VALUES 
(60001, 'East', 1001),
(60002, 'North', 3001);

-- 4. 插入通过代理购买的记录 (booking_agent_email 不再为 NULL)
INSERT INTO `purchases` (`ticket_id`, `customer_email`, `booking_agent_email`, `purchase_date`) VALUES 
(60001, 'alice@example.com', 'agent_007@travel.com', '2026-04-15'),
(60002, 'bob@example.com', 'super_trip@agency.com', '2026-04-20');