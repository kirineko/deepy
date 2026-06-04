## 1. Detail View Model And Viewer

- [x] 1.1 Add a skill detail view model that can represent installed skill content and market metadata.
- [x] 1.2 Add a full-screen prompt_toolkit skill detail viewer with close and scroll/navigation controls.
- [x] 1.3 Ensure the viewer renders available name, scope, path, version, install status, and body/description fields without crashing on missing metadata.
- [x] 1.4 Render Markdown structure in skill detail bodies and market descriptions.

## 2. Menu Action Routing

- [x] 2.1 Update `SkillMenuPicker` view actions so installed items carry local skill path data and uninstalled market items carry market metadata.
- [x] 2.2 Update `_handle_skill_menu_action` so `show` opens the dedicated viewer instead of printing skill bodies to the main console.
- [x] 2.3 Ensure viewing an uninstalled market item does not call `find_skill` and does not show a false "Skill not installed" error.
- [x] 2.4 Preserve existing install scope picker behavior for uninstalled market items.
- [x] 2.5 Preserve update, uninstall, remove-local, refresh, and tab-switch behavior.

## 3. Tests And Verification

- [x] 3.1 Add skill picker tests for view actions on installed and uninstalled market items.
- [x] 3.2 Add terminal handler tests proving installed skill view calls the detail viewer and does not print the body to the main console.
- [x] 3.3 Add terminal handler tests proving uninstalled market skill view opens metadata in the detail viewer rather than reporting a missing install.
- [x] 3.4 Add skill detail formatting coverage for Markdown headings, lists, and code fences.
- [x] 3.5 Run focused skill picker and terminal UI tests.
- [x] 3.6 Verify `openspec validate fix-skill-view-window --type change --strict` passes.
