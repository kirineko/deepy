from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from deepy.skills import read_skill_info
from deepy.utils import json as json_utils


DEFAULT_MARKET_URL = "https://skill.kirineko.tech"
INSTALL_RECORD_VERSION = 1


@dataclass(frozen=True)
class MarketSkill:
    name: str
    description: str = ""
    uploaded_at: str = ""
    version: str = ""
    sha256: str = ""
    installed: bool = False


@dataclass(frozen=True)
class InstalledSkill:
    name: str
    scope: str
    install_path: Path
    market_url: str
    version_id: str
    version: str
    sha256: str
    content_hash: str
    installed_at: str
    uploaded_at: str = ""


def market_base_url() -> str:
    return (os.environ.get("DEEPY_SKILL_MARKET_URL") or DEFAULT_MARKET_URL).rstrip("/")


def installed_records_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".deepy" / "skill-market" / "installed.json"


def user_skills_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".agents" / "skills"


def project_skills_dir(project_root: Path) -> Path:
    return project_root / ".agents" / "skills"


def search_market_skills(query: str = "", *, base_url: str | None = None) -> list[MarketSkill]:
    url = f"{base_url or market_base_url()}/api/skills"
    if query:
        url += "?" + urllib.parse.urlencode({"q": query})
    payload = _get_json(url)
    rows = payload.get("skills", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    installed = {record.name for record in list_installed_skills()}
    skills: list[MarketSkill] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _string(row, "name")
        if not name:
            continue
        skills.append(
            MarketSkill(
                name=name,
                description=_string(row, "description"),
                uploaded_at=_string(row, "uploaded_at") or _string(row, "uploadedAt"),
                version=_string(row, "version"),
                sha256=_string(row, "sha256"),
                installed=name in installed,
            )
        )
    return skills


def get_market_skill(name: str, *, base_url: str | None = None) -> MarketSkill:
    url = f"{base_url or market_base_url()}/api/skills/{urllib.parse.quote(name)}"
    row = _get_json(url)
    if not isinstance(row, dict):
        raise ValueError(f"Invalid market skill response for {name}")
    skill_name = _string(row, "name")
    if not skill_name:
        raise ValueError(f"Market skill response is missing a name for {name}")
    return MarketSkill(
        name=skill_name,
        description=_string(row, "description"),
        uploaded_at=_string(row, "uploaded_at") or _string(row, "uploadedAt"),
        version=_string(row, "version"),
        sha256=_string(row, "sha256"),
        installed=any(record.name == skill_name for record in list_installed_skills()),
    )


def install_market_skill(
    name: str,
    *,
    base_url: str | None = None,
    home: Path | None = None,
    project_root: Path | None = None,
    scope: Literal["user", "project"] = "user",
) -> InstalledSkill:
    root = _install_root(scope=scope, home=home, project_root=project_root)
    root.mkdir(parents=True, exist_ok=True)
    resolved_base_url = base_url or market_base_url()
    latest = get_market_skill(name, base_url=resolved_base_url)
    url = f"{resolved_base_url}/api/skills/{urllib.parse.quote(name)}/download"
    package = _get_bytes(url)
    zip_hash = hashlib.sha256(package).hexdigest()
    if latest.sha256 and latest.sha256 != zip_hash:
        raise ValueError(f"Downloaded package hash mismatch for {name}")
    with tempfile.TemporaryDirectory(prefix="deepy-skill-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "skill.zip"
        zip_path.write_bytes(package)
        extract_root = tmp_path / "extract"
        extract_root.mkdir()
        _safe_extract(zip_path, extract_root)
        skill_path = _find_single_skill(extract_root)
        skill = read_skill_info(skill_path, scope="user")
        if skill is None:
            raise ValueError("Downloaded package does not contain a valid SKILL.md")
        dest = root / skill.name
        if dest.exists():
            raise FileExistsError(f"Skill already exists: {dest}")
        shutil.copytree(skill_path.parent, dest)
    content_hash = hash_directory(dest)
    record = InstalledSkill(
        name=skill.name,
        scope=scope,
        install_path=dest,
        market_url=resolved_base_url,
        version_id=latest.version or latest.sha256 or zip_hash,
        version=latest.version,
        sha256=latest.sha256 or zip_hash,
        content_hash=content_hash,
        installed_at=datetime.now(UTC).isoformat(),
        uploaded_at=latest.uploaded_at,
    )
    records = [item for item in list_installed_skills(home=home) if item.name != record.name]
    records.append(record)
    write_installed_skills(records, home=home)
    return record


def _install_root(
    *,
    scope: Literal["user", "project"],
    home: Path | None = None,
    project_root: Path | None = None,
) -> Path:
    if scope == "user":
        return user_skills_dir(home)
    if project_root is None:
        raise ValueError("project_root is required for project skill installation")
    return project_skills_dir(project_root)


def update_market_skill(
    name: str,
    *,
    base_url: str | None = None,
    home: Path | None = None,
) -> tuple[str, InstalledSkill]:
    records = list_installed_skills(home=home)
    record = next((item for item in records if item.name == name), None)
    if record is None:
        raise ValueError(f"Skill was not installed by Deepy market: {name}")
    if record.install_path.exists() and hash_directory(record.install_path) != record.content_hash:
        raise RuntimeError(f"Skill has local modifications: {record.install_path}")
    latest = get_market_skill(name, base_url=base_url or record.market_url)
    if latest.sha256 and latest.sha256 == record.sha256:
        return "unchanged", record

    package = _get_bytes(
        f"{base_url or record.market_url}/api/skills/{urllib.parse.quote(name)}/download"
    )
    zip_hash = hashlib.sha256(package).hexdigest()
    if latest.sha256 and latest.sha256 != zip_hash:
        raise ValueError(f"Downloaded package hash mismatch for {name}")
    with tempfile.TemporaryDirectory(prefix="deepy-skill-update-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "skill.zip"
        zip_path.write_bytes(package)
        extract_root = tmp_path / "extract"
        extract_root.mkdir()
        _safe_extract(zip_path, extract_root)
        skill_path = _find_single_skill(extract_root)
        skill = read_skill_info(skill_path, scope="user")
        if skill is None:
            raise ValueError("Downloaded package does not contain a valid SKILL.md")
        if skill.name != record.name:
            raise ValueError(f"Updated package name mismatch: {skill.name} != {record.name}")
        if record.install_path.exists():
            shutil.rmtree(record.install_path)
        shutil.copytree(skill_path.parent, record.install_path)
    updated = InstalledSkill(
        name=record.name,
        scope=record.scope,
        install_path=record.install_path,
        market_url=base_url or record.market_url,
        version_id=latest.version or latest.sha256 or zip_hash,
        version=latest.version,
        sha256=latest.sha256 or zip_hash,
        content_hash=hash_directory(record.install_path),
        installed_at=datetime.now(UTC).isoformat(),
        uploaded_at=latest.uploaded_at,
    )
    write_installed_skills([updated if item.name == name else item for item in records], home=home)
    return "updated", updated


def uninstall_market_skill(name: str, *, home: Path | None = None, force: bool = False) -> str:
    records = list_installed_skills(home=home)
    record = next((item for item in records if item.name == name), None)
    if record is None:
        raise ValueError(f"Skill was not installed by Deepy market: {name}")
    if record.install_path.exists():
        current_hash = hash_directory(record.install_path)
        if current_hash != record.content_hash and not force:
            raise RuntimeError(f"Skill has local modifications: {record.install_path}")
        shutil.rmtree(record.install_path)
    write_installed_skills([item for item in records if item.name != name], home=home)
    return name


def list_installed_skills(*, home: Path | None = None) -> list[InstalledSkill]:
    path = installed_records_path(home)
    if not path.is_file():
        return []
    try:
        payload = json_utils.loads(path.read_text(encoding="utf-8"))
    except (OSError, json_utils.JSONDecodeError):
        return []
    rows = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    records: list[InstalledSkill] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _string(row, "name")
        install_path = _string(row, "install_path")
        if not name or not install_path:
            continue
        records.append(
            InstalledSkill(
                name=name,
                scope=_string(row, "scope") or "user",
                install_path=Path(install_path).expanduser(),
                market_url=_string(row, "market_url") or DEFAULT_MARKET_URL,
                version_id=_string(row, "version_id"),
                version=_string(row, "version"),
                sha256=_string(row, "sha256"),
                content_hash=_string(row, "content_hash"),
                installed_at=_string(row, "installed_at"),
                uploaded_at=_string(row, "uploaded_at"),
            )
        )
    return records


def write_installed_skills(records: list[InstalledSkill], *, home: Path | None = None) -> None:
    path = installed_records_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": INSTALL_RECORD_VERSION,
        "skills": [
            {
                "name": record.name,
                "scope": record.scope,
                "install_path": str(record.install_path),
                "market_url": record.market_url,
                "version_id": record.version_id,
                "version": record.version,
                "sha256": record.sha256,
                "content_hash": record.content_hash,
                "installed_at": record.installed_at,
                "uploaded_at": record.uploaded_at,
            }
            for record in sorted(records, key=lambda item: item.name)
        ],
    }
    path.write_text(json_utils.dumps(payload), encoding="utf-8")


def hash_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        rel = file_path.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _safe_extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (dest / member.filename).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError(f"Unsafe path in zip: {member.filename}")
        archive.extractall(dest)


def _find_single_skill(root: Path) -> Path:
    candidates = [path for path in root.rglob("SKILL.md") if path.is_file()]
    if not candidates:
        raise ValueError("Package does not contain SKILL.md")
    if len(candidates) > 1:
        raise ValueError("Package contains multiple SKILL.md files; upload a single skill package")
    return candidates[0]


def _get_json(url: str) -> Any:
    data = _get_bytes(url)
    try:
        return json_utils.loads(data.decode("utf-8"))
    except json_utils.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response from {url}") from exc


def _get_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Failed to reach skill market: {exc}") from exc


def _string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""
