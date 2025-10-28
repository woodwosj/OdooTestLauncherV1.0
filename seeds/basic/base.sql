-- Seed baseline data for disposable Odoo databases.
-- Adds a smoke-test user linked to the default company.

WITH company AS (
    SELECT id FROM res_company ORDER BY id LIMIT 1
)
INSERT INTO res_partner (name, company_id, email, create_uid, write_uid, create_date, write_date)
SELECT 'Launcher Admin', company.id, 'admin@example.com', 1, 1, NOW(), NOW()
FROM company
ON CONFLICT DO NOTHING;
