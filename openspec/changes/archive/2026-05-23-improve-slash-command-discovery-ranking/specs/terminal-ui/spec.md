## ADDED Requirements

### Requirement: Stable Slash Command Discovery Ranking
Deepy's stable prompt-toolkit UI SHALL rank slash command completions by user
intent and command relevance rather than by implementation category alone.

#### Scenario: Bare slash discovery includes task entry points
- **WHEN** the stable interactive prompt builds completions for a bare `/`
- **THEN** Deepy SHALL include built-in commands, subagent commands, and skill
  invocation commands in the completion candidate set
- **AND** common workflow commands SHALL appear before lower-frequency
  management or exit commands
- **AND** subagent commands SHALL be discoverable without requiring the user to
  type a subagent-specific prefix

#### Scenario: Typed slash search ranks useful matches
- **WHEN** the user types a partial slash command token
- **THEN** exact command-name matches SHALL rank before prefix matches
- **AND** prefix matches SHALL rank before weaker description or substring
  matches
- **AND** ties SHALL use the shared slash command priority and then stable
  alphabetical ordering

#### Scenario: Skill completions show metadata
- **WHEN** the stable UI renders skill slash completions
- **THEN** each skill completion SHALL expose the skill label and description
  when available
- **AND** loaded skills SHALL be distinguishable from unloaded skills
- **AND** loaded skills SHALL rank ahead of otherwise equivalent unloaded skill
  completions

#### Scenario: File mention completion is unaffected
- **WHEN** slash command completions and file mention completions are both
  available through the stable prompt input
- **THEN** slash command ranking SHALL NOT prevent file mention completions from
  appearing for `@` file tokens
- **AND** file mention completions SHALL NOT reorder slash command candidates
  for `/` command tokens
