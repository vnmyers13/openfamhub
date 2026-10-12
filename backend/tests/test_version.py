"""The app's view of the release number (spec: per-commit release number)."""
from pathlib import Path

from app.core.config import _resolve_version


def test_reads_version_file(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(version_path=vf) == "0.31"


def test_build_env_wins(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(build_env="0.31.7", version_path=vf) == "0.31.7"


def test_dev_env_falls_through_to_file(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(build_env="dev", version_path=vf) == "0.31"


def test_missing_file_falls_back(tmp_path: Path):
    assert _resolve_version(version_path=tmp_path / "nope") == "0.0-dev"


def test_non_numeric_file_falls_back(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("thirty\n", encoding="utf-8")
    assert _resolve_version(version_path=vf) == "0.0-dev"
