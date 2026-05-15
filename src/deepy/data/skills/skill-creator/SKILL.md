---
name: skill-creator
description: Create or update Agent Skills for Deepy. Use when the user wants to design, write, validate, or improve a reusable skill.
metadata:
  short-description: Create or update an Agent Skill
---

# Skill Creator

Use this skill when creating or improving an Agent Skill.

## Skill Shape

An Agent Skill is a directory with a required `SKILL.md` file:

```text
skill-name/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

`SKILL.md` uses YAML frontmatter followed by concise Markdown instructions:

```markdown
---
name: code-review
description: Review code changes for correctness, regressions, and missing tests.
---

# Code Review

Review the change before summarizing it. Lead with findings.
```

## Rules

- Store user skills in `~/.agents/skills/<name>/SKILL.md`.
- Store project skills in `<project>/.agents/skills/<name>/SKILL.md`.
- Use lowercase letters, digits, and hyphens for skill names.
- Keep `SKILL.md` focused. Move detailed material to `references/`.
- Use `scripts/` for deterministic repeated operations.
- Use `assets/` for templates or files that support final outputs.
- Do not add market-specific metadata to the skill directory.

## Creation Process

1. Identify the concrete situations that should trigger the skill.
2. Choose a short hyphen-case name.
3. Write a clear `description` that says when to use the skill.
4. Keep the main workflow in `SKILL.md`.
5. Add references, scripts, or assets only when they remove real repetition or ambiguity.
6. Validate that the skill can be discovered by Deepy with `/skills list`.
