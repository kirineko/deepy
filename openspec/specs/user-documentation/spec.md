## Purpose

Define the user-facing documentation structure, onboarding expectations, topic
document parity, tutorial-video documentation, and documentation asset checks.

## Requirements

### Requirement: User-centered README onboarding

Deepy SHALL present README files as user-centered onboarding documents that
prioritize first successful use over exhaustive reference content.

#### Scenario: Quick Start shows the shortest supported first-run path

- **WHEN** a user reads `README.md` or `README.zh-CN.md`
- **THEN** the Quick Start SHALL include installing `uv`, installing
  `deepy-cli`, entering a project directory, and running `deepy`
- **AND** the Quick Start SHALL NOT require uv mirror setup before installing
  Deepy
- **AND** the Quick Start SHALL NOT require running `deepy config setup` before
  launching Deepy

#### Scenario: First-run configuration is explained

- **WHEN** a user reads the Quick Start or configuration overview
- **THEN** the documentation SHALL explain that launching `deepy` without
  existing configuration starts the first-run setup flow for provider, API key,
  model, and theme
- **AND** it SHALL describe `deepy config setup` as an optional manual
  configuration or reconfiguration command

#### Scenario: Advanced details are linked instead of embedded

- **WHEN** README content mentions MCP, subagents, UI/TUI, tutorial videos,
  installation troubleshooting, or detailed configuration
- **THEN** the README SHALL link to the relevant topic document instead of
  duplicating the full reference content

### Requirement: Bilingual topic documentation parity

Deepy SHALL provide aligned English and Chinese user documentation for major
topic docs introduced or reworked by this change.

#### Scenario: MCP docs are aligned

- **WHEN** MCP documentation is updated
- **THEN** `docs/mcp.md` and `docs/mcp.zh-CN.md` SHALL cover the same major
  topics: minimal setup, `~/.deepy/config.toml`, `~/.deepy/mcp.json`, stdio
  servers, streamable HTTP servers, environment placeholders, project config,
  subagent search inheritance, and troubleshooting

#### Scenario: Subagent docs are aligned

- **WHEN** subagent documentation is updated
- **THEN** English and Chinese subagent docs SHALL both explain built-in
  subagents, automatic delegation, lifecycle visibility, limitations, custom
  subagent definition files, supported tools, and `test_shell` policy

#### Scenario: UI and TUI docs are aligned

- **WHEN** UI/TUI documentation is updated
- **THEN** English and Chinese UI/TUI docs SHALL both explain that `deepy` is
  the stable default UI and `deepy tui` is the experimental Textual UI
- **AND** both docs SHALL preserve the current feature comparison, known
  limitations, and pending verification notes where applicable

### Requirement: Tutorial video documentation

Deepy SHALL document the tutorial video series as a stable learning resource.

#### Scenario: Tutorial video docs provide a playlist entrypoint

- **WHEN** a user opens the tutorial video documentation
- **THEN** the documentation SHALL link to the Bilibili season page
  `https://space.bilibili.com/560507/lists/8171057`
- **AND** it SHALL explain how the video series relates to README onboarding
  and topic reference docs

#### Scenario: Tutorial video table uses clean links

- **WHEN** individual Bilibili videos are listed
- **THEN** each table row SHALL use a URL without tracking query parameters
- **AND** the table SHALL include all supplied BV video IDs in the provided
  order

#### Scenario: Video titles are verified before title-specific copy

- **WHEN** implementation adds human-readable video titles
- **THEN** the implementer SHALL verify the titles during implementation
- **AND** if titles cannot be verified, the docs SHALL use BV IDs as link text
  rather than guessing titles

### Requirement: Documentation asset and link verification

Deepy SHALL keep documentation links and referenced visual assets reviewable
after the rewrite.

#### Scenario: Screenshot references are checked

- **WHEN** implementation keeps, moves, removes, or adds screenshot references
- **THEN** the implementer SHALL verify that referenced screenshot assets exist
  or that remote image URLs are intentionally retained

#### Scenario: Internal documentation links are checked

- **WHEN** README or topic docs link to other repository docs
- **THEN** the implementer SHALL verify that internal Markdown links point to
  existing files after any file rename or split

### Requirement: Textual TUI Polish Documentation
Deepy documentation SHALL describe the polished Textual TUI experience without
claiming that the stable UI has been removed or replaced.

#### Scenario: User reads TUI documentation
- **WHEN** documentation describes `deepy tui`
- **THEN** it SHALL explain the compact transcript, integrated composer,
  attachment deletion, live activity feedback, and inline decision blocks
