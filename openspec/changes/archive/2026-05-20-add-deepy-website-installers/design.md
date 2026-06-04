## Context

Deepy already ships as the `deepy-cli` package and exposes the `deepy` command.
Current documentation expects users to install `uv`, understand the package name
versus command name distinction, and optionally edit `uv.toml` to configure a
China mirror. That is too much setup for users who are not familiar with Python,
`uv`, or package-manager configuration.

The website should be an install-focused static site for `deepy.kirineko.tech`.
It will live in an independent directory at first so it can be migrated to a
standalone Git repository after release.

## Goals / Non-Goals

**Goals:**

- Provide a compact, light-themed static website focused on installation.
- Offer copyable POSIX and Windows PowerShell installation commands.
- Offer standard and China mirror installation variants for each OS shell.
- Install Deepy through `uv tool install --python 3.13 deepy-cli`.
- Make the China mirror variant temporary and non-mutating by using
  `--default-index https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/`.
- Package the site with Docker and Docker Compose for straightforward release.
- Include a UI screenshot section and a stronger feature section that highlights
  Skill market and Rules alongside core terminal-agent features.

**Non-Goals:**

- Do not change the Deepy CLI package, command behavior, or release workflow.
- Do not implement a dynamic backend, account system, telemetry, or analytics.
- Do not modify user `uv.toml`, `pip.conf`, or other package-manager
  configuration files from installer scripts.
- Do not make the website a broad marketing site; it remains an install-first
  product page with three primary content regions.

## Decisions

### Use a standalone static site directory

The implementation will add a dedicated website directory containing static
HTML/CSS/JS assets, script files, and Docker release files. This keeps the
website independent from Deepy's Python package and makes the later repository
migration a directory move instead of a repo split.

Alternative considered: integrate the site into existing docs or README assets.
That would reduce files but would make Docker release packaging and later
migration less clean.

### Keep installers shell-specific

The website will expose POSIX and Windows PowerShell commands separately because
the shell syntax, execution policy behavior, and pipe invocation forms differ.
The user-facing page can present them behind tabs, but the hosted assets remain
separate scripts.

Alternative considered: a single universal bootstrap command. That is less
transparent and harder to make safe across shell families.

### Make China mirror install non-mutating

The China mirror scripts will not write persistent `uv` or `pip` configuration.
They will call:

```text
uv tool install --python 3.13 deepy-cli --default-index https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/
```

This improves domestic package download reliability without changing future
behavior of the user's Python tooling.

Alternative considered: writing `uv.toml` automatically. That gives a smoother
future upgrade path but can overwrite, conflict with, or surprise existing user
configuration.

### Use Docker only for website publishing

Docker and Docker Compose will package and serve the static site plus installer
scripts. They will not containerize Deepy itself or become a required install
path for end users.

Alternative considered: deploy directly as raw static files only. Docker adds a
small amount of boilerplate but makes repeatable release and server migration
simpler.

### Keep page content compact and action-oriented

The page will use three primary regions: install commands, UI screenshot, and
feature introduction. The install section is first because the site exists to
reduce setup friction. The feature section should use a denser grid and concise
copy rather than long prose or extra illustrations.

## Risks / Trade-offs

- [Risk] Users may expect the China mirror variant to persist for future upgrades.
  -> Mitigation: page copy and script output should state that the mirror applies
  only to the current install command and does not modify user config.
- [Risk] `uv` may need to download Python 3.13 from a source not accelerated by
  the PyPI mirror.
  -> Mitigation: keep this outside the first requirement, document it as a known
  limitation, and add a follow-up only after verifying a stable mirror for uv
  managed Python downloads.
- [Risk] Pipe-to-shell installers create trust concerns.
  -> Mitigation: provide visible links to the script files and keep scripts
  short, readable, and narrowly scoped.
- [Risk] Later repository migration could break script URLs.
  -> Mitigation: avoid repo-relative assumptions in page copy and serve scripts
  from stable root paths such as `/install.sh` and `/install-zh.ps1`.

## Migration Plan

1. Build the site in the independent website directory inside the current
   checkout.
2. Run local static validation and browser checks against the Docker-served site.
3. Publish the container or static assets for `deepy.kirineko.tech`.
4. After release validation, move the directory into the dedicated website
   repository without changing public URL paths.

Rollback is straightforward: revert the website deployment to the previous
static asset set or stop the Docker Compose service. The Deepy CLI package and
existing install methods are unaffected.

## Open Questions

- Which final UI screenshot path and filename should be used once the screenshot
  is provided?
- Should the website mention that the China mirror only accelerates package
  resolution, not necessarily uv managed-Python downloads, if no verified Python
  download mirror is added?
