SET search_path TO backend_data, public;

-- Snapshot of Agent's current paperpuppy-internal function names. Keep this
-- catalog aligned with agent/src/main/resources/skills/paperpuppy-internal/skill.json.
INSERT INTO skill_registry
    (skill_name, display_name, category, system_locked, default_enabled, display_order)
VALUES
    ('todo_list', 'Todo List', 'system', true, true, 1),
    ('agent_ledger_update', 'Agent Ledger Update', 'system', true, true, 2),
    ('agent_tool_result_open', 'Tool Result Open', 'system', true, true, 3),
    ('agent_artifact_view_open', 'Artifact View Open', 'system', true, true, 4),
    ('file_list', 'File List', 'file', false, true, 10),
    ('file_content_read', 'File Content Read', 'file', false, true, 11),
    ('image_read', 'Image Read', 'file', false, true, 12),
    ('file_read_url', 'File Read URL', 'file', false, true, 13),
    ('json_structure_read', 'JSON Structure Read', 'file', false, true, 14),
    ('json_subtree_read', 'JSON Subtree Read', 'file', false, true, 15),
    ('document_read', 'Document Read', 'document', false, true, 20),
    ('document_locate', 'Document Locate', 'document', false, true, 21),
    ('document_diff', 'Document Diff', 'document', false, true, 22),
    ('document_save', 'Document Save', 'document', false, true, 23),
    ('document_update_summary', 'Document Summary', 'document', false, true, 24),
    ('document_create', 'Document Create', 'document', false, true, 25),
    ('manage_user_rules', 'User Rules', 'user_management', false, true, 40),
    ('manage_user_memory', 'User Memory', 'user_management', false, true, 41)
ON CONFLICT DO NOTHING;
