-- Projects, file storage, file access, and derived media.

-- projects

CREATE TABLE backend_data.projects (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    name text NOT NULL,
    description text,
    cover_image text,
    tags text[],
    archived boolean DEFAULT false NOT NULL,
    last_active_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.projects_id_seq OWNED BY backend_data.projects.id;

ALTER TABLE ONLY backend_data.projects ALTER COLUMN id SET DEFAULT nextval('backend_data.projects_id_seq'::regclass);

ALTER TABLE ONLY backend_data.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);

CREATE INDEX idx_projects_owner_archived ON backend_data.projects USING btree (owner_id, archived, is_deleted);

CREATE TRIGGER trg_projects_updated_at BEFORE UPDATE ON backend_data.projects FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.projects
    ADD CONSTRAINT projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- object_storage_files

CREATE TABLE backend_data.object_storage_files (
    id bigint NOT NULL,
    owner_user_id bigint NOT NULL,
    source_type text DEFAULT 'generated'::text NOT NULL,
    source_key text NOT NULL,
    storage_type text DEFAULT 'r2'::text NOT NULL,
    bucket text NOT NULL,
    object_key text NOT NULL,
    public_domain text,
    public_path text,
    mime_type text,
    file_ext text,
    size_bytes bigint DEFAULT 0 NOT NULL,
    original_name text,
    etag text,
    version_id text,
    last_modified timestamp with time zone,
    status text DEFAULT 'available'::text NOT NULL,
    source_id text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    storage_channel text DEFAULT 'public'::text NOT NULL,
    visibility text DEFAULT 'public'::text NOT NULL,
    CONSTRAINT chk_object_storage_files_storage_channel CHECK ((storage_channel = ANY (ARRAY['public'::text, 'private'::text]))),
    CONSTRAINT chk_object_storage_files_visibility CHECK ((visibility = ANY (ARRAY['public'::text, 'private'::text]))),
    CONSTRAINT object_storage_files_size_bytes_check CHECK ((size_bytes >= 0)),
    CONSTRAINT object_storage_files_source_key_check CHECK ((length(source_key) = 64)),
    CONSTRAINT object_storage_files_status_check CHECK ((status = ANY (ARRAY['available'::text, 'stale'::text, 'deleted'::text]))),
    CONSTRAINT object_storage_files_storage_type_check CHECK ((storage_type = 'r2'::text))
);

CREATE SEQUENCE backend_data.object_storage_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.object_storage_files_id_seq OWNED BY backend_data.object_storage_files.id;

ALTER TABLE ONLY backend_data.object_storage_files ALTER COLUMN id SET DEFAULT nextval('backend_data.object_storage_files_id_seq'::regclass);

ALTER TABLE ONLY backend_data.object_storage_files
    ADD CONSTRAINT object_storage_files_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.object_storage_files
    ADD CONSTRAINT uq_object_storage_files_object UNIQUE (storage_type, bucket, object_key);

ALTER TABLE ONLY backend_data.object_storage_files
    ADD CONSTRAINT uq_object_storage_files_user_source_channel UNIQUE (owner_user_id, source_type, source_key, storage_channel);

CREATE INDEX idx_object_storage_files_channel_visibility ON backend_data.object_storage_files USING btree (storage_channel, visibility, updated_at DESC) WHERE (is_deleted = false);

CREATE INDEX idx_object_storage_files_owner ON backend_data.object_storage_files USING btree (owner_user_id);

CREATE INDEX idx_object_storage_files_source_id ON backend_data.object_storage_files USING btree (source_id) WHERE (source_id IS NOT NULL);

CREATE INDEX idx_object_storage_files_status_updated ON backend_data.object_storage_files USING btree (status, updated_at);

CREATE TRIGGER trg_object_storage_files_updated_at BEFORE UPDATE ON backend_data.object_storage_files FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.object_storage_files
    ADD CONSTRAINT object_storage_files_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- file_derivatives

