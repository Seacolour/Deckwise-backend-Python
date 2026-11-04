-- OAuth credentials are separate from plugin switches and scoped to one user.
CREATE TABLE backend_data.user_mcp_connections (
    user_id bigint NOT NULL REFERENCES backend_data.users(id) ON DELETE CASCADE,
    provider_id varchar(32) NOT NULL CHECK (provider_id = 'notion'),
    status varchar(32) NOT NULL CHECK (status IN ('authorizing', 'connected', 'reconnect_required')),
    credential_ciphertext bytea NOT NULL,
    nonce bytea NOT NULL CHECK (octet_length(nonce) = 12),
    key_version integer NOT NULL CHECK (key_version > 0),
    workspace_id text,
    workspace_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, provider_id)
);

CREATE TRIGGER trg_user_mcp_connections_updated_at
    BEFORE UPDATE ON backend_data.user_mcp_connections
    FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();
