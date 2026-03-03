-- Test verileri
INSERT INTO leave_types (name, requires_approval, deducts_from_balance) VALUES 
('Annual Leave', true, true),
('Sick Leave', true, true),
('Unpaid Leave', true, false);

-- Test kullanıcıları
INSERT INTO users (telegram_id, full_name, role, annual_leave_balance) VALUES 
(123456789, 'Admin User', 'hr_admin', 20),
(987654321, 'Employee Test', 'employee', 14),
(555555555, 'Manager Test', 'manager', 15);

-- Manager relationship
UPDATE users SET manager_id = (SELECT id FROM users WHERE telegram_id = 555555555) 
WHERE telegram_id = 987654321;

-- Check data
SELECT 'Leave Types:' as info;
SELECT id, name, requires_approval, deducts_from_balance FROM leave_types;
SELECT 'Users:' as info;
SELECT id, telegram_id, full_name, role, annual_leave_balance, manager_id FROM users;
