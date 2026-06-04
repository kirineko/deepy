## Why

Windows user feedback showed that Deepy's managed `modify` path can create Python
source files with a UTF-8 signature when the new file contains non-ASCII text.
That signature appears as U+FEFF to common source-parsing flows and can break
validation, while modern Windows Notepad no longer needs a signature to identify
UTF-8 text.

## What Changes

- Change managed new text file creation to use plain UTF-8 without a signature
  on all platforms, including Windows.
- Preserve existing-file encoding behavior: editing a file that is already
  UTF-8 with signature, UTF-16, GBK-compatible, or plain UTF-8 keeps that
  detected encoding.
- Remove the current Windows-only default that writes new non-ASCII text files
  as `utf8-sig`.
- Treat CSV or legacy Windows consumer compatibility as explicit future/export
  behavior rather than the default for project file creation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tools`: revise managed text file creation requirements so new text files are
  BOM-free by default across platforms while existing edits preserve detected
  encodings.

## Impact

- Affected code: `src/deepy/tools/builtin.py` new-file encoding selection.
- Affected tests: `tests/test_tools.py` Windows new-file encoding regression
  coverage.
- Affected specs: `openspec/specs/tools/spec.md` managed text write/file
  creation requirements.
- No public CLI API or dependency changes are expected.
