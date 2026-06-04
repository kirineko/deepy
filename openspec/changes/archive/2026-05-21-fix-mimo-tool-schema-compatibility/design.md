## Context

Deepy exposes built-in tools through the OpenAI Agents SDK. Several schemas use
the strict OpenAI pattern where optional arguments are represented as nullable
properties that still appear in `required`. For example, `read_file` currently
requires `offset`, `limit`, and `pages`, while each accepts `null`.

MiMo behaves differently from DeepSeek for this schema shape. Live API
investigation showed:

- Xiaomi MiMo returns standard OpenAI `message.tool_calls` for simple tools.
- Xiaomi MiMo returns standard `tool_calls` when optional fields are represented
  as ordinary non-null optional fields, even when `strict=true` remains present.
- Xiaomi MiMo fails when nullable fields are included in `required`; some edit
  tool calls can also fail when nullable optional fields remain in the schema.
  Direct Xiaomi responses may place an XML-like `<tool_call>` block in
  assistant content instead of `message.tool_calls`.
- OpenRouter-hosted `xiaomi/mimo-v2.5` shows the same root behavior, except the
  failing case may produce no content and no tool call, leaving only reasoning
  deltas visible in Deepy.
- Xiaomi direct MiMo has a second compatibility requirement: in thinking mode,
  multi-turn follow-up requests must include the prior assistant
  `reasoning_content`. Without it, the tool result follow-up request fails with
  `400 Param Incorrect`.

The problem is therefore not that MiMo lacks tool calling. It is that MiMo is
not compatible with Deepy's strict nullable-required schema shape.

## Goals / Non-Goals

**Goals:**

- Make built-in tool calls work for Xiaomi MiMo and OpenRouter-hosted Xiaomi
  MiMo models.
- Keep tool runtime behavior unchanged: omitted optional arguments continue to
  use the same defaults as explicit `null`.
- Keep existing DeepSeek and legacy provider behavior unchanged.
- Preserve strict schema mode for MiMo when possible; only remove nullable
  optional parameters from `required`.
- Replay prior Xiaomi direct MiMo `reasoning_content` when tool calls create a
  thinking-enabled multi-turn request.
- Cover the compatibility transformation with focused tests.

**Non-Goals:**

- Parsing MiMo's XML-like `<tool_call>` assistant content as a fallback tool
  protocol.
- Changing the public tool names or user-facing command surface.
- Reworking all tools to a new schema style for every provider.
- Solving MiMo reasoning token budget behavior; that remains a separate model
  output-budget issue.

## Decisions

1. Add provider/model-aware tool schema compatibility at agent construction.

   Deepy should decide whether to apply MiMo compatibility using resolved model
   settings:

   - provider `xiaomi` with model `mimo-v2.5` or `mimo-v2.5-pro`
   - provider `openrouter` with model id matching `xiaomi/mimo-v2.5` or
     `xiaomi/mimo-v2.5-pro`

   The compatibility flag should flow into tool construction so the model sees a
   provider-appropriate schema without changing the runtime invocation code.

   Alternative considered: always use optional nullable schemas. That may work
   broadly, but it changes the model-visible strict schema contract for
   DeepSeek without need.

2. Transform nullable optional fields for MiMo.

   For MiMo-compatible schemas, recursively inspect object schemas and remove a
   property name from `required` when that property's `type` includes `null`.
   Then remove `null` from the property's model-visible type so it remains an
   ordinary optional field. Leave descriptions and `additionalProperties`
   intact.

   Example:

   ```json
   {
     "properties": {
       "file_path": {"type": "string"},
       "offset": {"type": ["number", "null"]}
     },
     "required": ["file_path", "offset"]
   }
   ```

   becomes:

   ```json
   {
     "properties": {
       "file_path": {"type": "string"},
       "offset": {"type": "number"}
     },
     "required": ["file_path"]
   }
   ```

   Alternative considered: only remove fields from `required` while keeping
   nullable types. Live edit tests showed MiMo can still emit pseudo tool calls
   for `edit_text` with optional nullable fields, so MiMo needs the extra
   non-null optional simplification.

3. Treat omitted optional arguments like `null`.

   Deepy's current tool argument parsing already defaults missing optional
   values:

   - `read_file.offset` defaults to line 1
   - `read_file.limit` and `read_file.pages` default to `None`
   - optional edit/write safety fields default to their existing fallback values

   The compatibility layer should rely on these defaults rather than changing
   tool runtime code.

4. Do not parse XML-like pseudo tool calls.

   MiMo's XML-like output is a failure mode, not a stable protocol. Parsing it
   would duplicate model/tool routing outside the Agents SDK and would be
   fragile across providers. The safer fix is to keep MiMo on the standard
   `message.tool_calls` path by giving it a compatible schema.

5. Replay reasoning content only for direct Xiaomi MiMo.

   Xiaomi's API requires `reasoning_content` to be passed back in multi-turn
   thinking-mode requests. Deepy already uses the Agents SDK's reasoning replay
   hook for DeepSeek. Extend that hook to return true for direct Xiaomi MiMo
   requests where `base_url` is Xiaomi's official API and the selected model is
   `mimo-v2.5` or `mimo-v2.5-pro`.

   OpenRouter-hosted MiMo should not use this Xiaomi-specific replay path,
   because OpenRouter's reasoning protocol is different and live testing showed
   OpenRouter MiMo tool follow-ups work without Xiaomi `reasoning_content`.

## Risks / Trade-offs

- [Risk] Some tools have nested schemas, especially structured patch
  operations. -> Mitigation: make the nullable-required transformation
  recursive and test representative nested schema cases.
- [Risk] OpenRouter custom models may not be MiMo but still use provider
  `openrouter`. -> Mitigation: gate compatibility by model id prefix, not only
  by provider.
- [Risk] Future MiMo models may change ids. -> Mitigation: keep the detection
  helper small and easy to extend.
- [Risk] A model may omit an optional safety field such as `expected_hash`. ->
  Mitigation: existing runtime safety checks already treat absent and `null`
  consistently; tests should assert behavior for omitted arguments.
- [Risk] Reasoning replay sent to the wrong provider may break otherwise
  working OpenRouter requests. -> Mitigation: gate Xiaomi replay by official
  Xiaomi base URL and direct MiMo model id.

## Migration Plan

No config migration is required. The change affects only model-visible tool
schemas during agent construction for MiMo-compatible models. Rollback is to
disable the compatibility flag and return to the current tool schema builder.

## Open Questions

- Should provider/model-compatible schema transformation also apply to MCP tools
  if future MiMo users rely on MCP tool calls, or should this change remain
  scoped to Deepy's built-in tools first?
