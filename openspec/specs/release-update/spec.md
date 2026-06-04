# Release And Update Specification

## Purpose

Deepy is released through GitHub and PyPI while update prompts stay aligned with
the PyPI package users actually install.

## Requirements

### Requirement: PyPI Distribution

Deepy SHALL publish the Python distribution under the package name `deepy-cli`.

#### Scenario: Package is built

- **WHEN** release artifacts are built
- **THEN** they SHALL produce `deepy_cli-<version>.tar.gz` and
  `deepy_cli-<version>-py3-none-any.whl`

### Requirement: Command Name Stability

Deepy SHALL keep the installed command name `deepy` even though the package name
is `deepy-cli`.

#### Scenario: Wheel entry points are inspected

- **WHEN** a wheel is built
- **THEN** its console script entry point SHALL map `deepy` to `deepy.cli:main`

### Requirement: Trusted Publishing

Deepy SHALL publish to PyPI through GitHub Actions Trusted Publishing.

#### Scenario: Release tag is pushed

- **WHEN** a semantic version tag matching `*.*.*` is pushed
- **THEN** GitHub Actions SHALL run tests, lint, type check, build, and `uv publish`
- **AND** publishing SHALL use the `pypi` GitHub environment with OIDC

### Requirement: PyPI-Only Update Check

Deepy SHALL check only PyPI for startup version update hints.

#### Scenario: Startup checks for an update

- **WHEN** interactive mode starts
- **THEN** Deepy SHALL query `https://pypi.org/pypi/deepy-cli/json`
- **AND** it SHALL NOT use GitHub tags or releases as an update source
- **AND** it SHALL suggest `uv tool upgrade deepy-cli` only when PyPI reports a
  newer version
