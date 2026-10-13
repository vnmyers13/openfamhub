"""The app's view of the release number (spec: per-commit release number)."""
from pathlib import Path

import pytest

from app.core.config import _resolve_version, release_name


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


@pytest.mark.parametrize(
    "n,name",
    [(0, "0.0"), (5, "0.5"), (31, "0.31"), (99, "0.99"), (100, "1"), (101, "1.01"),
     (109, "1.09"), (110, "1.10"), (199, "1.99"), (200, "2"), (1234, "12.34")],
)
def test_release_name(n, name):
    assert release_name(n) == name


def test_version_file_past_99(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("101\n", encoding="utf-8")
    assert _resolve_version(version_path=vf) == "1.01"
