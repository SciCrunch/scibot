-- postgres postgres
-- CONNECT TO postgres USER postgres;

DO
$body$
BEGIN
    IF NOT EXISTS ( SELECT * FROM pg_catalog.pg_user
        WHERE usename = 'scibot-user') THEN
        CREATE ROLE "scibot-user" LOGIN
        NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS ( SELECT * FROM pg_catalog.pg_user
        WHERE usename = 'scibot-admin') THEN
        CREATE ROLE "scibot-admin" LOGIN
        NOSUPERUSER INHERIT NOCREATEDB NOCREATEROLE;
    END IF;
END;
$body$ language plpgsql;

-- postgres postgres

ALTER ROLE "scibot-admin" SET search_path = scibot, public;
ALTER ROLE "scibot-user" SET search_path = scibot, public;

-- postgres postgres

DROP DATABASE IF EXISTS :database;

-- postgres postgres

CREATE DATABASE :database -- scibot
    WITH OWNER = 'scibot-admin'
    ENCODING = 'UTF8'
    TABLESPACE = pg_default
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    CONNECTION LIMIT = -1;