- **AND** it SHALL state that `deepy` remains the current default entrypoint

#### Scenario: User reads theme documentation
- **WHEN** documentation describes UI themes
- **THEN** it SHALL explain that Deepy's shared theme values remain `dark` and
  `light`
- **AND** it SHALL document the Textual TUI's curated built-in theme mapping
- **AND** it SHALL document that the Textual TUI can save a TUI-specific
  `ui.textual_theme` override from the theme picker
- **AND** it SHALL distinguish any TUI-specific Textual theme selection from the
  stable UI theme contract

#### Scenario: Documentation includes screenshots
- **WHEN** documentation includes TUI screenshots after this change
- **THEN** screenshots SHALL show the current polished layout
- **AND** stale screenshots of the previous TUI layout SHALL be removed or
  clearly replaced

### Requirement: Textual UI Migration Documentation
Deepy documentation SHALL describe the redesigned Textual TUI direction without
claiming that the stable UI has already been removed or replaced.

#### Scenario: UI topic docs are updated
- **WHEN** UI documentation is updated for this change
- **THEN** English and Chinese docs SHALL explain that `deepy` remains the
  current stable default entrypoint
- **AND** they SHALL explain that `deepy tui` is being redesigned as the future
  primary UI candidate
- **AND** they SHALL describe the staged migration goal to eventually remove
  stable/TUI duplication

#### Scenario: Composer behavior is documented
- **WHEN** docs describe the redesigned Textual composer
- **THEN** they SHALL explain prompt text, image attachments, generated input
  suggestions, slash suggestions, and file suggestions as distinct UI states
- **AND** they SHALL NOT describe attachment state as text replacement tokens
  inside the prompt buffer

#### Scenario: Screenshots are updated
- **WHEN** screenshots or visual assets are kept, replaced, or removed for the
  redesigned TUI
- **THEN** docs SHALL reference only existing assets
- **AND** stale screenshots of the old TUI layout SHALL be removed or clearly
  replaced

### Requirement: Provider Search And Image Documentation
Deepy SHALL document the new provider, API, configuration and image contracts consistently in English and Chinese after implementation is verified.

#### Scenario: Provider setup docs
- **WHEN** README or configuration/model reference is updated
- **THEN** both languages SHALL show the four providers, exact API model IDs, independent profiles, provider environment variables, and switch-without-key-loss behavior
- **AND** examples SHALL NOT contain real credentials or the local proxy test token

#### Scenario: API and search docs
- **WHEN** users read web/tool/provider documentation
- **THEN** it SHALL explain Responses for model calls and the separate DeepSeek Messages WebSearch exception
- **AND** it SHALL explain the independent DeepSeek key requirement, unchanged MCP preference and local WebFetch
- **AND** it SHALL remove current-support claims for OpenRouter, SearXNG and DuckDuckGo fallback

#### Scenario: Image docs
- **WHEN** users read model/UI documentation
- **THEN** it SHALL distinguish supported Responses image models from text-only MiMo Pro and unsupported native audio/video/PDF paths
- **AND** it SHALL explain image limits and incompatible model-switch recovery

#### Scenario: Upgrade docs
- **WHEN** a user upgrades from a shared model configuration
- **THEN** documentation SHALL state that explicit profile reconfiguration is required and old configuration is not automatically migrated
- **AND** it SHALL explain preserving the old file for manual recovery without suggesting secrets be committed

### Requirement: Model Context And History Documentation
Deepy SHALL document model-specific windows, output budgets and history migration consistently in English and Chinese.

#### Scenario: Users configure or switch models
- **WHEN** users consult the provider and context documentation
- **THEN** it SHALL distinguish official nominal limits, conservative values and unverified proxy limits, explain overrides and output reserve, and show history-preserving model switching
- **AND** it SHALL describe /compact --for-model, image-summary information loss, usage attribution and failure recovery
- **AND** it SHALL not claim maximum-context live validation from short smoke tests

### Requirement: Current Release Landing Copy
The project landing page SHALL describe shipped provider, search and context capabilities and show the package release version.

#### Scenario: Users review the release features
- **WHEN** users open the project landing page
- **THEN** they SHALL see DeepSeek, MiMo, Kimi and CLI Proxy support, independently stored provider credentials and history preservation across model selection
- **AND** built-in search SHALL be described as DeepSeek-backed while MCP search remains supported
- **AND** compact K/M context status and bilingual context-guide links SHALL be available
- **AND** the displayed release version SHALL match package metadata
