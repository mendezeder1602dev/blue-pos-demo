import sqlite3
from contextlib import closing
from pathlib import Path
import shutil
import os
import tempfile
from sqlalchemy.engine import make_url


def backup_database(database_path: str, backup_path: str):
    with closing(sqlite3.connect(database_path)) as database_connection:
        with closing(sqlite3.connect(backup_path)) as backup_connection:
            database_connection.backup(backup_connection)


def restore_database(database_path: str, backup_path: str):
    working_database_path = Path(database_path)
    backup_database_path = Path(backup_path)
    if not backup_database_path.is_file():
        raise FileNotFoundError(f'Backup database not found: {backup_database_path}')
    working_database_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_database_path.absolute(), working_database_path.absolute())


def backup_database_bytes(database_url: str) -> bytes:
    """Crea una copia consistente y descargable de una base SQLite activa."""
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite' or not url.database:
        raise ValueError('La descarga directa sólo está disponible para SQLite.')
    handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    backup_path = handle.name
    handle.close()
    try:
        backup_database(url.database, backup_path)
        return Path(backup_path).read_bytes()
    finally:
        if os.path.exists(backup_path):
            os.unlink(backup_path)
