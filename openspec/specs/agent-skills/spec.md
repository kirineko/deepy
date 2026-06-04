# agent-skills Specification

## Purpose
TBD - created by archiving change add-agent-skill-market. Update Purpose after archive.
## Requirements
### Requirement: Standard Agent Skills Discovery
Deepy SHALL discover user skills from `~/.agents/skills` and project skills from `<project>/.agents/skills`, using standard Agent Skills directories that contain `SKILL.md`.

#### Scenario: Project and user skills are discovered
- **WHEN** Deepy starts in a project with `.agents/skills/review/SKILL.md` and the user has `~/.agents/skills/pdf/SKILL.md`
- **THEN** both `review` and `pdf` appear in the available skills list

#### Scenario: Legacy Deepy skill directory is ignored
- **WHEN** a project contains `.deepy/skills/legacy/SKILL.md`
- **THEN** Deepy MUST NOT discover `legacy` as an available skill

### Requirement: Built-in Skills
Deepy SHALL ship `skill-creator` and `skill-installer` as built-in skills that are available without being installed into `.agents/skills`.

#### Scenario: Built-in skill availability
- **WHEN** no user or project skill directories exist
- **THEN** Deepy still lists `skill-creator` and `skill-installer` as built-in skills

### Requirement: Scope Priority
Deepy SHALL resolve duplicate skill names by scope priority: project skills override user skills, and user skills override built-in skills.

#### Scenario: Project overrides user
- **WHEN** both `.agents/skills/review/SKILL.md` and `~/.agents/skills/review/SKILL.md` exist
- **THEN** Deepy uses the project `review` skill

### Requirement: Progressive Skill Loading
Deepy SHALL expose skill metadata in the system prompt and provide a `load_skill` tool that returns complete skill instructions on demand.

#### Scenario: Skill metadata is available without body content
- **WHEN** Deepy builds the system prompt
- **THEN** the prompt includes each available skill name, scope, path, and description
- **AND** the prompt does not include every available skill body

#### Scenario: Model loads a skill
- **WHEN** the model calls `load_skill` with an available skill name
- **THEN** Deepy returns the skill body and skill root path

### Requirement: No Harness Keyword Auto-loading
Deepy SHALL NOT load skills by harness-side keyword matching before the model turn.

#### Scenario: Prompt mentions a skill description keyword
- **WHEN** the user prompt contains a word that appears in a skill description
- **THEN** Deepy does not pre-load that skill body unless the user explicitly invoked it

### Requirement: Explicit Skill Invocation
Deepy SHALL support explicit skill invocation through `/skill:<skill-name> [request]`.

#### Scenario: Invoke skill by slash prefix
- **WHEN** the user enters `/skill:review summarize this diff`
- **THEN** Deepy starts a model turn with the `review` skill content and the request `summarize this diff`

