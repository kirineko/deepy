## 1. Config Catalog

- [x] 1.1 Add localhost constants, model catalog, thinking modes, and `ProviderInfo.api` field in `src/deepy/config/providers.py`
- [x] 1.2 Extend provider inference, reasoning normalization, thinking enablement, and effort mapping for localhost
- [x] 1.3 Update `ModelConfig.reasoning_mode` in `schema.py` and provider validation messages in `config_io.py`
- [x] 1.4 Export new localhost constants from `settings.py` / `__init__.py`

## 2. LLM Responses Path

- [x] 2.1 Branch `build_provider_bundle` to construct `OpenAIResponsesModel` when `provider_info.api == "responses"`
- [x] 2.2 Build localhost `ModelSettings` with `Reasoning(effort=...)` and empty chat thinking `extra_body`
- [x] 2.3 Allowlist localhost GPT-5.6 models in `model_supports_image_input`
- [x] 2.4 Make localhost input suggestions use `gpt-5.6-luna` with Chat Completions `reasoning_effort=none`

## 3. UI and CLI Surfaces

- [x] 3.1 Add localhost thinking-mode picker choices in `model_picker.py`
- [x] 3.2 Update CLI `--provider` help and any hard-coded provider lists for localhost

## 4. Tests and Verification

- [x] 4.1 Add/update config tests for localhost catalog, inference, and reasoning normalization
- [x] 4.2 Add/update provider, multimodal, and input-suggestion tests for Responses/settings behavior
- [x] 4.3 Run focused tests plus `ruff`, `ty`, and full `pytest`
- [x] 4.4 Validate OpenSpec change with `openspec validate add-localhost-provider --type change --strict`
