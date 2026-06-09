import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f'sqlite+aiosqlite:///{os.path.join(BASE_DIR, "..", "..", "..", "data", "db", "homehub.db")}'
)
