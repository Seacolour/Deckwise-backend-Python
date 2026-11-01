-- Per-user BYOK credentials. Only allowlisted provider IDs are accepted at both API and DB layers.
CREATE TABLE backend_data.user_model_credentials (
    user_id bigint NOT NULL REFERENCES backend_data.users(id) ON DELETE CASCADE,
    provider_id varchar(32) NOT NULL CHECK (provider_id IN ('openai', 'deepseek')),
    ciphertext bytea NOT NULL,
    nonce bytea NOT NULL CHECK (octet_length(nonce) = 12),
    key_version integer NOT NULL CHECK (key_version > 0),
    key_suffix varchar(4) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (user_id, provider_id)
);

CREATE TRIGGER trg_user_model_credentials_updated_at
    BEFORE UPDATE ON backend_data.user_model_credentials
    FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();
