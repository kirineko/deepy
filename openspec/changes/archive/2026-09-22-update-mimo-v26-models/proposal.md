## Why

Deepy currently offers MiMo V2.5 and V2.5 Pro, which Xiaomi schedules to retire on 2026-10-21 at 10:00 Asia/Shanghai. MiMo V2.6 Flash and Pro are available through the existing Responses endpoint, and both passed text, image, function-call generation and streaming reasoning probes using the environment credential on 2026-09-22.

## What Changes

- **BREAKING**: Replace `mimo-v2.5` and `mimo-v2.5-pro` with `mimo-v2.6-flash` and `mimo-v2.6-pro` in the supported MiMo catalog. Reject retired IDs with specific replacement guidance without silently rewriting configuration.
- Use V2.6 Flash as the default MiMo model and fixed input-suggestion model; retain `enabled`/`disabled` thinking modes and disabled thinking for suggestions.
- Enable Responses image input for both new models throughout prompt, Read, history and subagent paths.
- Retain direct-MiMo tool-schema compatibility for the new models.
- Record the nominal 1M context as a conservative 1,000,000-token runtime window and the documented 131,072-token maximum output, preserving the existing default request budget.
- Update model selection/help, English and Chinese documentation, website model copy, and behavior tests together.
- Scope this update to text and images in Deepy. Native audio/video input, media generation, the custom-service UltraSpeed model, release/version changes and automatic configuration migration are excluded.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configuration`: Replace the MiMo catalog/default, mark both models image capable, and define actionable retired-model/profile-limit errors.
- `image-understanding-input`: Allow both V2.6 models and remove the old Pro-specific image prohibition.
- `input-suggestions`: Use V2.6 Flash with thinking disabled.
- `deepseek-provider`: Apply the existing direct-MiMo Responses tool compatibility to both V2.6 models.
- `model-context-budget`: Specify current MiMo model limits and evidence boundaries.
- `terminal-ui`: Update direct model commands and discovery examples to V2.6.

## Impact

Affected code includes `src/deepy/config/{providers,schema,model_limits}.py`, model selection/configuration validation consumers, `src/deepy/input_suggestions.py`, `src/deepy/llm/agent.py`, and classic/modern UI help. Tests cover configuration (including inactive profiles and retired model-limit overrides), Responses images and tool loops, suggestions, subagents and both UIs. README translations, model-context documentation and `index.html` need matching copy.

Saved V2.5 profiles require explicit user edits, including any model-keyed limit overrides. Existing session history remains intact. The provider ID, endpoint, environment key name and API transport stay the same; no new dependency is required.
