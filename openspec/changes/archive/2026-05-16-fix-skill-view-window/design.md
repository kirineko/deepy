## Context

The `/skills` menu uses `SkillMenuPicker` as a full-screen prompt_toolkit UI for
market browsing and installed skill management. Installing a market skill now
correctly opens a second full-screen scope picker so the user can choose between
the user skill directory and the current project skill directory.

The view path did not receive the same treatment. A selected installed skill is
currently handled by returning a `show` action to `terminal.py`, which prints the
skill body to the main Deepy output with `console.print(...)`. For market-list
items that are not installed, the same `show` action does not have an installed
skill path, so it can fall through to a "Skill not installed" message instead
of showing useful details.

## Goals / Non-Goals

**Goals:**

- Restore view behavior for installed project, user, and market-managed skills.
- Render skill details in a dedicated full-screen viewer instead of printing
  the body into the main Deepy output area.
- Let users inspect uninstalled market entries from the market tab by showing
  market metadata in the same viewer.
- Keep the install scope picker and existing install/update/uninstall/remove
  actions unchanged.

**Non-Goals:**

- Change `/skills show NAME` command output outside the menu.
- Add editing, paging search, or install-from-view workflows.
- Change market API responses or install metadata format.
- Change skill discovery precedence.

## Decisions

### Add a dedicated skill detail viewer

Create a prompt_toolkit full-screen viewer for skill details, similar in spirit
to the skill menu and install scope picker. It should display a clear title,
metadata such as name/scope/path/version when available, and a scrollable body
containing either the installed `SKILL.md` content or market metadata.

Alternative considered: keep printing the skill body to the console. That is
the current behavior and is the bug being fixed; it mixes browsing output into
the conversation area and breaks the modal flow introduced by the scope picker.

### Preserve menu action routing

The menu can continue to return a `show` action. The handler should resolve the
right view model and call the viewer instead of printing to the console. This
keeps action semantics stable while changing presentation.

Alternative considered: open the viewer inside `SkillMenuPicker` without
returning to `terminal.py`. That would make market metadata easy, but installed
skill body loading and filesystem error handling already belong in the terminal
handler. Keeping the handler responsible avoids duplicating IO in the picker.

### Make uninstalled market view explicit

When the selected item is in the market tab and not installed, `v` should still
return enough metadata for the handler to show a detail view. The view should not
pretend the skill is installed and should not require a local `SKILL.md` path.

Alternative considered: disable `v` for uninstalled market items. That avoids a
new metadata view, but it removes useful browsing behavior and contradicts the
visible footer hint that `v` views the selected skill.

## Risks / Trade-offs

- Full-screen viewer keyboard handling may conflict with the existing menu
  lifecycle -> Keep it separate, return to the menu loop after the viewer exits,
  and cover this with handler tests.
- Large skill bodies may exceed the visible area -> Use a scrollable control or
  text area with clear close/navigation keys.
- Market metadata may be sparse -> Render available fields only and provide a
  concise fallback instead of failing.