CREATE TABLE backend_data.file_derivatives (
    id bigint NOT NULL,
    file_id bigint NOT NULL,
    type text NOT NULL,
    status text DEFAULT 'ready'::text NOT NULL,
    storage_type text DEFAULT 'r2'::text NOT NULL,
    bucket text,
    object_key text,
    content_text text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_file_derivatives_payload CHECK (((object_key IS NOT NULL) OR (content_text IS NOT NULL))),
    CONSTRAINT file_derivatives_status_check CHECK ((status = ANY (ARRAY['processing'::text, 'ready'::text, 'failed'::text]))),
    CONSTRAINT file_derivatives_storage_type_check CHECK ((storage_type = 'r2'::text)),
    CONSTRAINT file_derivatives_type_check CHECK ((type = ANY (ARRAY['thumbnail'::text, 'extracted_text'::text, 'page_image'::text, 'embedding'::text])))
);

CREATE SEQUENCE backend_data.file_derivatives_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.file_derivatives_id_seq OWNED BY backend_data.file_derivatives.id;

ALTER TABLE ONLY backend_data.file_derivatives ALTER COLUMN id SET DEFAULT nextval('backend_data.file_derivatives_id_seq'::regclass);

ALTER TABLE ONLY backend_data.file_derivatives
    ADD CONSTRAINT file_derivatives_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.file_derivatives
    ADD CONSTRAINT uq_file_derivatives_type UNIQUE (file_id, type);

CREATE INDEX idx_file_derivatives_file_type ON backend_data.file_derivatives USING btree (file_id, type);

