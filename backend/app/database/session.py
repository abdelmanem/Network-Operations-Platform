import os
from collections.abc import Generator
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config.settings import Settings, get_settings

settings: Settings = get_settings()

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


_database_initialized = False
_database_init_lock = Lock()


def initialize_database() -> None:
    """Apply Alembic migrations to the configured database."""

    global _database_initialized
    if _database_initialized:
        return

    with _database_init_lock:
        if _database_initialized:
            return

        project_root = Path(__file__).resolve().parents[3]
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("script_location", str(project_root / "alembic"))
        config.set_main_option("sqlalchemy.url", settings.database_url)
        config.set_main_option("prepend_sys_path", str(project_root))
        config.set_main_option("path_separator", os.pathsep)
        command.upgrade(config, "head")
        _database_initialized = True


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
