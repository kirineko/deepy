## 1. Documentation Inventory

- [x] 1.1 Audit current README, MCP, subagents, UI/TUI, and asset references before rewriting.
- [x] 1.2 Decide final paired filenames for subagents, UI/TUI, and tutorial video docs.
- [x] 1.3 Confirm whether existing README screenshots remain accurate enough to keep.

## 2. README Rewrite

- [x] 2.1 Rewrite `README.md` around user-centered onboarding and shortest first-run path.
- [x] 2.2 Rewrite `README.zh-CN.md` with matching structure and Chinese-first wording.
- [x] 2.3 Keep `uv` installation in Quick Start and remove uv mirror setup from the primary path.
- [x] 2.4 Replace required `deepy config setup` onboarding with direct `deepy` launch and first-run auto-configuration explanation.
- [x] 2.5 Move uv mirror setup, manual config setup, and advanced references to later sections or linked docs.

## 3. Topic Docs

- [x] 3.1 Update `docs/mcp.md` as the English MCP reference.
- [x] 3.2 Update `docs/mcp.zh-CN.md` to match the English MCP structure, including subagent search inheritance.
- [x] 3.3 Update `docs/subagents.md` as the English subagent reference.
- [x] 3.4 Add `docs/subagents.zh-CN.md` with aligned Chinese subagent documentation.
- [x] 3.5 Create or split English and Chinese UI/TUI docs while preserving the stable UI versus experimental TUI status.
- [x] 3.6 Preserve current UI/TUI known limitations and pending verification notes where still accurate.

## 4. Tutorial Video Docs

- [x] 4.1 Add English tutorial video documentation with the Bilibili season link.
- [x] 4.2 Add Chinese tutorial video documentation with matching structure.
- [x] 4.3 Build a table of all supplied individual Bilibili videos in order with query strings removed.
- [x] 4.4 Verify individual video titles during implementation with a browser when possible.
- [x] 4.5 Use BV IDs as link text for any video whose title cannot be verified.

## 5. Verification

- [x] 5.1 Verify internal Markdown links point to existing files after any doc rename or split.
- [x] 5.2 Verify referenced local screenshot assets exist and remote screenshot URLs are intentional.
- [x] 5.3 Check README and topic docs for command/default drift between English and Chinese.
- [x] 5.4 Run `openspec validate restructure-user-docs --type change --strict`.
- [x] 5.5 Run any available repository documentation or formatting checks relevant to Markdown changes.
