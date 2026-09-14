## ADDED Requirements

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
