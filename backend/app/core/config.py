import os
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_version(build_env: str | None = None, version_path: Path | None = None) -> str:
    build = (build_env if build_env is not None else os.environ.get("OPENFAMHUB_BUILD", "")).strip()
    if build and build != "dev":
        return build
    path = version_path if version_path is not None else _PROJECT_ROOT / "VERSION"
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0-dev"
    return f"0.{raw}" if raw.isdigit() else "0.0-dev"


APP_VERSION = _resolve_version()


class Settings(BaseSettings):
    app_version: str = APP_VERSION
    # Baked into published images (OPENFAMHUB_BUILD / OPENFAMHUB_COMMIT env).
    openfamhub_build: str = ""
    openfamhub_commit: str = ""
    family_name: str = "OpenFamHub"
    timezone: str = "UTC"
    secret_key: str
    database_url: str = "sqlite+aiosqlite:////data/db/homehub.db"
    allowed_origins: str = "https://openfamhub.local"
    backup_retention_days: int = 30
    backup_time: str = "03:00"
    wall_idle_timeout_seconds: int = 300

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        if self.database_url.startswith("sqlite+aiosqlite:///./"):
            rel = self.database_url[len("sqlite+aiosqlite:///.") :]
            abs_path = str(_PROJECT_ROOT / rel.lstrip("/"))
            self.database_url = f"sqlite+aiosqlite:///{abs_path}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
