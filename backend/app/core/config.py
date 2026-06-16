from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    FAMILY_NAME: str = "MyFamily"
    TIMEZONE: str = "America/Chicago"
    SECRET_KEY: str = "change-me-in-production"
    DATA_PATH: str = "./data"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/db/openfamhub.db"

    @property
    def app_version(self) -> str:
        return "0.27"

    @property
    def data_db_path(self) -> str:
        return f"sqlite+aiosqlite:///{self.DATA_PATH}/db/openfamhub.db"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