CREATE TRIGGER trg_file_derivatives_updated_at BEFORE UPDATE ON backend_data.file_derivatives FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.file_derivatives
    ADD CONSTRAINT file_derivatives_file_id_fkey FOREIGN KEY (file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE CASCADE;

-- file_text_fragments

CREATE TABLE backend_data.file_text_fragments (
    id bigint NOT NULL,
    file_id bigint NOT NULL,
    fragment_index integer NOT NULL,
    fragment_content text NOT NULL,
    raw_content jsonb,
    message_type text,
    total_fragments integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.file_text_fragments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.file_text_fragments_id_seq OWNED BY backend_data.file_text_fragments.id;

ALTER TABLE ONLY backend_data.file_text_fragments ALTER COLUMN id SET DEFAULT nextval('backend_data.file_text_fragments_id_seq'::regclass);

ALTER TABLE ONLY backend_data.file_text_fragments
    ADD CONSTRAINT file_text_fragments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.file_text_fragments
    ADD CONSTRAINT uq_file_frag_idx UNIQUE (file_id, fragment_index);

CREATE INDEX idx_file_text_fragments_created ON backend_data.file_text_fragments USING btree (created_at);

CREATE INDEX idx_file_text_fragments_file ON backend_data.file_text_fragments USING btree (file_id);

CREATE TRIGGER trg_file_text_fragments_updated_at BEFORE UPDATE ON backend_data.file_text_fragments FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.file_text_fragments
    ADD CONSTRAINT file_text_fragments_file_id_fkey FOREIGN KEY (file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE CASCADE;

-- file_access_grants

CREATE TABLE backend_data.file_access_grants (
    id bigint NOT NULL,
    file_id bigint NOT NULL,
    user_id bigint NOT NULL,
    project_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.file_access_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.file_access_grants_id_seq OWNED BY backend_data.file_access_grants.id;

ALTER TABLE ONLY backend_data.file_access_grants ALTER COLUMN id SET DEFAULT nextval('backend_data.file_access_grants_id_seq'::regclass);

ALTER TABLE ONLY backend_data.file_access_grants
    ADD CONSTRAINT file_access_grants_pkey PRIMARY KEY (id);

CREATE INDEX idx_file_access_grants_file_user ON backend_data.file_access_grants USING btree (file_id, user_id) WHERE (is_deleted = false);

CREATE UNIQUE INDEX uq_file_access_grants_project ON backend_data.file_access_grants USING btree (file_id, user_id, project_id) WHERE ((is_deleted = false) AND (project_id IS NOT NULL));

CREATE TRIGGER trg_file_access_grants_updated_at BEFORE UPDATE ON backend_data.file_access_grants FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.file_access_grants
    ADD CONSTRAINT file_access_grants_file_id_fkey FOREIGN KEY (file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.file_access_grants
    ADD CONSTRAINT file_access_grants_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.file_access_grants
    ADD CONSTRAINT file_access_grants_user_id_fkey FOREIGN KEY (user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

-- pdf_derived_media_asset_cache

CREATE TABLE backend_data.pdf_derived_media_asset_cache (
    id bigint NOT NULL,
    owner_user_id bigint NOT NULL,
    source_content_hash text NOT NULL,
    source_file_id bigint,
    extractor_signature text NOT NULL,
    derived_file_id bigint,
    kind text NOT NULL,
    provider text DEFAULT 'jgda'::text NOT NULL,
    page_number integer NOT NULL,
    asset_index integer NOT NULL,
    bbox jsonb,
    caption text,
    description text,
    content_hash text,
    score numeric(8,5),
    status text DEFAULT 'available'::text NOT NULL,
    error_message text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_pdf_derived_media_asset_cache_kind CHECK ((kind = ANY (ARRAY['pdf_image_block'::text, 'pdf_embedded_image'::text, 'pdf_page_snapshot'::text, 'docx_embedded_image'::text, 'pptx_embedded_image'::text]))),
    CONSTRAINT ck_pdf_derived_media_asset_cache_payload CHECK (((derived_file_id IS NOT NULL) OR (status = ANY (ARRAY['processing'::text, 'failed'::text, 'deleted'::text])))),
    CONSTRAINT pdf_derived_media_asset_cache_asset_index_check CHECK ((asset_index > 0)),
    CONSTRAINT pdf_derived_media_asset_cache_metadata_check CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT pdf_derived_media_asset_cache_page_number_check CHECK ((page_number > 0)),
    CONSTRAINT pdf_derived_media_asset_cache_source_content_hash_check CHECK ((length(source_content_hash) = 64)),
    CONSTRAINT pdf_derived_media_asset_cache_status_check CHECK ((status = ANY (ARRAY['processing'::text, 'available'::text, 'failed'::text, 'deleted'::text])))
);

CREATE SEQUENCE backend_data.pdf_derived_media_asset_cache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.pdf_derived_media_asset_cache_id_seq OWNED BY backend_data.pdf_derived_media_asset_cache.id;

ALTER TABLE ONLY backend_data.pdf_derived_media_asset_cache ALTER COLUMN id SET DEFAULT nextval('backend_data.pdf_derived_media_asset_cache_id_seq'::regclass);

ALTER TABLE ONLY backend_data.pdf_derived_media_asset_cache
    ADD CONSTRAINT pdf_derived_media_asset_cache_pkey PRIMARY KEY (id);

CREATE INDEX idx_pdf_derived_media_asset_cache_derived_file ON backend_data.pdf_derived_media_asset_cache USING btree (derived_file_id) WHERE (derived_file_id IS NOT NULL);

CREATE INDEX idx_pdf_derived_media_asset_cache_lookup ON backend_data.pdf_derived_media_asset_cache USING btree (owner_user_id, source_content_hash, extractor_signature, status) WHERE (is_deleted = false);

CREATE INDEX idx_pdf_derived_media_asset_cache_source_file ON backend_data.pdf_derived_media_asset_cache USING btree (source_file_id) WHERE (source_file_id IS NOT NULL);

CREATE UNIQUE INDEX uq_pdf_derived_media_asset_cache_active_slot ON backend_data.pdf_derived_media_asset_cache USING btree (owner_user_id, source_content_hash, extractor_signature, kind, page_number, asset_index) WHERE (is_deleted = false);

CREATE TRIGGER trg_pdf_derived_media_asset_cache_updated_at BEFORE UPDATE ON backend_data.pdf_derived_media_asset_cache FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.pdf_derived_media_asset_cache
    ADD CONSTRAINT pdf_derived_media_asset_cache_derived_file_id_fkey FOREIGN KEY (derived_file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.pdf_derived_media_asset_cache
    ADD CONSTRAINT pdf_derived_media_asset_cache_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES backend_data.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.pdf_derived_media_asset_cache
    ADD CONSTRAINT pdf_derived_media_asset_cache_source_file_id_fkey FOREIGN KEY (source_file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE SET NULL;

-- project_file_links

CREATE TABLE backend_data.project_file_links (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    file_id bigint NOT NULL,
    added_by bigint NOT NULL,
    display_name text,
    kind text DEFAULT 'file'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    CONSTRAINT project_file_links_kind_check CHECK ((kind = ANY (ARRAY['file'::text, 'image'::text, 'document'::text, 'audio'::text, 'video'::text])))
);

CREATE SEQUENCE backend_data.project_file_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.project_file_links_id_seq OWNED BY backend_data.project_file_links.id;

ALTER TABLE ONLY backend_data.project_file_links ALTER COLUMN id SET DEFAULT nextval('backend_data.project_file_links_id_seq'::regclass);

ALTER TABLE ONLY backend_data.project_file_links
    ADD CONSTRAINT project_file_links_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.project_file_links
    ADD CONSTRAINT uq_project_file UNIQUE (project_id, file_id);

CREATE INDEX idx_project_file_links_file ON backend_data.project_file_links USING btree (file_id);

CREATE INDEX idx_project_file_links_project_created ON backend_data.project_file_links USING btree (project_id, is_deleted, created_at DESC);

CREATE TRIGGER trg_project_file_links_updated_at BEFORE UPDATE ON backend_data.project_file_links FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.project_file_links
    ADD CONSTRAINT project_file_links_added_by_fkey FOREIGN KEY (added_by) REFERENCES backend_data.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.project_file_links
    ADD CONSTRAINT project_file_links_file_id_fkey FOREIGN KEY (file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.project_file_links
    ADD CONSTRAINT project_file_links_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE CASCADE;

-- project_pdf_derived_media_asset_links

CREATE TABLE backend_data.project_pdf_derived_media_asset_links (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    source_file_id bigint NOT NULL,
    cache_asset_id bigint NOT NULL,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.project_pdf_derived_media_asset_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.project_pdf_derived_media_asset_links_id_seq OWNED BY backend_data.project_pdf_derived_media_asset_links.id;

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links ALTER COLUMN id SET DEFAULT nextval('backend_data.project_pdf_derived_media_asset_links_id_seq'::regclass);

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links
    ADD CONSTRAINT project_pdf_derived_media_asset_links_pkey PRIMARY KEY (id);

CREATE INDEX idx_project_pdf_derived_media_asset_links_cache ON backend_data.project_pdf_derived_media_asset_links USING btree (cache_asset_id) WHERE (is_deleted = false);

CREATE INDEX idx_project_pdf_derived_media_asset_links_project_source ON backend_data.project_pdf_derived_media_asset_links USING btree (project_id, source_file_id) WHERE (is_deleted = false);

CREATE INDEX idx_project_pdf_derived_media_asset_links_source_file ON backend_data.project_pdf_derived_media_asset_links USING btree (source_file_id) WHERE (is_deleted = false);

CREATE UNIQUE INDEX uq_project_pdf_derived_media_asset_links_active ON backend_data.project_pdf_derived_media_asset_links USING btree (project_id, source_file_id, cache_asset_id) WHERE (is_deleted = false);

CREATE TRIGGER trg_project_pdf_derived_media_asset_links_updated_at BEFORE UPDATE ON backend_data.project_pdf_derived_media_asset_links FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links
    ADD CONSTRAINT project_pdf_derived_media_asset_links_cache_asset_id_fkey FOREIGN KEY (cache_asset_id) REFERENCES backend_data.pdf_derived_media_asset_cache(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links
    ADD CONSTRAINT project_pdf_derived_media_asset_links_created_by_fkey FOREIGN KEY (created_by) REFERENCES backend_data.users(id) ON DELETE SET NULL;

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links
    ADD CONSTRAINT project_pdf_derived_media_asset_links_project_id_fkey FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE CASCADE;

ALTER TABLE ONLY backend_data.project_pdf_derived_media_asset_links
    ADD CONSTRAINT project_pdf_derived_media_asset_links_source_file_id_fkey FOREIGN KEY (source_file_id) REFERENCES backend_data.object_storage_files(id) ON DELETE CASCADE;
