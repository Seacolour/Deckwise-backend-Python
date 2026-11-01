-- Markdown documents and persisted document versions.

-- documents

CREATE TABLE backend_data.documents (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    title text NOT NULL,
    document_type text DEFAULT 'markdown'::text NOT NULL,
    summary text,
    summary_version integer DEFAULT 1,
    current_file_id bigint,
    draft_content text,
    draft_updated_at timestamp with time zone,
    version integer DEFAULT 1 NOT NULL,
    created_by bigint,
    updated_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_documents_document_type CHECK ((document_type = 'markdown'::text))
);

CREATE SEQUENCE backend_data.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.documents_id_seq OWNED BY backend_data.documents.id;

ALTER TABLE ONLY backend_data.documents ALTER COLUMN id SET DEFAULT nextval('backend_data.documents_id_seq'::regclass);

ALTER TABLE ONLY backend_data.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);

CREATE INDEX idx_documents_project_current_file ON backend_data.documents USING btree (project_id, current_file_id) WHERE (is_deleted = false);

CREATE INDEX idx_documents_project_type_updated_at ON backend_data.documents USING btree (project_id, document_type, updated_at DESC) WHERE (is_deleted = false);

CREATE INDEX idx_documents_project_updated_at ON backend_data.documents USING btree (project_id, updated_at DESC);

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON backend_data.documents FOR EACH ROW EXECUTE FUNCTION backend_data.touch_updated_at();

ALTER TABLE ONLY backend_data.documents
    ADD CONSTRAINT fk_documents_current_file FOREIGN KEY (current_file_id) REFERENCES backend_data.object_storage_files(id);

ALTER TABLE ONLY backend_data.documents
    ADD CONSTRAINT fk_documents_project FOREIGN KEY (project_id) REFERENCES backend_data.projects(id) ON DELETE CASCADE;

-- document_versions

CREATE TABLE backend_data.document_versions (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    version_no integer NOT NULL,
    file_id bigint NOT NULL,
    message text,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE backend_data.document_versions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE backend_data.document_versions_id_seq OWNED BY backend_data.document_versions.id;

ALTER TABLE ONLY backend_data.document_versions ALTER COLUMN id SET DEFAULT nextval('backend_data.document_versions_id_seq'::regclass);

ALTER TABLE ONLY backend_data.document_versions
    ADD CONSTRAINT document_versions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY backend_data.document_versions
    ADD CONSTRAINT uq_doc_versions_doc_ver UNIQUE (document_id, version_no);

CREATE INDEX idx_doc_versions_document_created_at ON backend_data.document_versions USING btree (document_id, created_at DESC);

CREATE INDEX idx_doc_versions_file_id ON backend_data.document_versions USING btree (file_id);

ALTER TABLE ONLY backend_data.document_versions
    ADD CONSTRAINT fk_doc_versions_document FOREIGN KEY (document_id) REFERENCES backend_data.documents(id);

ALTER TABLE ONLY backend_data.document_versions
    ADD CONSTRAINT fk_doc_versions_file FOREIGN KEY (file_id) REFERENCES backend_data.object_storage_files(id);
