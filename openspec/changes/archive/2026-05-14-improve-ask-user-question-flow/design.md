## Context

AskUserQuestion is implemented as a normal function tool. The model receives tool documentation, emits a tool call with a `questions` argument, the runtime returns a structured JSON result with `awaitUserResponse=true`, the runner converts that into `RunSummary(status="waiting_for_user")`, and the terminal prompts for answers.

The current design has two rough edges:

- The terminal treats AskUserQuestion like any other tool call, so its raw `questions` JSON appears in progress output.
- The interactive loop only handles one `waiting_for_user` summary after the original prompt. If the model asks a follow-up question after the first answer, the second pending question is not collected.

## Goals / Non-Goals

**Goals:**

- Preserve the existing AskUserQuestion tool contract and session format.
- Make AskUserQuestion feel like a first-class terminal interaction rather than visible tool plumbing.
- Support multiple clarification rounds within one user turn.
- Give the model clearer guidance for when proactive clarification is appropriate.
- Keep tests focused around the regression surface.

**Non-Goals:**

- Replace AskUserQuestion with a separate UI-only mechanism.
- Add a new transport protocol or dependency.
- Redesign non-terminal app state beyond preserving compatibility with existing pending-question parsing.
- Change the public schema of AskUserQuestion arguments or results.

## Decisions

### Keep AskUserQuestion as a tool-level pause signal

Deepy should keep using `awaitUserResponse=true` and `metadata.kind="ask_user_question"` as the pause signal. This avoids a migration and keeps existing parsing in `runner`, `ask_user_question`, session replay, and app state useful.

Alternative considered: introduce a separate runner event type that bypasses tool output. That would reduce coupling to tool JSON, but it would require larger changes across stream normalization, session persistence, and history replay.

### Handle repeated pending-question summaries with a bounded loop

The terminal should continue the current interactive turn while each run returns `status="waiting_for_user"`. For every pending-question summary, it should collect answers, send the synthetic answer text back into the same session, and repeat until the model completes or no response is available.

The loop should have a small defensive maximum to avoid pathological clarification loops. If the maximum is hit, Deepy should stop and show the latest summary/status rather than silently spinning.

Alternative considered: allow exactly two rounds. That fixes the observed bug but leaves the same structural failure for third-round clarification.

### Treat AskUserQuestion rendering as a specialized display case

Tool-call summaries should hide AskUserQuestion arguments. Tool-output summaries may keep a concise status such as `AskUserQuestion ok - Waiting for user input.` because the actual question UI is rendered separately.

Alternative considered: make all tool parameter summaries shorter. That would risk losing useful context for `read`, `shell`, and file-edit tools.

### Do not print synthetic answer protocol as user input

The formatted response sent back to the model is an internal protocol message. The terminal should either omit it from user-facing output or render a human-readable answer summary that does not pretend to be raw user input.

Alternative considered: keep printing the synthetic response because it is transparent. The observed screenshot shows it creates noise and exposes implementation details.

### Clarification guidance should be intent-driven, not only blocked-state-driven

Prompt and tool documentation should say AskUserQuestion is appropriate when user intent, scope, preferences, or high-impact decisions are unclear. It should still discourage asking for low-impact details that Deepy can reasonably infer.

Alternative considered: leave the conservative "only when blocked" guidance. That misses the user’s desired behavior and makes the tool appear to require explicit user instruction.

## Risks / Trade-offs

- Clarification loops could become annoying or infinite -> add a defensive round limit and keep prompt guidance focused on high-impact ambiguity.
- Hiding parameters could remove useful debugging context -> keep structured data in sessions/tool output while only suppressing normal user-facing summaries.
- Updated guidance could cause over-questioning -> include explicit guidance to proceed with reasonable assumptions for low-impact choices.
- Localized prompt labels may be inconsistent across languages -> use neutral wording and avoid introducing full localization scope in this change.
