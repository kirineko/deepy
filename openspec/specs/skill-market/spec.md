# skill-market Specification

## Purpose
TBD - created by archiving change add-agent-skill-market. Update Purpose after archive.
## Requirements
### Requirement: Market Catalog Query
Deepy SHALL query a configured skill market endpoint to browse and search installable skills.

#### Scenario: Browse market skills
- **WHEN** the user runs `/skills search`
- **THEN** Deepy fetches market skill records and displays names, descriptions, upload timestamps, and installed status when known

#### Scenario: Search market skills
- **WHEN** the user runs `/skills search pdf`
- **THEN** Deepy requests market records matching `pdf`

### Requirement: Market Skill Installation
Deepy SHALL download skill zip packages from the market, validate that they contain a standard `SKILL.md`, install them into `.agents/skills`, and record install metadata outside the skill directory.

#### Scenario: Install a market skill
- **WHEN** the user runs `/skills install pdf`
- **THEN** Deepy downloads the package for `pdf`
- **AND** installs the skill into `~/.agents/skills/pdf`
- **AND** records market URL, package identifier, version identifier, zip hash, install path, and install time under `~/.deepy`

### Requirement: Market Skill Uninstall
Deepy SHALL uninstall skills installed through the market while protecting locally modified skill content.

#### Scenario: Uninstall unchanged market skill
- **WHEN** the user runs `/skills uninstall pdf` and the installed content hash matches Deepy's install record
- **THEN** Deepy removes `~/.agents/skills/pdf` and removes the install record

#### Scenario: Refuse unsafe uninstall
- **WHEN** the user runs `/skills uninstall pdf` and the installed content hash differs from Deepy's install record
- **THEN** Deepy reports that the skill has local modifications and does not delete it by default

### Requirement: Upload-centered Market Service
The market service SHALL accept administrator-uploaded skill zip files, validate them, parse metadata from package content, and expose catalog and download endpoints.

#### Scenario: Admin uploads valid skill zip
- **WHEN** an administrator uploads a zip containing a valid `SKILL.md`
- **THEN** the market service stores the original zip
- **AND** stores an extracted snapshot for validation and preview
- **AND** creates database records using parsed skill metadata and upload event metadata

#### Scenario: Admin uploads invalid skill zip
- **WHEN** an administrator uploads a zip with no valid `SKILL.md`
- **THEN** the market service rejects the upload and does not create a catalog record

### Requirement: Market Service Metadata
The market service SHALL only persist metadata available from the uploaded package, file content, archive inspection, server-side hashing, and upload event.

#### Scenario: Persist uploaded skill metadata
- **WHEN** a valid skill package is uploaded
- **THEN** the service stores skill name, description, optional license, optional compatibility, optional metadata JSON, version label, upload timestamp, zip filename, size, sha256, extracted path, and active status

### Requirement: Version-ready Market Records
The market service SHALL allow multiple uploaded versions per skill while returning the latest active version by default.

#### Scenario: Download latest active version
- **WHEN** a user downloads a skill by name
- **THEN** the market service returns the latest active uploaded version for that skill
