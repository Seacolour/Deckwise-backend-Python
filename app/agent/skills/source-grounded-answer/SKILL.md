---
name: source-grounded-answer
description: Use when answering a question from several project files with traceable source fragments.
---

# Source-grounded answer

1. Use `semantic_file_search` to find relevant project fragments when it is available. For a specific attached file, pass its `cache_key`.
2. Read surrounding fragments with `file_content_read` when a snippet is incomplete or a claim needs confirmation.
3. Name the file and fragment index for each important fact. Separate what the files state from any inference.
4. If the search returns no relevant evidence, say so rather than inventing a source. Do not claim to have read the entire file from a short snippet.
