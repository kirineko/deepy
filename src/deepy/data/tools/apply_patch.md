## apply_patch

Batch structured file operations in one call.

Args: `operations`.

Use this when a change has multiple edits in one file, touches multiple files,
creates/deletes/moves files, replaces a larger block, or needs one all-or-nothing
preflight before writing. Use `edit_text` only for one small single-file exact
edit where `old_string` and `new_string` are straightforward.

Each operation is an object with a `type` and the fields relevant to that type.
Set unrelated nullable fields to `null` when required by the schema.

Supported operation types:

- `create_file`: create a new text file with `file_path` and `content`.
- `replace_file`: explicitly replace a whole existing file with `file_path`,
  `content`, `overwrite=true`, and either `snapshot_id` or `expected_hash`.
- `delete_file`: delete `file_path`.
- `move_file`: move `file_path` to `destination_path`.
- `replace_block`: replace exact `old_text` with `new_text`.
- `insert_before`: insert `content` before exact `anchor`.
- `insert_after`: insert `content` after exact `anchor`.
- `replace_all`: replace every exact `old_text` match with `new_text`.

Example:

```json
{
  "operations": [
    {
      "type": "replace_block",
      "file_path": "portfolio/index.html",
      "old_text": "<p>Old bio</p>",
      "new_text": "<p>New bio</p>",
      "expected_occurrences": 1,
      "destination_path": null,
      "content": null,
      "anchor": null,
      "replace_all": null,
      "overwrite": null,
      "snapshot_id": null,
      "expected_hash": null
    },
    {
      "type": "insert_after",
      "file_path": "portfolio/styles.css",
      "anchor": ".about {\\n  display: grid;\\n}\\n",
      "content": "\\n.about-tags {\\n  display: flex;\\n}\\n",
      "expected_occurrences": 1,
      "destination_path": null,
      "old_text": null,
      "new_text": null,
      "replace_all": null,
      "overwrite": null,
      "snapshot_id": null,
      "expected_hash": null
    }
  ]
}
```

Deepy preflights all operations before committing file side effects, preserves
existing encodings and line endings on updates, writes new text files as UTF-8
without BOM, and returns per-operation, changed-file, diff, and diff-preview
metadata. Exact text and anchor operations reject absent, ambiguous, no-op, and
unexpected-count matches with structured diagnostics.
