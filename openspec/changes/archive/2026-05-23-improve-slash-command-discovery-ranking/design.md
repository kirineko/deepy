## Context

Deepy currently builds one slash command list in `deepy.ui.slash_commands` and
feeds it to both the stable prompt-toolkit UI and the experimental Textual TUI.
The list is assembled in implementation categories: built-in commands first,
then built-in subagents, then skills. Each group is alphabetized.

That ordering is mechanically simple but user-hostile as the catalog grows. In
the Textual TUI, prompt-adjacent suggestions are capped to the first eight
entries, so typing a bare `/` only shows early built-in commands and hides
subagents and skills even though the full candidate list contains them. In the
stable UI, `WordCompleter` receives only command labels, so it cannot present
descriptions, loaded skill state, or a richer shared ranking.

## Goals / Non-Goals

**Goals:**

- Make bare `/` discovery useful by surfacing common workflows, subagents, and
  relevant skills in the first view.
- Use the same slash command ranking semantics in stable UI and Textual TUI.
- Preserve quick typed lookup by ranking exact and prefix matches before weaker
  matches.
- Keep skill invocation, subagent invocation, file mention completion, and
  existing slash command execution semantics unchanged.
- Make the behavior testable at the shared ranking layer and at each UI surface.

**Non-Goals:**

- Add persistent command usage history or telemetry.
- Redesign `/skills` management screens.
- Change which skills or subagents are discovered.
- Change the command names or remove legacy `/skill:<name>` support.
- Replace Textual's global command palette implementation.

## Decisions

1. Introduce shared slash command ranking.

   Add a shared ranking function near `deepy.ui.slash_commands` so both UIs ask
   the same source for ordered candidates. The ranking should handle two modes:
   bare discovery and typed search.

   Bare discovery should prioritize:

   1. Common workflow commands such as `/help`, `/new`, `/resume`, `/model`,
      `/skills`, `/status`, `/compact`, `/mcp`, and `/exit`.
   2. Subagents such as `/explore`, `/reviewer`, and `/tester`.
   3. Relevant skills, with loaded skills first, then project/user/built-in
      skills using existing discovery precedence metadata where available.
   4. Lower-frequency or high-impact management commands such as `/init`,
      `/theme`, `/input-suggestion`, `/ps`, `/stop`, and `/reset`.

   Typed search should rank exact matches, prefix matches, and weaker matches in
   that order, then apply the same priority and stable alphabetical tie-breakers.

   Alternative considered: only reorder `BUILTIN_SLASH_COMMANDS`. That would
   fix a few first-screen items but would leave Textual and prompt-toolkit with
   duplicated behavior and would not solve relevance for skills.

2. Make stable prompt-toolkit completion slash-aware.

   Replace the label-only `WordCompleter` path for slash commands with a custom
   completer that uses the shared ranking and emits completion metadata. The
   stable UI should still merge file mention completions, but slash completions
   should carry labels, descriptions, and loaded skill markers.

   Alternative considered: keep `WordCompleter` and rely on list order only.
   That keeps implementation smaller but cannot show descriptions or loaded
   state and makes future ranking harder to test directly.

3. Let Textual suggestions scroll instead of truncating the source list.

   The Textual suggestion widget already has a visual `max-height`; the data
   source should not also be truncated to eight items. Add all ranked
   suggestions to the `OptionList` and let the widget's scrolling behavior expose
   the rest. The first eight visible rows should still be useful because ranking
   is improved, but users can reach subagents and skills even when the catalog is
   larger.

   Alternative considered: keep the eight-item cap and force at least one item
   from each command kind into the first eight. That creates surprising gaps and
   makes keyboard navigation inconsistent.

4. Keep invocation parsing unchanged.

   Ranking is a discovery concern. `parse_slash_command()`,
   `find_exact_slash_command()`, skill lookup, subagent prompt generation, and
   unsupported-command handling should continue to decide execution behavior.

## Risks / Trade-offs

- More custom completion code can diverge from prompt-toolkit defaults.
  Mitigation: keep it narrowly scoped to slash commands and leave file mentions
  on the existing completer.
- A fixed priority list can become stale as commands are added.
  Mitigation: centralize priorities and give unknown commands a sensible
  default group plus alphabetical tie-breaking.
- Showing all Textual suggestions may create long lists in projects with many
  skills.
  Mitigation: rely on the existing visual max-height and scrolling; typed
  filtering narrows the list quickly.
- Ranking can be subjective.
  Mitigation: encode intent in tests around concrete examples: bare `/`,
  `/re`, `/skil`, subagent matches, and loaded skill priority.
