## Why

Deepy's current documentation mixes first-run onboarding, configuration
reference, feature overview, MCP details, TUI status, and development notes in
the README. This makes the first user path longer than necessary and leaves
Chinese/English documentation pairs uneven across MCP, subagents, UI/TUI, and
new tutorial video resources.

## What Changes

- Rebuild `README.md` and `README.zh-CN.md` around the user journey: what Deepy
  is, who it is for, the shortest path to first use, daily commands, trust
  boundaries, and links to deeper references.
- Keep `uv` installation in Quick Start for users unfamiliar with the Python
  tooling ecosystem, but remove uv mirror setup and mandatory
  `deepy config setup` from the primary first-run path.
- Document that `deepy` can be launched directly after installation and will
  guide first-run provider/API key/model/theme configuration when config is
  missing.
- Keep uv mirror configuration as an optional installation/troubleshooting note
  rather than a Quick Start step.
- Restructure MCP docs as complete English and Chinese reference pairs,
  including minimal setup, configuration files, transport examples, search
  preference, project-config safety, subagent search inheritance, and
  troubleshooting.
- Add Chinese subagent documentation and align it with the English subagent
  reference.
- Split or pair the UI/TUI documentation into English and Chinese versions,
  preserving the current stable UI versus experimental TUI status and pending
  verification notes.
- Add tutorial video documentation with the Bilibili season link and a table of
  individual video links with tracking parameters removed.
- Add implementation tasks to verify screenshots and video titles during the
  implementation phase rather than guessing them in the proposal.
- Audit internal links, command examples, config defaults, and bilingual section
  parity after the rewrite.

## Capabilities

### New Capabilities

- `user-documentation`: User-facing documentation structure, bilingual parity,
  first-run onboarding, advanced reference docs, and tutorial video resources.

### Modified Capabilities

- None.

## Impact

- Affected files include `README.md`, `README.zh-CN.md`, `docs/mcp.md`,
  `docs/mcp.zh-CN.md`, `docs/subagents.md`, new Chinese subagent docs, UI/TUI
  docs, and new tutorial video docs.
- No runtime behavior, package APIs, command semantics, or dependencies are
  expected to change.
- Documentation screenshots and video titles may require live verification
  during implementation.
