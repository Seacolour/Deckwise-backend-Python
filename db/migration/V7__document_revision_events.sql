-- Document revision audit; depends on documents, sessions, and Agent runs.

-- document_revision_events

CREATE TABLE backend_data.document_revision_events (
    id bigint NOT NULL,
    event_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id bigint NOT NULL,
    project_id bigint,
    document_id bigint NOT NULL,
    document_type text,
    canonical_kind text,
    document_event_seq bigint NOT NULL,
    event_type text NOT NULL,
    actor_type text NOT NULL,
    trigger_source text NOT NULL,
    status text DEFAULT 'committed'::text NOT NULL,
    from_revision text,
    to_revision text,
    target_revision text,
    rollback_entry_id bigint,
    rollback_of_event_id bigint,
    document_version_id bigint,
    source_session_id bigint,
    source_message_id bigint,
    source_agent_run_id text,
    source_tool_call_id text,
    source_tool_name text,
    modified_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    touched_pages jsonb DEFAULT '[]'::jsonb NOT NULL,
    summary text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    delete_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_document_revision_events_actor_type CHECK ((actor_type = ANY (ARRAY['user'::text, 'agent'::text, 'system'::text]))),
    CONSTRAINT chk_document_revision_events_deleted_at CHECK (((is_deleted = true) OR (deleted_at IS NULL))),
    CONSTRAINT chk_document_revision_events_event_type CHECK ((event_type = ANY (ARRAY['agent_write'::text, 'agent_rollback_restore'::text, 'user_rollback_restore'::text, 'user_edit_checkpoint'::text, 'publish'::text, 'import'::text, 'system_repair'::text]))),
    CONSTRAINT chk_document_revision_events_from_revision_nonblank CHECK (((from_revision IS NULL) OR (btrim(from_revision) <> ''::text))),
    CONSTRAINT chk_document_revision_events_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT chk_document_revision_events_modified_paths_array CHECK ((jsonb_typeof(modified_paths) = 'array'::text)),
    CONSTRAINT chk_document_revision_events_seq_positive CHECK ((document_event_seq > 0)),
    CONSTRAINT chk_document_revision_events_source_tool_call_id_nonblank CHECK (((source_tool_call_id IS NULL) OR (btrim(source_tool_call_id) <> ''::text))),
    CONSTRAINT chk_document_revision_events_source_tool_name_nonblank CHECK (((source_tool_name IS NULL) OR (btrim(source_tool_name) <> ''::text))),
    CONSTRAINT chk_document_revision_events_status CHECK ((status = ANY (ARRAY['committed'::text, 'noop'::text, 'failed'::text, 'superseded'::text]))),
    CONSTRAINT chk_document_revision_events_target_revision_nonblank CHECK (((target_revision IS NULL) OR (btrim(target_revision) <> ''::text))),
    CONSTRAINT chk_document_revision_events_to_revision_nonblank CHECK (((to_revision IS NULL) OR (btrim(to_revision) <> ''::text))),
    CONSTRAINT chk_document_revision_events_touched_pages_array CHECK ((jsonb_typeof(touched_pages) = 'array'::text)),
    CONSTRAINT chk_document_revision_events_trigger_source CHECK ((trigger_source = ANY (ARRAY['agent_tool'::text, 'frontend_button'::text, 'editor_checkpoint'::text, 'publish_api'::text, 'import_api'::text, 'system_job'::text])))
);

CREATE SEQUENCE backend_data.document_revision_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.document_revision_events_id_seq OWNED BY backend_data.document_revision_events.id;

ALTER TABLE ONLY backend_data.document_revision_events ALTER COLUMN id SET DEFAULT nextval('backend_data.document_revision_events_id_seq'::regclass);

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT uq_document_revision_events_document_seq UNIQUE (document_id, document_event_seq);

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT uq_document_revision_events_uid UNIQUE (event_uid);

CREATE INDEX idx_document_revision_events_agent_run ON backend_data.document_revision_events USING btree (source_agent_run_id, id DESC) WHERE ((source_agent_run_id IS NOT NULL) AND (is_deleted = false));

CREATE INDEX idx_document_revision_events_document_seq ON backend_data.document_revision_events USING btree (document_id, document_event_seq DESC) WHERE (is_deleted = false);

CREATE INDEX idx_document_revision_events_document_time ON backend_data.document_revision_events USING btree (document_id, created_at DESC, id DESC) WHERE (is_deleted = false);

CREATE INDEX idx_document_revision_events_event_type ON backend_data.document_revision_events USING btree (document_id, event_type, created_at DESC, id DESC) WHERE (is_deleted = false);

CREATE INDEX idx_document_revision_events_project_time ON backend_data.document_revision_events USING btree (project_id, created_at DESC, id DESC) WHERE ((project_id IS NOT NULL) AND (is_deleted = false));

CREATE INDEX idx_document_revision_events_rollback_entry ON backend_data.document_revision_events USING btree (rollback_entry_id, id DESC) WHERE ((rollback_entry_id IS NOT NULL) AND (is_deleted = false));

CREATE INDEX idx_document_revision_events_session ON backend_data.document_revision_events USING btree (source_session_id, document_event_seq DESC, id DESC) WHERE ((source_session_id IS NOT NULL) AND (is_deleted = false));

CREATE TRIGGER trg_document_revision_events_updated_at BEFORE UPDATE ON backend_data.document_revision_events FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_document_id_fkey FOREIGN KEY (document_id) REFERENCES backend_data.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES backend_data.document_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_rollback_entry_id_fkey FOREIGN KEY (rollback_entry_id) REFERENCES backend_data.agent_run_document_revisions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_rollback_of_event_id_fkey FOREIGN KEY (rollback_of_event_id) REFERENCES backend_data.document_revision_events(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_source_agent_run_id_fkey FOREIGN KEY (source_agent_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_source_message_id_fkey FOREIGN KEY (source_message_id) REFERENCES backend_data.session_messages(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_source_session_id_fkey FOREIGN KEY (source_session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.document_revision_events
    ADD CONSTRAINT document_revision_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;
