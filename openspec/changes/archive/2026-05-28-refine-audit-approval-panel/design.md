## Context

`add-system-audit-modes` introduced SDK approval interruptions in the stable
terminal UI. The current rendering is functionally correct but exposes raw
internal fields (`action`, `tool`, `agent`, and `arguments.*`) and can make
large write payloads dominate the terminal.

The approval surface is a high-attention UI: users are deciding whether to
allow a side effect. It should therefore answer "what will happen?" first, and
only reveal implementation-shaped details when no better summary is available.

Reference patterns:
- Kimi renders an approval panel with a small preview budget and an explicit
  expand path for truncated content.
- Qwen renders type-specific confirmation messages for shell, edit/write, and
  MCP instead of dumping generic arguments.
- Reasonix separates a card header/body/footer and keeps decision controls
  visually distinct from contextual information.

## Goals / Non-Goals

**Goals:**
- Make approval prompts task-focused rather than SDK-field-focused.
- Use project-relative paths in approval displays whenever possible.
- Render `Write` and `Update` approval prompts with highlighted diff previews.
- Support a visible expand/collapse control for truncated diffs without mixing
  that auxiliary control into the final approve/reject area.
- Restrict approval keyboard interaction to `Up`, `Down`, `Enter`, and `Esc`.
- Preserve the existing SDK approval/resume semantics and audit mode policy.

**Non-Goals:**
- Add new audit modes or change mode semantics.
- Add persistent "always allow" rules.
- Change MCP allowlist configuration.
- Redesign the experimental Textual TUI.
- Replace the current prompt-toolkit picker if it remains usable after the
  interaction constraints are applied.

## Decisions

### Introduce an approval view model

Create a small internal representation for terminal approval rendering before
building Rich/prompt-toolkit widgets. The view model should derive:

- `title`: the user-facing question, such as `Approve command?`,
  `Approve write? two_sum.py`, `Approve update? src/app.py`, or
  `Approve MCP tool? tavily_extract`.
- `target`: the primary command, relative path, or MCP server/tool.
- `metadata`: only meaningful secondary fields, such as command description,
  MCP `url`, MCP `query`, content size, or line counts.
- `preview`: an optional Rich renderable for command, diff, or compact
  structured arguments.
- `can_expand`: whether an auxiliary expand/collapse control should be shown.

Rationale: this avoids scattering special cases across panel rendering and
allows focused tests for summary derivation without driving terminal input.

Alternative considered: continue building `Text` directly from `PendingApproval`.
That keeps code smaller in the short term but makes it harder to hide raw
arguments consistently and to add diff-specific behavior.

### Use diff-first rendering for Write and Update approvals

`Write` should be treated as a diff from an empty file to the proposed content.
`Update` should render the proposed replacement as a diff when enough
information is available from tool arguments. Paths should be displayed relative
to the active project root when the target path is under that root; otherwise
they should be displayed with the existing home-relative formatter.

Rationale: approval for file mutation is safest when the user sees what changes,
not only which file is targeted.

Alternative considered: show a content preview only. This is less useful for
updates because it hides removed text and makes replacements harder to audit.

### Separate auxiliary controls from final decisions

If a diff is truncated, render an auxiliary `Diff expand` / `Diff collapse`
control adjacent to the decision picker. The final decision controls remain only
`Approve` and `Reject`, and expanding or collapsing the diff should redraw the
same prompt surface rather than appending another approval panel to the
transcript.

Rationale: users should not confuse "inspect more" with "allow side effect".
Keeping it above the decision area preserves a simple mental model while still
allowing only `Up` / `Down` / `Enter` / `Esc`.

Alternative considered: use an `e` key to expand. The user explicitly preferred
keeping keyboard interaction limited to navigation, Enter, and Esc.

### Remove letter shortcuts from approval picking

The approval picker should not respond to `Y`, `A`, `N`, or `R`, and visible
hints should not advertise those shortcuts. `Esc` always rejects. `Enter`
activates the currently selected item.

Rationale: restricting shortcuts reduces accidental approvals and keeps the
approval surface easy to explain.

## Risks / Trade-offs

- [Risk] Diff previews may be inaccurate if `Update` arguments do not contain
  enough context to construct a reliable before/after diff.
  → Mitigation: fall back to a compact typed summary rather than fabricating a
  diff; add tests for missing/partial arguments.
- [Risk] Long expanded diffs can push context out of the terminal scrollback.
  → Mitigation: expanded mode is user-triggered and can still be bounded by a
  high line cap if needed.
- [Risk] Relative path formatting can hide that a tool targets a file outside
  the project.
  → Mitigation: use relative paths only for paths under the project root; show
  home-relative or absolute paths otherwise.
- [Risk] Removing letter shortcuts may feel slower for power users.
  → Mitigation: this only affects the high-risk approval surface; normal prompt
  input and other pickers are unchanged.
