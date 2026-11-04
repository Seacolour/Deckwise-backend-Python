---
name: document-review
description: Use when reviewing or making a focused edit to a project Markdown document.
---

# Document review

1. Identify the document from the user's explicit reference or `file_list`.
2. Read the current draft and version with `document_read`. For a narrow edit, use `document_locate` to find the exact original line.
3. Apply a small `document_diff` hunk to the working copy. If the source is ambiguous, ask for a more specific target or locate again.
4. Call `document_save` with the version returned by the read and omit `draft_content` when saving a diff.
5. Describe only edits confirmed by a successful save result. On a version conflict, read the latest draft before deciding how to retry.
