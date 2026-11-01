-- Accounts, login history, user preferences, check-in, and skill catalog.

-- users

CREATE TABLE backend_data.users (
    id bigint NOT NULL,
    email backend_data.citext,
    email_verified boolean DEFAULT false,
    name text,
    avatar_url text,
    sign_up_provider text DEFAULT 'unknown'::text NOT NULL,
    role text DEFAULT 'user'::text NOT NULL,
    preferred_locale text,
    preferred_time_zone text,
    last_known_country character(2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone,
    is_active boolean DEFAULT true,
    is_deleted boolean DEFAULT false,
    CONSTRAINT users_role_check CHECK ((role = ANY (ARRAY['user'::text, 'admin'::text, 'ban'::text])))
);

CREATE SEQUENCE backend_data.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.users_id_seq OWNED BY backend_data.users.id;

ALTER TABLE ONLY backend_data.users ALTER COLUMN id SET DEFAULT nextval('backend_data.users_id_seq'::regclass);

ALTER TABLE ONLY backend_data.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

ALTER TABLE ONLY backend_data.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON backend_data.users FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

-- user_login_log

CREATE TABLE backend_data.user_login_log (
    id bigint NOT NULL,
    user_id bigint,
    login_time timestamp with time zone DEFAULT now(),
    ip_address text,
    user_agent text,
    provider backend_data.identity_provider,
    success boolean DEFAULT true
);

CREATE SEQUENCE backend_data.user_login_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_login_log_id_seq OWNED BY backend_data.user_login_log.id;

ALTER TABLE ONLY backend_data.user_login_log ALTER COLUMN id SET DEFAULT nextval('backend_data.user_login_log_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_login_log
    ADD CONSTRAINT user_login_log_pkey PRIMARY KEY (id);

CREATE INDEX idx_user_login_log_user_id ON backend_data.user_login_log USING btree (user_id);

ALTER TABLE ONLY backend_data.user_login_log
    ADD CONSTRAINT user_login_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_devices

CREATE TABLE backend_data.user_devices (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    device_token text NOT NULL,
    device_type text NOT NULL,
    environment text DEFAULT 'production'::text,
    last_active_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);

CREATE SEQUENCE backend_data.user_devices_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_devices_id_seq OWNED BY backend_data.user_devices.id;

ALTER TABLE ONLY backend_data.user_devices ALTER COLUMN id SET DEFAULT nextval('backend_data.user_devices_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_devices
    ADD CONSTRAINT user_devices_device_token_environment_key UNIQUE (device_token, environment);

ALTER TABLE ONLY backend_data.user_devices
    ADD CONSTRAINT user_devices_pkey PRIMARY KEY (id);

CREATE INDEX idx_user_devices_user_id ON backend_data.user_devices USING btree (user_id);

ALTER TABLE ONLY backend_data.user_devices
    ADD CONSTRAINT user_devices_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_rules

CREATE TABLE backend_data.user_rules (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    content text NOT NULL,
    enabled boolean DEFAULT true,
    source text DEFAULT 'user'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false
);

CREATE SEQUENCE backend_data.user_rules_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_rules_id_seq OWNED BY backend_data.user_rules.id;

ALTER TABLE ONLY backend_data.user_rules ALTER COLUMN id SET DEFAULT nextval('backend_data.user_rules_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_rules
    ADD CONSTRAINT user_rules_pkey PRIMARY KEY (id);

CREATE INDEX idx_user_rules_user_id ON backend_data.user_rules USING btree (user_id) WHERE (NOT is_deleted);

CREATE TRIGGER trg_user_rules_updated_at BEFORE UPDATE ON backend_data.user_rules FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.user_rules
    ADD CONSTRAINT fk_user_rules_user FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_memories

CREATE TABLE backend_data.user_memories (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    source text DEFAULT 'ai'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false
);

CREATE SEQUENCE backend_data.user_memories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_memories_id_seq OWNED BY backend_data.user_memories.id;

ALTER TABLE ONLY backend_data.user_memories ALTER COLUMN id SET DEFAULT nextval('backend_data.user_memories_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_memories
    ADD CONSTRAINT user_memories_pkey PRIMARY KEY (id);

CREATE INDEX idx_user_memories_user_id ON backend_data.user_memories USING btree (user_id) WHERE (NOT is_deleted);

CREATE TRIGGER trg_user_memories_updated_at BEFORE UPDATE ON backend_data.user_memories FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.user_memories
    ADD CONSTRAINT fk_user_memories_user FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_custom_skills

CREATE TABLE backend_data.user_custom_skills (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    skill_name character varying(128) NOT NULL,
    display_name character varying(256),
    description text,
    content text NOT NULL,
    version character varying(32),
    source_type character varying(32) DEFAULT 'manual'::character varying NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.user_custom_skills_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_custom_skills_id_seq OWNED BY backend_data.user_custom_skills.id;

ALTER TABLE ONLY backend_data.user_custom_skills ALTER COLUMN id SET DEFAULT nextval('backend_data.user_custom_skills_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_custom_skills
    ADD CONSTRAINT user_custom_skills_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX idx_user_custom_skills_unique ON backend_data.user_custom_skills USING btree (user_id, skill_name) WHERE (NOT is_deleted);

CREATE INDEX idx_user_custom_skills_user_enabled ON backend_data.user_custom_skills USING btree (user_id) WHERE ((NOT is_deleted) AND enabled);

CREATE TRIGGER trg_user_custom_skills_updated_at BEFORE UPDATE ON backend_data.user_custom_skills FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.user_custom_skills
    ADD CONSTRAINT fk_user_custom_skills_user FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- skill_registry

CREATE TABLE backend_data.skill_registry (
    id bigint NOT NULL,
    skill_name character varying(64) NOT NULL,
    display_name character varying(128),
    description text,
    category character varying(32) DEFAULT 'general'::character varying NOT NULL,
    system_locked boolean DEFAULT false NOT NULL,
    default_enabled boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    icon character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.skill_registry_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.skill_registry_id_seq OWNED BY backend_data.skill_registry.id;

ALTER TABLE ONLY backend_data.skill_registry ALTER COLUMN id SET DEFAULT nextval('backend_data.skill_registry_id_seq'::regclass);

ALTER TABLE ONLY backend_data.skill_registry
    ADD CONSTRAINT skill_registry_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX idx_skill_registry_name ON backend_data.skill_registry USING btree (skill_name) WHERE (NOT is_deleted);

CREATE TRIGGER trg_skill_registry_updated_at BEFORE UPDATE ON backend_data.skill_registry FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

-- user_skill_settings

CREATE TABLE backend_data.user_skill_settings (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    skill_name character varying(64) NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.user_skill_settings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_skill_settings_id_seq OWNED BY backend_data.user_skill_settings.id;

ALTER TABLE ONLY backend_data.user_skill_settings ALTER COLUMN id SET DEFAULT nextval('backend_data.user_skill_settings_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_skill_settings
    ADD CONSTRAINT user_skill_settings_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX idx_user_skill_settings_unique ON backend_data.user_skill_settings USING btree (user_id, skill_name) WHERE (NOT is_deleted);

CREATE INDEX idx_user_skill_settings_user_id ON backend_data.user_skill_settings USING btree (user_id) WHERE (NOT is_deleted);

CREATE TRIGGER trg_user_skill_settings_updated_at BEFORE UPDATE ON backend_data.user_skill_settings FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.user_skill_settings
    ADD CONSTRAINT fk_user_skill_settings_user FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_checkin_status

CREATE TABLE backend_data.user_checkin_status (
    user_id bigint NOT NULL,
    streak_count integer DEFAULT 0 NOT NULL,
    longest_streak integer DEFAULT 0 NOT NULL,
    last_checkin_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY backend_data.user_checkin_status
    ADD CONSTRAINT user_checkin_status_pkey PRIMARY KEY (user_id);

CREATE TRIGGER trg_user_checkin_status_updated_at BEFORE UPDATE ON backend_data.user_checkin_status FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.user_checkin_status
    ADD CONSTRAINT user_checkin_status_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- user_checkin_log

CREATE TABLE backend_data.user_checkin_log (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    checkin_date date NOT NULL,
    platform text,
    app_version text,
    device_type text,
    device_token text,
    reward_points integer DEFAULT 0 NOT NULL,
    streak_after integer DEFAULT 1 NOT NULL,
    ip_address text,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.user_checkin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.user_checkin_log_id_seq OWNED BY backend_data.user_checkin_log.id;

ALTER TABLE ONLY backend_data.user_checkin_log ALTER COLUMN id SET DEFAULT nextval('backend_data.user_checkin_log_id_seq'::regclass);

ALTER TABLE ONLY backend_data.user_checkin_log
    ADD CONSTRAINT user_checkin_log_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.user_checkin_log
    ADD CONSTRAINT user_checkin_log_user_id_checkin_date_key UNIQUE (user_id, checkin_date);

CREATE INDEX idx_user_checkin_log_user_id ON backend_data.user_checkin_log USING btree (user_id);

ALTER TABLE ONLY backend_data.user_checkin_log
    ADD CONSTRAINT user_checkin_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;
