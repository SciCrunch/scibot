-- scibot-admin scibot_test
-- CONNECT TO :database USER "scibot-admin";

GRANT CONNECT ON DATABASE :database TO "scibot-user";
GRANT USAGE ON SCHEMA scibot TO "scibot-user";

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA scibot TO "scibot-user";  -- tables includes views
GRANT USAGE ON ALL SEQUENCES IN SCHEMA scibot TO "scibot-user";
