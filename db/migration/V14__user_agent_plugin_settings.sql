-- Per-user switches for repository-approved MCP and Skill plugins.
CREATE TABLE backend_data.user_agent_plugin_settings (
    user_id bigint NOT NULL REFERENCES backend_data.users(id) ON DELETE CASCADE,
    plugin_id varchar(80) NOT NULL,
    enabled boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (user_id, plugin_id)
);

CREATE TRIGGER trg_user_agent_plugin_settings_updated_at
    BEFORE UPDATE ON backend_data.user_agent_plugin_settings
    FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();
