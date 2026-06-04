## Why

Deepy currently asks new users to understand `uv`, Python installation, and mirror
configuration before they can install the CLI. A dedicated website for
`deepy.kirineko.tech` can make installation safer and faster, especially for
Windows and China-based users who may not know how to configure Python tooling.

## What Changes

- Add an independent static website directory that can later be migrated into its
  own repository.
- Provide OS-specific one-line installation commands for POSIX shells and Windows
  PowerShell.
- Provide standard and China mirror installation scripts for each supported shell.
- Ensure all installation scripts install Deepy with `uv tool install --python
  3.13 deepy-cli`.
- Ensure China mirror scripts use the Tsinghua PyPI mirror only for the install
  command via `--default-index
  https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/`.
- Do not write, create, or modify user `uv.toml`, `pip.conf`, shell profiles
  beyond the upstream `uv` installer behavior, or other global package-manager
  configuration files.
- Package the static site for release through Docker and Docker Compose.
- Design the page as a light, compact install-focused site with three primary
  sections: installation commands, UI screenshot preview, and feature
  introduction.
- Strengthen the feature section to include Skill market and Rules alongside
  core terminal agent features.

## Capabilities

### New Capabilities

- `website-installation`: Static website, hosted installer scripts, Docker
  release packaging, and page content contract for helping users install Deepy.

### Modified Capabilities

- None.

## Impact

- Adds a new standalone website directory and release files.
- Adds four installer script assets: POSIX standard, POSIX China mirror, Windows
  PowerShell standard, and Windows PowerShell China mirror.
- Adds Docker and Docker Compose configuration for serving the static site and
  scripts.
- Does not change the Deepy Python package, CLI runtime behavior, PyPI release
  workflow, or existing user configuration format.
