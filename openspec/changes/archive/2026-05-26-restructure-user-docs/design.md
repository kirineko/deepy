## Context

Deepy's public documentation currently serves several audiences at once:
new users, advanced users configuring MCP, users comparing the stable terminal
UI with the experimental Textual TUI, users learning subagents, and project
contributors. The README files have grown into mixed onboarding, reference, and
feature-status documents. Some reference docs are not available in both English
and Chinese, and the new Bilibili tutorial series has no stable documentation
entrypoint.

This change is documentation-only. It should not alter runtime behavior,
commands, package metadata, dependencies, or tests except where documentation
link validation or formatting checks are available.

## Goals / Non-Goals

**Goals:**

- Make README the shortest credible path from discovery to first successful
  Deepy session.
- Keep `uv` installation visible in Quick Start for users unfamiliar with the
  Python package/tooling ecosystem.
- Remove uv mirror setup and mandatory `deepy config setup` from the primary
  Quick Start path.
- Present first-run configuration as automatic when the user launches `deepy`
  without existing config.
- Provide complete English and Chinese docs for MCP, subagents, UI/TUI, and
  tutorial videos.
- Keep advanced configuration, safety boundaries, troubleshooting, and feature
  matrices in topic-specific docs instead of README.
- Verify screenshot references and video titles during implementation before
  writing title-specific copy.

**Non-Goals:**

- Change Deepy's CLI behavior, configuration defaults, MCP behavior, subagent
  policy, UI/TUI behavior, or package installation method.
- Add a docs build system or new documentation dependency.
- Translate code comments or internal OpenSpec specs outside the docs surfaces
  in scope.
- Guarantee Bilibili metadata freshness after the implementation-time title
  check.

## Decisions

1. README becomes a user journey, not a full reference.

   The README files should answer: what Deepy is, why a user would install it,
   how to start the first session, which commands matter daily, what trust
   boundaries exist, and where to go next. Detailed config tables and feature
   matrices should move to docs pages.

   Alternative considered: keep README as the canonical complete manual. This
   keeps everything in one file but makes the first-run path too long and
   increases bilingual drift.

2. Quick Start keeps `uv` installation but removes uv mirror setup.

   `uv` is necessary context for users who do not know Python tooling, so the
   install command stays in Quick Start. Mirror setup is regional optimization
   and should be optional installation/troubleshooting content.

   Alternative considered: remove `uv` installation entirely and link to uv
   docs. That is shorter, but it weakens onboarding for non-Python users.

3. First-run setup is described as `deepy`, not `deepy config setup`.

   The shortest path should be install, `cd` into a project, and run `deepy`.
   `deepy config setup` remains useful as a manual reconfiguration command and
   should appear in configuration docs or command reference, not as a required
   first-run step.

   Alternative considered: keep `deepy config setup` in Quick Start for
   explicitness. That is more verbose and no longer matches the desired default
   user path.

4. English and Chinese docs use paired filenames.

   Existing pattern is `README.md` and `README.zh-CN.md`. New or split docs
   should follow the same convention, for example
   `docs/tutorial-videos.md` and `docs/tutorial-videos.zh-CN.md`.

   Alternative considered: keep bilingual content in single files. That reduces
   file count but makes deep links and language-specific README references
   awkward.

5. Video documentation uses stable links first.

   The tutorial video docs should include the Bilibili season link and a table
   of individual video links with all query strings removed. If titles cannot be
   verified during implementation, the table should use BV IDs as link text
   rather than invent titles.

   Alternative considered: write estimated titles from memory or playlist
   order. That creates avoidable documentation errors.

## Risks / Trade-offs

- Bilingual drift after the rewrite -> Keep the same section order across
  English and Chinese paired docs and audit commands/defaults together.
- Video metadata may be unavailable from non-browser fetches -> Confirm titles
  during implementation with a browser when possible; otherwise use BV IDs.
- Screenshot references may be stale -> Check referenced assets and rendered
  Markdown image links during implementation.
- README may become too thin -> Keep concise links to topic docs and preserve
  the daily workflow commands that help users succeed immediately.
- Existing external links may change -> Prefer stable Bilibili video URLs
  without tracking parameters and avoid promising exact video counts outside the
  maintained table.
