---
name: skill-installer
description: Install, uninstall, update, and inspect Deepy skills from the configured Deepy skill market.
metadata:
  short-description: Install skills from Deepy's market
---

# Skill Installer

Use this skill when the user wants to browse, install, uninstall, update, or inspect skills.

## Deepy Skill Commands

- `/skills` shows available management commands.
- `/skills list` lists local project, user, and built-in skills.
- `/skills search [query]` searches the configured Deepy skill market.
- `/skills install <name>` installs a market skill into `~/.agents/skills/<name>`.
- `/skills uninstall <name>` removes a skill installed by Deepy's market installer.
- `/skills installed` lists market-installed skills.
- `/skills update <name>` updates one market-installed skill when a newer upload exists.
- `/skills update --all` updates all market-installed skills when newer uploads exist.
- `/skill:<name> [request]` actively invokes an installed or built-in skill.

## Storage Rules

- Skill content must stay in standard Agent Skills directories.
- User-installed skills go under `~/.agents/skills`.
- Project skills go under `.agents/skills`.
- Deepy market installation records live under `~/.deepy/skill-market/`.
- Do not put market lock files inside a skill directory.

## Safety

Before uninstalling or updating a market-installed skill, compare the current skill content hash with Deepy's install record. If the user modified the skill locally, report the modification and do not overwrite or delete it by default.
