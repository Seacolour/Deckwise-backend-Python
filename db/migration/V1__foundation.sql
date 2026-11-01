-- Shared schema objects used by every domain.

CREATE SCHEMA IF NOT EXISTS backend_data;

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA backend_data;

-- Historical labels stay readable when this code points at an older database;
-- the Demo exposes only email-code login.
CREATE TYPE backend_data.identity_provider AS ENUM (
    'google',
    'apple',
    'email',
    'github'
);

CREATE FUNCTION backend_data.touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
