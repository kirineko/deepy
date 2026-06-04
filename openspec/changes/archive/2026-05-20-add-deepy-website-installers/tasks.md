## 1. Website Structure

- [x] 1.1 Create a dedicated website directory for the static site, public assets, installer scripts, and release configuration.
- [x] 1.2 Add root-relative routing or static server configuration so `/`, `/install.sh`, `/install.ps1`, `/install-zh.sh`, and `/install-zh.ps1` are stable public paths.
- [x] 1.3 Add a placeholder or documented asset path for the future Deepy UI screenshot without blocking local rendering.

## 2. Installer Scripts

- [x] 2.1 Implement the POSIX standard installer script that installs uv when missing and runs `uv tool install --python 3.13 deepy-cli`.
- [x] 2.2 Implement the Windows PowerShell standard installer script that installs uv when missing and runs `uv tool install --python 3.13 deepy-cli`.
- [x] 2.3 Implement the POSIX China mirror installer script that installs Deepy with `--default-index https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/`.
- [x] 2.4 Implement the Windows PowerShell China mirror installer script that installs Deepy with `--default-index https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/`.
- [x] 2.5 Ensure installer scripts do not create, overwrite, or append to `uv.toml`, `pip.conf`, or persistent mirror configuration.
- [x] 2.6 Add concise script output that identifies the install mode and explains that China mirror mode only applies to the current install command.

## 3. Static Page

- [x] 3.1 Build the light, compact installation-first page with OS tabs and standard versus China mirror mode selection.
- [x] 3.2 Add copy buttons and inspect-script links for each visible install command.
- [x] 3.3 Add the UI screenshot preview section using the configured screenshot asset path.
- [x] 3.4 Add the feature introduction section with DeepSeek thinking, reviewable diff, shell execution, WebSearch/WebFetch, long-session continuity, Skill market, and Rules.
- [x] 3.5 Verify desktop and mobile layouts keep text readable, controls non-overlapping, and the feature section easy to scan.

## 4. Docker Release

- [x] 4.1 Add a Dockerfile that serves only the static website and installer script assets.
- [x] 4.2 Add Docker Compose configuration for running the website locally and in the release environment.
- [x] 4.3 Add web server configuration that serves installer scripts with plain text content types and disables accidental redirects for script paths.

## 5. Verification

- [x] 5.1 Run local static checks or formatting checks for the website files.
- [x] 5.2 Start the site through Docker Compose and verify the homepage and four installer script URLs respond successfully.
- [x] 5.3 Use a browser check to verify the install tabs, mode selection, copy buttons, script links, screenshot section, and feature grid.
- [x] 5.4 Inspect all installer scripts and confirm they install with Python 3.13 and do not write persistent package-manager configuration.
- [x] 5.5 Run `openspec validate add-deepy-website-installers --type change --strict` before implementation is considered complete.
