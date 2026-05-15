from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from deepy import skill_market


def _zip_bytes(name: str = "demo") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"---\nname: {name}\ndescription: Demo skill\n---\nUse demo.",
        )
    return buf.getvalue()


def _zip_bytes_with_body(name: str, body: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"---\nname: {name}\ndescription: Demo skill\n---\n{body}",
        )
    return buf.getvalue()


def _market_skill_payload(name: str = "demo", package: bytes | None = None) -> dict[str, str]:
    package = package or _zip_bytes(name)
    return {
        "name": name,
        "description": "Demo skill",
        "version": "1.2.3",
        "sha256": skill_market.hashlib.sha256(package).hexdigest(),
        "uploaded_at": "2026-05-15T00:00:00+00:00",
    }


def test_install_market_skill_writes_standard_skill_and_record(monkeypatch, tmp_path):
    package = _zip_bytes()
    monkeypatch.setattr(skill_market, "_get_json", lambda _url: _market_skill_payload(package=package))
    monkeypatch.setattr(skill_market, "_get_bytes", lambda _url: package)

    record = skill_market.install_market_skill(
        "demo",
        base_url="https://market.example",
        home=tmp_path,
    )

    assert record.name == "demo"
    assert record.install_path == tmp_path / ".agents" / "skills" / "demo"
    assert record.install_path.joinpath("SKILL.md").is_file()
    records = skill_market.list_installed_skills(home=tmp_path)
    assert [item.name for item in records] == ["demo"]
    assert records[0].market_url == "https://market.example"
    assert records[0].version_id == "1.2.3"
    assert records[0].version == "1.2.3"
    assert records[0].sha256 == skill_market.hashlib.sha256(package).hexdigest()
    assert records[0].uploaded_at == "2026-05-15T00:00:00+00:00"


def test_install_market_skill_supports_project_scope(monkeypatch, tmp_path):
    package = _zip_bytes()
    project = tmp_path / "project"
    monkeypatch.setattr(skill_market, "_get_json", lambda _url: _market_skill_payload(package=package))
    monkeypatch.setattr(skill_market, "_get_bytes", lambda _url: package)

    record = skill_market.install_market_skill(
        "demo",
        home=tmp_path / "home",
        project_root=project,
        scope="project",
    )

    assert record.scope == "project"
    assert record.install_path == project / ".agents" / "skills" / "demo"
    assert record.install_path.joinpath("SKILL.md").is_file()


def test_uninstall_market_skill_removes_unchanged_install(monkeypatch, tmp_path):
    package = _zip_bytes()
    monkeypatch.setattr(skill_market, "_get_json", lambda _url: _market_skill_payload(package=package))
    monkeypatch.setattr(skill_market, "_get_bytes", lambda _url: package)
    skill_market.install_market_skill("demo", home=tmp_path)

    removed = skill_market.uninstall_market_skill("demo", home=tmp_path)

    assert removed == "demo"
    assert not (tmp_path / ".agents" / "skills" / "demo").exists()
    assert skill_market.list_installed_skills(home=tmp_path) == []


def test_uninstall_market_skill_protects_local_modifications(monkeypatch, tmp_path):
    package = _zip_bytes()
    monkeypatch.setattr(skill_market, "_get_json", lambda _url: _market_skill_payload(package=package))
    monkeypatch.setattr(skill_market, "_get_bytes", lambda _url: package)
    record = skill_market.install_market_skill("demo", home=tmp_path)
    record.install_path.joinpath("notes.txt").write_text("local change", encoding="utf-8")

    with pytest.raises(RuntimeError, match="local modifications"):
        skill_market.uninstall_market_skill("demo", home=tmp_path)

    assert record.install_path.exists()


def test_search_market_skills_marks_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    installed = skill_market.InstalledSkill(
        name="demo",
        scope="user",
        install_path=tmp_path / ".agents" / "skills" / "demo",
        market_url="https://market.example",
        version_id="v1",
        version="v1",
        sha256="abc",
        content_hash="hash",
        installed_at="now",
    )
    skill_market.write_installed_skills([installed], home=tmp_path)
    monkeypatch.setattr(
        skill_market,
        "_get_json",
        lambda _url: {"skills": [{"name": "demo", "description": "Demo skill"}]},
    )

    skills = skill_market.search_market_skills(base_url="https://market.example")

    assert len(skills) == 1
    assert skills[0].name == "demo"
    assert skills[0].installed is True


def test_update_market_skill_replaces_when_market_hash_changes(monkeypatch, tmp_path):
    packages = [_zip_bytes_with_body("demo", "Old body."), _zip_bytes_with_body("demo", "New body.")]

    def fake_get_bytes(url: str) -> bytes:
        if url.endswith("/download"):
            return packages.pop(0)
        raise AssertionError(url)

    monkeypatch.setattr(skill_market, "_get_bytes", fake_get_bytes)
    monkeypatch.setattr(
        skill_market,
        "_get_json",
        lambda _url: _market_skill_payload(package=packages[0]),
    )
    record = skill_market.install_market_skill("demo", base_url="https://market.example", home=tmp_path)
    latest_hash = skill_market.hashlib.sha256(packages[0]).hexdigest()
    monkeypatch.setattr(
        skill_market,
        "_get_json",
        lambda _url: {"name": "demo", "description": "Demo skill", "sha256": latest_hash},
    )

    status, updated = skill_market.update_market_skill("demo", home=tmp_path)

    assert status == "updated"
    assert updated.sha256 == latest_hash
    assert "New body." in record.install_path.joinpath("SKILL.md").read_text(encoding="utf-8")


def test_update_market_skill_noops_when_hash_matches(monkeypatch, tmp_path):
    package = _zip_bytes()
    monkeypatch.setattr(skill_market, "_get_json", lambda _url: _market_skill_payload(package=package))
    monkeypatch.setattr(skill_market, "_get_bytes", lambda _url: package)
    record = skill_market.install_market_skill("demo", home=tmp_path)
    monkeypatch.setattr(
        skill_market,
        "_get_json",
        lambda _url: {"name": "demo", "description": "Demo skill", "sha256": record.sha256},
    )

    status, updated = skill_market.update_market_skill("demo", home=tmp_path)

    assert status == "unchanged"
    assert updated.name == "demo"
