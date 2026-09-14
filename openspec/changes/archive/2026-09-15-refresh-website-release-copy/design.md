## Context
Provider and history changes are implemented and archived. The website needs matching public copy.

## Goals / Non-Goals
Describe shipped behavior concisely and publish 0.2.33. Preserve the page layout and installation workflow.

## Decisions
Keep existing static HTML and assets. Identify provider-specific image capabilities through documentation instead of promising all models support images. Separate DeepSeek-backed search from local WebFetch and existing MCP search priority.

## Risks / Trade-offs
Existing screenshots are illustrative and can show older UI; captions will say so. CLI Proxy limits are deployment dependent.

## Migration Plan
Validate documentation and release metadata, run gates, archive, commit, tag and push. Verify both Actions and published artifacts.
