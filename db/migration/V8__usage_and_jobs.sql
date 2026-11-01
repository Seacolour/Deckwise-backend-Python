-- AI usage observation and background jobs.

-- ai_usage_ledger

CREATE TABLE backend_data.ai_usage_ledger (
    id bigint NOT NULL,
    usage_key text NOT NULL,
    usage_source text NOT NULL,
    user_id bigint NOT NULL,
    session_id bigint,
    project_id bigint,
    feature_type text,
    report_status text NOT NULL,
    settlement_key text NOT NULL,
    provider text NOT NULL,
    provider_request_id text,
    requested_model text,
    actual_model text,
    success boolean,
    input_tokens integer,
    output_tokens integer,
    cached_tokens integer,
    reasoning_tokens integer,
    total_tokens integer,
    latency_ms integer,
    billable_input_tokens integer,
    billable_cached_tokens integer,
    billable_output_tokens integer,
    currency character(3),
    input_rate_micros_per_million bigint,
    cached_input_rate_micros_per_million bigint,
    output_rate_micros_per_million bigint,
    estimated_input_cost_micros bigint,
    estimated_cached_cost_micros bigint,
    estimated_output_cost_micros bigint,
    estimated_total_cost_micros bigint,
    raw_usage jsonb,
    metadata jsonb,
    settled_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE backend_data.ai_usage_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.ai_usage_ledger_id_seq OWNED BY backend_data.ai_usage_ledger.id;

ALTER TABLE ONLY backend_data.ai_usage_ledger ALTER COLUMN id SET DEFAULT nextval('backend_data.ai_usage_ledger_id_seq'::regclass);

ALTER TABLE ONLY backend_data.ai_usage_ledger
    ADD CONSTRAINT ai_usage_ledger_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.ai_usage_ledger
    ADD CONSTRAINT ai_usage_ledger_usage_key_key UNIQUE (usage_key);

CREATE INDEX idx_ai_usage_ledger_settlement ON backend_data.ai_usage_ledger USING btree (settlement_key, settled_at DESC);

CREATE INDEX idx_ai_usage_ledger_source_time ON backend_data.ai_usage_ledger USING btree (usage_source, settled_at DESC);

CREATE INDEX idx_ai_usage_ledger_user_time ON backend_data.ai_usage_ledger USING btree (user_id, settled_at DESC);

CREATE TRIGGER trg_ai_usage_ledger_updated_at BEFORE UPDATE ON backend_data.ai_usage_ledger FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.ai_usage_ledger
    ADD CONSTRAINT ai_usage_ledger_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.ai_usage_ledger
    ADD CONSTRAINT ai_usage_ledger_session_id_fkey FOREIGN KEY (session_id) REFERENCES backend_data.sessions(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.ai_usage_ledger
    ADD CONSTRAINT ai_usage_ledger_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- background_jobs

CREATE TABLE backend_data.background_jobs (
    id bigint NOT NULL,
    job_type text NOT NULL,
    dedup_key text,
    status text DEFAULT 'pending'::text NOT NULL,
    priority integer DEFAULT 0 NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    result jsonb DEFAULT '{}'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    next_run_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_by text,
    locked_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_background_jobs_attempts CHECK (((attempts >= 0) AND (max_attempts > 0) AND (attempts <= max_attempts))),
    CONSTRAINT chk_background_jobs_dedup_key_nonblank CHECK (((dedup_key IS NULL) OR (btrim(dedup_key) <> ''::text))),
    CONSTRAINT chk_background_jobs_lock_state CHECK ((((status = 'running'::text) AND (locked_by IS NOT NULL) AND (locked_at IS NOT NULL)) OR (status <> 'running'::text))),
    CONSTRAINT chk_background_jobs_metadata_object CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT chk_background_jobs_payload_object CHECK ((jsonb_typeof(payload) = 'object'::text)),
    CONSTRAINT chk_background_jobs_result_object CHECK ((jsonb_typeof(result) = 'object'::text)),
    CONSTRAINT chk_background_jobs_status CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'succeeded'::text, 'failed'::text, 'dead'::text, 'cancelled'::text]))),
    CONSTRAINT chk_background_jobs_type_nonblank CHECK ((btrim(job_type) <> ''::text))
);

CREATE SEQUENCE backend_data.background_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.background_jobs_id_seq OWNED BY backend_data.background_jobs.id;

ALTER TABLE ONLY backend_data.background_jobs ALTER COLUMN id SET DEFAULT nextval('backend_data.background_jobs_id_seq'::regclass);

ALTER TABLE ONLY backend_data.background_jobs
    ADD CONSTRAINT background_jobs_pkey PRIMARY KEY (id);

CREATE INDEX idx_background_jobs_created_by_created ON backend_data.background_jobs USING btree (created_by, created_at DESC) WHERE (created_by IS NOT NULL);

CREATE INDEX idx_background_jobs_pending_due ON backend_data.background_jobs USING btree (next_run_at, priority DESC, id) WHERE (status = 'pending'::text);

CREATE INDEX idx_background_jobs_running_locked ON backend_data.background_jobs USING btree (locked_at, id) WHERE (status = 'running'::text);

CREATE INDEX idx_background_jobs_type_status_updated ON backend_data.background_jobs USING btree (job_type, status, updated_at DESC);

CREATE UNIQUE INDEX uq_background_jobs_active_dedup ON backend_data.background_jobs USING btree (job_type, dedup_key) WHERE ((dedup_key IS NOT NULL) AND (status = ANY (ARRAY['pending'::text, 'running'::text])));

CREATE TRIGGER trg_background_jobs_updated_at BEFORE UPDATE ON backend_data.background_jobs FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.background_jobs
    ADD CONSTRAINT background_jobs_created_by_fkey FOREIGN KEY (created_by) REFERENCES backend_data.users(id) ON DELETE SET NULL;
