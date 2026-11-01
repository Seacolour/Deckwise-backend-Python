-- Agent runs, tool/model calls, memory projections, and session run links.

-- agent_runs

CREATE TABLE backend_data.agent_runs (
    run_id text NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint,
    project_id bigint,
    goal text,
    status text DEFAULT 'running'::text NOT NULL,
    model text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    total_model_calls integer DEFAULT 0 NOT NULL,
    total_tool_calls integer DEFAULT 0 NOT NULL,
    total_tool_result_open_calls integer DEFAULT 0 NOT NULL,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    error_message text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY backend_data.agent_runs
    ADD CONSTRAINT agent_runs_pkey PRIMARY KEY (run_id);

CREATE INDEX idx_agent_runs_session_time ON backend_data.agent_runs USING btree (session_id, started_at DESC);

CREATE INDEX idx_agent_runs_user_time ON backend_data.agent_runs USING btree (user_id, started_at DESC);

CREATE TRIGGER trg_agent_runs_updated_at BEFORE UPDATE ON backend_data.agent_runs FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_runs
    ADD CONSTRAINT agent_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_runs
    ADD CONSTRAINT agent_runs_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_runs
    ADD CONSTRAINT agent_runs_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_model_calls

CREATE TABLE backend_data.agent_model_calls (
    id bigint NOT NULL,
    run_id text NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint,
    project_id bigint,
    provider text DEFAULT 'openai'::text NOT NULL,
    call_site text,
    model text,
    response_id text,
    input_items integer,
    estimated_input_chars integer,
    instructions_chars integer,
    tools_count integer,
    max_output_tokens integer,
    service_tier text,
    attempt integer,
    success boolean,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    elapsed_ms integer,
    error_type text,
    error_message text,
    raw_usage jsonb,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_model_calls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_model_calls_id_seq OWNED BY backend_data.agent_model_calls.id;

ALTER TABLE ONLY backend_data.agent_model_calls ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_model_calls_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_model_calls
    ADD CONSTRAINT agent_model_calls_pkey PRIMARY KEY (id);

CREATE INDEX idx_agent_model_calls_run_time ON backend_data.agent_model_calls USING btree (run_id, created_at);

CREATE INDEX idx_agent_model_calls_user_time ON backend_data.agent_model_calls USING btree (user_id, created_at DESC);

ALTER TABLE ONLY backend_data.agent_model_calls
    ADD CONSTRAINT agent_model_calls_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_model_calls
    ADD CONSTRAINT agent_model_calls_run_id_fkey FOREIGN KEY (run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_model_calls
    ADD CONSTRAINT agent_model_calls_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_model_calls
    ADD CONSTRAINT agent_model_calls_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_tool_calls

CREATE TABLE backend_data.agent_tool_calls (
    id bigint NOT NULL,
    run_id text NOT NULL,
    call_id text NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint,
    project_id bigint,
    tool_name text NOT NULL,
    arguments_json text,
    status text NOT NULL,
    success boolean,
    result_summary text,
    error_code text,
    result_chars integer,
    read_key text,
    duplicate_of_call_id text,
    cost_ms integer,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_tool_calls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_tool_calls_id_seq OWNED BY backend_data.agent_tool_calls.id;

ALTER TABLE ONLY backend_data.agent_tool_calls ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_tool_calls_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT uq_agent_tool_calls_run_call UNIQUE (run_id, call_id);

CREATE INDEX idx_agent_tool_calls_run_time ON backend_data.agent_tool_calls USING btree (run_id, created_at);

CREATE INDEX idx_agent_tool_calls_tool_time ON backend_data.agent_tool_calls USING btree (tool_name, created_at DESC);

CREATE TRIGGER trg_agent_tool_calls_updated_at BEFORE UPDATE ON backend_data.agent_tool_calls FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_run_id_fkey FOREIGN KEY (run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_tool_results

CREATE TABLE backend_data.agent_tool_results (
    id bigint NOT NULL,
    run_id text NOT NULL,
    call_id text NOT NULL,
    tool_name text NOT NULL,
    result_json jsonb,
    result_chars integer,
    compacted_for_model boolean DEFAULT false NOT NULL,
    stored_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_tool_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_tool_results_id_seq OWNED BY backend_data.agent_tool_results.id;

ALTER TABLE ONLY backend_data.agent_tool_results ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_tool_results_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_tool_results
    ADD CONSTRAINT agent_tool_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_tool_results
    ADD CONSTRAINT uq_agent_tool_results_run_call UNIQUE (run_id, call_id);

CREATE INDEX idx_agent_tool_results_run_time ON backend_data.agent_tool_results USING btree (run_id, stored_at);

CREATE TRIGGER trg_agent_tool_results_updated_at BEFORE UPDATE ON backend_data.agent_tool_results FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_tool_results
    ADD CONSTRAINT agent_tool_results_run_id_fkey FOREIGN KEY (run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

-- agent_run_ledger_snapshots

CREATE TABLE backend_data.agent_run_ledger_snapshots (
    run_id text NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint,
    project_id bigint,
    ledger_json jsonb NOT NULL,
    model_calls integer DEFAULT 0 NOT NULL,
    tool_calls integer DEFAULT 0 NOT NULL,
    tool_result_open_calls integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY backend_data.agent_run_ledger_snapshots
    ADD CONSTRAINT agent_run_ledger_snapshots_pkey PRIMARY KEY (run_id);

CREATE INDEX idx_agent_run_ledger_session_time ON backend_data.agent_run_ledger_snapshots USING btree (session_id, updated_at DESC);

CREATE TRIGGER trg_agent_run_ledger_snapshots_updated_at BEFORE UPDATE ON backend_data.agent_run_ledger_snapshots FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_run_ledger_snapshots
    ADD CONSTRAINT agent_run_ledger_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_run_ledger_snapshots
    ADD CONSTRAINT agent_run_ledger_snapshots_run_id_fkey FOREIGN KEY (run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_run_ledger_snapshots
    ADD CONSTRAINT agent_run_ledger_snapshots_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_run_ledger_snapshots
    ADD CONSTRAINT agent_run_ledger_snapshots_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_task_progress

CREATE TABLE backend_data.agent_task_progress (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    project_scope_key text DEFAULT 'none'::text NOT NULL,
    task_key text DEFAULT 'default'::text NOT NULL,
    projection_json jsonb NOT NULL,
    source_run_id text,
    source_updated_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_task_progress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_task_progress_id_seq OWNED BY backend_data.agent_task_progress.id;

ALTER TABLE ONLY backend_data.agent_task_progress ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_task_progress_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT agent_task_progress_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT uq_agent_task_progress_scope UNIQUE (user_id, session_id, project_scope_key, task_key);

CREATE INDEX idx_agent_task_progress_expires ON backend_data.agent_task_progress USING btree (expires_at) WHERE (expires_at IS NOT NULL);

CREATE INDEX idx_agent_task_progress_session_time ON backend_data.agent_task_progress USING btree (user_id, session_id, project_scope_key, updated_at DESC);

CREATE TRIGGER trg_agent_task_progress_updated_at BEFORE UPDATE ON backend_data.agent_task_progress FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT agent_task_progress_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT agent_task_progress_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT agent_task_progress_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_task_progress
    ADD CONSTRAINT agent_task_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_artifact_projection

CREATE TABLE backend_data.agent_artifact_projection (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    project_scope_key text DEFAULT 'none'::text NOT NULL,
    artifact_key text DEFAULT 'session_artifacts'::text NOT NULL,
    document_id bigint,
    file_id bigint,
    latest_revision text,
    projection_json jsonb NOT NULL,
    source_run_id text,
    source_updated_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_artifact_projection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_artifact_projection_id_seq OWNED BY backend_data.agent_artifact_projection.id;

ALTER TABLE ONLY backend_data.agent_artifact_projection ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_artifact_projection_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT agent_artifact_projection_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT uq_agent_artifact_projection_scope UNIQUE (user_id, session_id, project_scope_key, artifact_key);

CREATE INDEX idx_agent_artifact_projection_document ON backend_data.agent_artifact_projection USING btree (document_id, updated_at DESC) WHERE (document_id IS NOT NULL);

CREATE INDEX idx_agent_artifact_projection_expires ON backend_data.agent_artifact_projection USING btree (expires_at) WHERE (expires_at IS NOT NULL);

CREATE INDEX idx_agent_artifact_projection_session_time ON backend_data.agent_artifact_projection USING btree (user_id, session_id, project_scope_key, updated_at DESC);

CREATE TRIGGER trg_agent_artifact_projection_updated_at BEFORE UPDATE ON backend_data.agent_artifact_projection FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT agent_artifact_projection_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT agent_artifact_projection_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT agent_artifact_projection_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_artifact_projection
    ADD CONSTRAINT agent_artifact_projection_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_artifact_views

CREATE TABLE backend_data.agent_artifact_views (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    project_scope_key text DEFAULT 'none'::text NOT NULL,
    view_key text NOT NULL,
    document_id bigint,
    file_id bigint,
    tool_name text,
    view_type text,
    read_key text,
    revision text,
    status text,
    result_chars integer,
    projection_json jsonb NOT NULL,
    source_run_id text,
    source_call_id text,
    source_updated_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.agent_artifact_views_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_artifact_views_id_seq OWNED BY backend_data.agent_artifact_views.id;

ALTER TABLE ONLY backend_data.agent_artifact_views ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_artifact_views_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT agent_artifact_views_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT uq_agent_artifact_views_scope UNIQUE (user_id, session_id, project_scope_key, view_key);

CREATE INDEX idx_agent_artifact_views_document_status ON backend_data.agent_artifact_views USING btree (document_id, status, updated_at DESC) WHERE (document_id IS NOT NULL);

CREATE INDEX idx_agent_artifact_views_expires ON backend_data.agent_artifact_views USING btree (expires_at) WHERE (expires_at IS NOT NULL);

CREATE INDEX idx_agent_artifact_views_session_time ON backend_data.agent_artifact_views USING btree (user_id, session_id, project_scope_key, updated_at DESC);

CREATE TRIGGER trg_agent_artifact_views_updated_at BEFORE UPDATE ON backend_data.agent_artifact_views FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT agent_artifact_views_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT agent_artifact_views_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT agent_artifact_views_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_artifact_views
    ADD CONSTRAINT agent_artifact_views_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_context_compactions

CREATE TABLE backend_data.agent_context_compactions (
    id bigint NOT NULL,
    compaction_uid uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    source_agent_run_id text,
    provider text DEFAULT 'openai'::text NOT NULL,
    model text,
    mode text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    context_format text DEFAULT 'responses_compacted_window_v1'::text NOT NULL,
    source_first_seq integer,
    source_last_seq integer,
    source_first_item_idx integer,
    source_last_item_idx integer,
    instructions_hash text,
    input_fingerprint text,
    compact_threshold integer,
    compacted_input_json jsonb,
    compacted_item_count integer,
    estimated_input_chars integer,
    estimated_saved_chars integer,
    response_id text,
    previous_response_id text,
    raw_usage jsonb,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_type text,
    error_message text,
    expires_at timestamp with time zone,
    superseded_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_agent_context_compactions_active_superseded_at CHECK ((((status = 'active'::text) AND (superseded_at IS NULL)) OR ((status = 'superseded'::text) AND (superseded_at IS NOT NULL)) OR (status = ANY (ARRAY['expired'::text, 'failed'::text])))),
    CONSTRAINT chk_agent_context_compactions_compact_threshold_positive CHECK (((compact_threshold IS NULL) OR (compact_threshold > 0))),
    CONSTRAINT chk_agent_context_compactions_context_format_nonblank CHECK ((btrim(context_format) <> ''::text)),
    CONSTRAINT chk_agent_context_compactions_error_type_nonblank CHECK (((error_type IS NULL) OR (btrim(error_type) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_estimated_chars_nonnegative CHECK ((((estimated_input_chars IS NULL) OR (estimated_input_chars >= 0)) AND ((estimated_saved_chars IS NULL) OR (estimated_saved_chars >= 0)))),
    CONSTRAINT chk_agent_context_compactions_input_fingerprint_nonblank CHECK (((input_fingerprint IS NULL) OR (btrim(input_fingerprint) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_instructions_hash_nonblank CHECK (((instructions_hash IS NULL) OR (btrim(instructions_hash) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_item_count_nonnegative CHECK (((compacted_item_count IS NULL) OR (compacted_item_count >= 0))),
    CONSTRAINT chk_agent_context_compactions_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT chk_agent_context_compactions_mode CHECK ((mode = ANY (ARRAY['auto'::text, 'manual'::text]))),
    CONSTRAINT chk_agent_context_compactions_model_nonblank CHECK (((model IS NULL) OR (btrim(model) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_previous_response_id_nonblank CHECK (((previous_response_id IS NULL) OR (btrim(previous_response_id) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_provider CHECK ((provider = 'openai'::text)),
    CONSTRAINT chk_agent_context_compactions_raw_usage_object CHECK (((raw_usage IS NULL) OR (jsonb_typeof(raw_usage) = 'object'::text))),
    CONSTRAINT chk_agent_context_compactions_response_id_nonblank CHECK (((response_id IS NULL) OR (btrim(response_id) <> ''::text))),
    CONSTRAINT chk_agent_context_compactions_source_item_idx_nonnegative CHECK ((((source_first_item_idx IS NULL) OR (source_first_item_idx >= 0)) AND ((source_last_item_idx IS NULL) OR (source_last_item_idx >= 0)))),
    CONSTRAINT chk_agent_context_compactions_source_item_idx_range CHECK (((source_first_item_idx IS NULL) OR (source_last_item_idx IS NULL) OR (source_first_item_idx <= source_last_item_idx))),
    CONSTRAINT chk_agent_context_compactions_source_seq_positive CHECK ((((source_first_seq IS NULL) OR (source_first_seq > 0)) AND ((source_last_seq IS NULL) OR (source_last_seq > 0)))),
    CONSTRAINT chk_agent_context_compactions_source_seq_range CHECK (((source_first_seq IS NULL) OR (source_last_seq IS NULL) OR (source_first_seq <= source_last_seq))),
    CONSTRAINT chk_agent_context_compactions_status CHECK ((status = ANY (ARRAY['active'::text, 'superseded'::text, 'expired'::text, 'failed'::text]))),
    CONSTRAINT chk_agent_context_compactions_window_required CHECK (((status = 'failed'::text) OR (compacted_input_json IS NOT NULL))),
    CONSTRAINT chk_agent_context_compactions_window_shape CHECK (((compacted_input_json IS NULL) OR (jsonb_typeof(compacted_input_json) = ANY (ARRAY['object'::text, 'array'::text]))))
);

CREATE SEQUENCE backend_data.agent_context_compactions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_context_compactions_id_seq OWNED BY backend_data.agent_context_compactions.id;

ALTER TABLE ONLY backend_data.agent_context_compactions ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_context_compactions_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT agent_context_compactions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT uq_agent_context_compactions_uid UNIQUE (compaction_uid);

CREATE INDEX idx_agent_context_compactions_agent_run ON backend_data.agent_context_compactions USING btree (source_agent_run_id, created_at DESC, id DESC) WHERE (source_agent_run_id IS NOT NULL);

CREATE INDEX idx_agent_context_compactions_project_time ON backend_data.agent_context_compactions USING btree (project_id, created_at DESC, id DESC) WHERE (project_id IS NOT NULL);

CREATE INDEX idx_agent_context_compactions_response_id ON backend_data.agent_context_compactions USING btree (response_id) WHERE (response_id IS NOT NULL);

CREATE INDEX idx_agent_context_compactions_session_active ON backend_data.agent_context_compactions USING btree (session_id, provider, created_at DESC, id DESC) WHERE (status = 'active'::text);

CREATE INDEX idx_agent_context_compactions_session_source_seq ON backend_data.agent_context_compactions USING btree (session_id, source_last_seq DESC, id DESC) WHERE (source_last_seq IS NOT NULL);

CREATE INDEX idx_agent_context_compactions_session_time ON backend_data.agent_context_compactions USING btree (session_id, created_at DESC, id DESC);

CREATE INDEX idx_agent_context_compactions_user_time ON backend_data.agent_context_compactions USING btree (user_id, created_at DESC, id DESC);

CREATE UNIQUE INDEX uq_agent_context_compactions_active_session_provider ON backend_data.agent_context_compactions USING btree (session_id, provider) WHERE (status = 'active'::text);

CREATE TRIGGER trg_agent_context_compactions_updated_at BEFORE UPDATE ON backend_data.agent_context_compactions FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT agent_context_compactions_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT agent_context_compactions_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT agent_context_compactions_source_agent_run_id_fkey FOREIGN KEY (source_agent_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_context_compactions
    ADD CONSTRAINT agent_context_compactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- agent_run_document_revisions

CREATE TABLE backend_data.agent_run_document_revisions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    agent_run_id text NOT NULL,
    document_id bigint NOT NULL,
    document_type text,
    canonical_kind text,
    before_revision text,
    after_revision text,
    before_revision_source text,
    after_revision_source text,
    first_write_call_id text,
    last_write_call_id text,
    first_write_tool_name text,
    last_write_tool_name text,
    write_count integer DEFAULT 0 NOT NULL,
    modified_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    touched_pages jsonb DEFAULT '[]'::jsonb NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    rollback_visible boolean DEFAULT false NOT NULL,
    rollback_disabled_reason text,
    source text DEFAULT 'agent'::text NOT NULL,
    first_write_at timestamp with time zone,
    last_write_at timestamp with time zone,
    completed_at timestamp with time zone,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    delete_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_agent_run_document_revisions_deleted_at CHECK (((is_deleted = true) OR (deleted_at IS NULL))),
    CONSTRAINT chk_agent_run_document_revisions_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT chk_agent_run_document_revisions_modified_paths_array CHECK ((jsonb_typeof(modified_paths) = 'array'::text)),
    CONSTRAINT chk_agent_run_document_revisions_rollback_ready CHECK (((rollback_visible = false) OR ((before_revision IS NOT NULL) AND (btrim(before_revision) <> ''::text) AND (after_revision IS NOT NULL) AND (btrim(after_revision) <> ''::text) AND (before_revision <> after_revision) AND (is_deleted = false)))),
    CONSTRAINT chk_agent_run_document_revisions_source CHECK ((source = 'agent'::text)),
    CONSTRAINT chk_agent_run_document_revisions_status CHECK ((status = ANY (ARRAY['running'::text, 'changed'::text, 'unchanged'::text, 'failed'::text, 'rolled_back'::text, 'superseded'::text]))),
    CONSTRAINT chk_agent_run_document_revisions_touched_pages_array CHECK ((jsonb_typeof(touched_pages) = 'array'::text)),
    CONSTRAINT chk_agent_run_document_revisions_write_count CHECK ((write_count >= 0))
);

CREATE SEQUENCE backend_data.agent_run_document_revisions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.agent_run_document_revisions_id_seq OWNED BY backend_data.agent_run_document_revisions.id;

ALTER TABLE ONLY backend_data.agent_run_document_revisions ALTER COLUMN id SET DEFAULT nextval('backend_data.agent_run_document_revisions_id_seq'::regclass);

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT uq_agent_run_document_revisions_run_document UNIQUE (agent_run_id, document_id);

CREATE INDEX idx_agent_run_document_revisions_agent_run ON backend_data.agent_run_document_revisions USING btree (agent_run_id, id DESC) WHERE (is_deleted = false);

CREATE INDEX idx_agent_run_document_revisions_document_rollback ON backend_data.agent_run_document_revisions USING btree (document_id, last_write_at DESC, id DESC) WHERE ((rollback_visible = true) AND (is_deleted = false));

CREATE INDEX idx_agent_run_document_revisions_project_time ON backend_data.agent_run_document_revisions USING btree (project_id, last_write_at DESC, id DESC) WHERE ((project_id IS NOT NULL) AND (is_deleted = false));

CREATE INDEX idx_agent_run_document_revisions_session_time ON backend_data.agent_run_document_revisions USING btree (session_id, last_write_at DESC, id DESC) WHERE (is_deleted = false);

CREATE TRIGGER trg_agent_run_document_revisions_updated_at BEFORE UPDATE ON backend_data.agent_run_document_revisions FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_document_id_fkey FOREIGN KEY (document_id) REFERENCES backend_data.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.agent_run_document_revisions
    ADD CONSTRAINT agent_run_document_revisions_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- session_agent_runs

CREATE TABLE backend_data.session_agent_runs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint NOT NULL,
    project_id bigint,
    agent_run_id text NOT NULL,
    user_message_id bigint,
    assistant_message_start_id bigint,
    assistant_message_end_id bigint,
    first_message_seq integer,
    last_message_seq integer,
    status text DEFAULT 'running'::text NOT NULL,
    mapping_source text DEFAULT 'backend_stream'::text NOT NULL,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    delete_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_session_agent_runs_deleted_at CHECK (((is_deleted = true) OR (deleted_at IS NULL))),
    CONSTRAINT chk_session_agent_runs_mapping_source_nonblank CHECK ((btrim(mapping_source) <> ''::text)),
    CONSTRAINT chk_session_agent_runs_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT chk_session_agent_runs_seq_range CHECK (((first_message_seq IS NULL) OR (last_message_seq IS NULL) OR (first_message_seq <= last_message_seq))),
    CONSTRAINT chk_session_agent_runs_status CHECK ((status = ANY (ARRAY['running'::text, 'completed'::text, 'aborted'::text, 'error'::text, 'cancelled'::text])))
);

CREATE SEQUENCE backend_data.session_agent_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.session_agent_runs_id_seq OWNED BY backend_data.session_agent_runs.id;

ALTER TABLE ONLY backend_data.session_agent_runs ALTER COLUMN id SET DEFAULT nextval('backend_data.session_agent_runs_id_seq'::regclass);

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT uq_session_agent_runs_agent_run UNIQUE (agent_run_id);

CREATE INDEX idx_session_agent_runs_project_time ON backend_data.session_agent_runs USING btree (project_id, started_at DESC, id DESC) WHERE ((project_id IS NOT NULL) AND (is_deleted = false));

CREATE INDEX idx_session_agent_runs_session_seq ON backend_data.session_agent_runs USING btree (session_id, first_message_seq, last_message_seq) WHERE (is_deleted = false);

CREATE INDEX idx_session_agent_runs_user_message ON backend_data.session_agent_runs USING btree (user_message_id) WHERE (user_message_id IS NOT NULL);

CREATE INDEX idx_session_agent_runs_user_time ON backend_data.session_agent_runs USING btree (user_id, started_at DESC, id DESC) WHERE (is_deleted = false);

CREATE TRIGGER trg_session_agent_runs_updated_at BEFORE UPDATE ON backend_data.session_agent_runs FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES backend_data.agent_runs(run_id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_assistant_message_end_id_fkey FOREIGN KEY (assistant_message_end_id) REFERENCES backend_data.session_messages(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_assistant_message_start_id_fkey FOREIGN KEY (assistant_message_start_id) REFERENCES backend_data.session_messages(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.session_agent_runs
    ADD CONSTRAINT session_agent_runs_user_message_id_fkey FOREIGN KEY (user_message_id) REFERENCES backend_data.session_messages(id) ON DELETE SET NULL;
