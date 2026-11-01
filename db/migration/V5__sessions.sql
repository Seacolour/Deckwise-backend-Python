-- Conversations and their messages.

-- sessions

CREATE TABLE backend_data.sessions (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    created_by bigint NOT NULL,
    title text NOT NULL,
    last_user_message text,
    last_active_at timestamp with time zone DEFAULT now(),
    archived boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.sessions_id_seq OWNED BY backend_data.sessions.id;

ALTER TABLE ONLY backend_data.sessions ALTER COLUMN id SET DEFAULT nextval('backend_data.sessions_id_seq'::regclass);

ALTER TABLE ONLY backend_data.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);

CREATE INDEX idx_sessions_project_creator_archived_updated ON backend_data.sessions USING btree (project_id, created_by, archived, is_deleted, updated_at DESC);

CREATE INDEX idx_sessions_project_updated ON backend_data.sessions USING btree (project_id, is_deleted, updated_at DESC);

CREATE TRIGGER trg_sessions_updated_at BEFORE UPDATE ON backend_data.sessions FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.sessions
    ADD CONSTRAINT sessions_created_by_fkey FOREIGN KEY (created_by) REFERENCES backend_data.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.sessions
    ADD CONSTRAINT sessions_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE CASCADE;

-- session_messages

CREATE TABLE backend_data.session_messages (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    seq integer NOT NULL,
    role text NOT NULL,
    type text DEFAULT 'text'::text NOT NULL,
    content text,
    raw_content text,
    parts jsonb,
    name text,
    tool_call_id text,
    metadata jsonb,
    status text DEFAULT 'final'::text NOT NULL,
    token_count integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    CONSTRAINT session_messages_role_check CHECK ((role = ANY (ARRAY['system'::text, 'developer'::text, 'user'::text, 'assistant'::text, 'tool'::text]))),
    CONSTRAINT session_messages_status_check CHECK ((status = ANY (ARRAY['final'::text, 'streaming'::text, 'aborted'::text, 'error'::text]))),
    CONSTRAINT session_messages_type_check CHECK ((type = ANY (ARRAY['text'::text, 'tool_output'::text, 'metadata'::text, 'image'::text])))
);

CREATE SEQUENCE backend_data.session_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.session_messages_id_seq OWNED BY backend_data.session_messages.id;

ALTER TABLE ONLY backend_data.session_messages ALTER COLUMN id SET DEFAULT nextval('backend_data.session_messages_id_seq'::regclass);

ALTER TABLE ONLY backend_data.session_messages
    ADD CONSTRAINT session_messages_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.session_messages
    ADD CONSTRAINT uq_session_messages_seq UNIQUE (session_id, seq);

CREATE TRIGGER trg_session_messages_updated_at BEFORE UPDATE ON backend_data.session_messages FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.session_messages
    ADD CONSTRAINT session_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;
