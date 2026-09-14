# Verification

- Full release suite: 1,102 passed in 62.83 seconds.
- Landing-page version, asset and bilingual context-link checks: 2 passed separately.
- Ruff and ty passed; wheel and sdist built successfully.
- CLI reports Deepy 0.2.33; package metadata and lock match.
- Strict change validation passed. Archive synchronizes the landing-page requirement before the release commit.

## CI release follow-up

Initial PyPI workflow 34881415327 stopped before publication: the model-switch
attachment test closed its Textual app after settings changed but before its
command worker finished updating/focusing the prompt. It now submits with Pilot
Enter and awaits worker completion before continuing or closing. No runtime
behavior changed. The focused test passed; all 146 Modern UI tests passed in
50.20 seconds, and Ruff/ty passed. PyPI confirmed version 0.2.33 was absent before
retargeting the failed release tag with an exact remote lease.
