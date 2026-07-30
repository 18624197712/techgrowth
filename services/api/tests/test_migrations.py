import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_existing_v2_database_upgrades_to_head(tmp_path: Path) -> None:
    service_root = Path(__file__).parents[1]
    database_path = tmp_path / "migration.db"
    with sqlite3.connect(database_path) as database:
        database.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('0002');
            CREATE TABLE learning_tasks (id VARCHAR(36) PRIMARY KEY);
            CREATE TABLE repositories (
                id VARCHAR(36) PRIMARY KEY,
                device_id VARCHAR(36), provider VARCHAR(24) NOT NULL,
                external_key VARCHAR(300) NOT NULL, name VARCHAR(200) NOT NULL,
                default_branch VARCHAR(120) NOT NULL, languages JSON NOT NULL,
                last_commit VARCHAR(80) NOT NULL, last_synced_at DATETIME,
                created_at DATETIME NOT NULL
            );
            """
        )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(service_root / "src")
    environment["TG_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=service_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=service_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "0003" in current.stdout
