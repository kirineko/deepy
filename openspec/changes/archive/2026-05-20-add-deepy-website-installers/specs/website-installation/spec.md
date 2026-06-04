## ADDED Requirements

### Requirement: Static Website Packaging

Deepy SHALL provide an independent static website directory for
`deepy.kirineko.tech` that can later be migrated to a standalone repository.

#### Scenario: Website files are isolated

- **WHEN** the website is implemented
- **THEN** website source files, public assets, installer scripts, and release
  configuration SHALL live under one dedicated website directory
- **AND** the Deepy Python package source SHALL NOT be required to serve the
  website

#### Scenario: Website is served by Docker Compose

- **WHEN** the website release is started through Docker Compose
- **THEN** the static website and installer scripts SHALL be served by the
  containerized web server
- **AND** the Docker setup SHALL NOT install or run the Deepy CLI itself

### Requirement: OS-Specific Installer Commands

The website SHALL present separate one-line installation commands for POSIX
shells and Windows PowerShell.

#### Scenario: POSIX standard install command is shown

- **WHEN** a user selects the macOS or Linux standard installation option
- **THEN** the website SHALL show a command that downloads `/install.sh` and
  executes it with a POSIX shell

#### Scenario: Windows standard install command is shown

- **WHEN** a user selects the Windows standard installation option
- **THEN** the website SHALL show a PowerShell command that downloads
  `/install.ps1` and executes it in PowerShell

#### Scenario: China mirror commands are shown separately

- **WHEN** a user selects the China mirror installation option
- **THEN** the website SHALL show the OS-appropriate `install-zh` script command
- **AND** it SHALL keep the standard and China mirror commands visually distinct

### Requirement: Installer Script Behavior

Deepy installer scripts SHALL install `uv` when needed and then install
`deepy-cli` with Python 3.13.

#### Scenario: Existing uv is reused

- **WHEN** an installer script runs on a machine where `uv` is already available
- **THEN** the script SHALL reuse the existing `uv` command
- **AND** it SHALL install Deepy with `uv tool install --python 3.13 deepy-cli`

#### Scenario: uv is missing

- **WHEN** an installer script runs on a machine where `uv` is not available
- **THEN** the script SHALL invoke the upstream uv installer for that shell family
- **AND** it SHALL verify that `uv` is available before installing Deepy

#### Scenario: China mirror install uses a temporary package index

- **WHEN** a China mirror installer script installs Deepy
- **THEN** it SHALL invoke `uv tool install --python 3.13 deepy-cli
  --default-index https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/`
- **AND** it SHALL NOT require users to manually configure a Python package
  mirror

#### Scenario: Installer avoids persistent package-manager configuration

- **WHEN** any Deepy website installer script runs
- **THEN** it SHALL NOT create, overwrite, or append to user `uv.toml`
- **AND** it SHALL NOT create, overwrite, or append to user `pip.conf`
- **AND** it SHALL NOT persist the Tsinghua mirror as a global Python tooling
  default

### Requirement: Install-Focused Page Content

The website SHALL prioritize installation while still showing a UI preview and a
concise feature overview.

#### Scenario: Page has three primary sections

- **WHEN** a user opens the website
- **THEN** the page SHALL present installation commands, a UI screenshot preview,
  and feature introduction as the primary content sections
- **AND** the installation section SHALL appear before the screenshot and feature
  sections

#### Scenario: UI screenshot is included

- **WHEN** a UI screenshot asset is available
- **THEN** the page SHALL display the screenshot in the UI preview section
- **AND** the layout SHALL preserve a compact light visual style around the
  screenshot

#### Scenario: Feature overview covers core capabilities

- **WHEN** a user reviews the feature introduction section
- **THEN** the page SHALL include DeepSeek thinking, reviewable file diff, shell
  execution, WebSearch/WebFetch, long-session continuity, Skill market, and
  Rules as visible feature items
- **AND** the feature section SHALL use concise text suitable for scanning rather
  than long-form documentation

### Requirement: Script Transparency

The website SHALL make installer scripts easy to inspect before execution.

#### Scenario: User can inspect installer scripts

- **WHEN** installation commands are shown
- **THEN** the page SHALL provide links to the corresponding script files
- **AND** each script file SHALL be served from a stable root-relative path

#### Scenario: Script output explains mirror scope

- **WHEN** a China mirror installer script runs
- **THEN** its output SHALL indicate that the Tsinghua mirror applies to the
  current install command
- **AND** its output SHALL NOT claim that user Python tooling configuration has
  been changed
