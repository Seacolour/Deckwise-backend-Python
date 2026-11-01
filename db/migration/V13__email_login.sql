-- Email login state for the Python backend. The original Java backend used Redis.

CREATE TABLE backend_data.email_login_codes (
    email backend_data.citext PRIMARY KEY,
    code_salt bytea NOT NULL CHECK (octet_length(code_salt) = 16),
    code_hash bytea NOT NULL CHECK (octet_length(code_hash) = 32),
    sent_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0)
);

CREATE INDEX idx_email_login_codes_expires_at
    ON backend_data.email_login_codes (expires_at);

CREATE TABLE backend_data.web_auth_sessions (
    token_hash bytea PRIMARY KEY CHECK (octet_length(token_hash) = 32),
    user_id bigint NOT NULL REFERENCES backend_data.users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX idx_web_auth_sessions_user_id
    ON backend_data.web_auth_sessions (user_id);

CREATE INDEX idx_web_auth_sessions_expires_at
    ON backend_data.web_auth_sessions (expires_at);
