-- Optional password login for accounts whose email has already been verified.
CREATE TABLE backend_data.user_password_credentials (
    user_id bigint PRIMARY KEY REFERENCES backend_data.users(id) ON DELETE CASCADE,
    password_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TRIGGER trg_user_password_credentials_updated_at
    BEFORE UPDATE ON backend_data.user_password_credentials
    FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TYPE backend_data.identity_provider ADD VALUE 'email_password';
