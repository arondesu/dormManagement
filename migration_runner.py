import os
import sqlite3
from datetime import datetime
from pathlib import Path


MIGRATIONS_TABLE = "schema_migrations"


def _get_db_path() -> str:
    return os.getenv("DB_PATH", "database/manager.db")


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            applied_at DATETIME NOT NULL
        )
        """
    )
    connection.commit()


def _get_migration_files(migrations_dir: str = "migrations") -> list[Path]:
    base_path = Path(migrations_dir)
    if not base_path.exists():
        return []
    migration_files = [file_path for file_path in base_path.glob("*.sql") if file_path.is_file()]
    return sorted(migration_files, key=lambda file_path: file_path.name)


def _get_applied_versions(connection: sqlite3.Connection) -> set[str]:
    _ensure_migrations_table(connection)
    cursor = connection.cursor()
    cursor.execute(f"SELECT version FROM {MIGRATIONS_TABLE}")
    return {row["version"] for row in cursor.fetchall()}


def migration_version(file_path: Path) -> str:
    return file_path.stem.split("_", 1)[0]


def status(migrations_dir: str = "migrations") -> dict:
    connection = _get_connection()
    try:
        migration_files = _get_migration_files(migrations_dir)
        applied_versions = _get_applied_versions(connection)

        applied = []
        pending = []
        for file_path in migration_files:
            version = migration_version(file_path)
            item = {
                "version": version,
                "filename": file_path.name,
            }
            if version in applied_versions:
                applied.append(item)
            else:
                pending.append(item)

        return {
            "applied": applied,
            "pending": pending,
            "total": len(migration_files),
        }
    finally:
        connection.close()


def apply_pending(migrations_dir: str = "migrations", target: str | None = None) -> list[str]:
    connection = _get_connection()
    applied_now: list[str] = []

    try:
        _ensure_migrations_table(connection)
        migration_files = _get_migration_files(migrations_dir)
        applied_versions = _get_applied_versions(connection)

        for file_path in migration_files:
            version = migration_version(file_path)
            if version in applied_versions:
                continue

            if target and version > target:
                continue

            sql_script = file_path.read_text(encoding="utf-8")
            connection.executescript(sql_script)
            connection.execute(
                f"INSERT INTO {MIGRATIONS_TABLE} (version, filename, applied_at) VALUES (?, ?, ?)",
                (version, file_path.name, datetime.utcnow().isoformat(timespec="seconds")),
            )
            connection.commit()
            applied_now.append(file_path.name)

        return applied_now
    finally:
        connection.close()
