import sqlite3
from contextlib import closing
from pathlib import Path
import shutil
import os
import tempfile
from datetime import datetime, timedelta
from sqlalchemy.engine import make_url
from model.authorization import require_role


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
    require_role('superuser')
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


def scheduled_backup(database_url: str, interval_days: int = 7, keep: int = 12):
    """Crea una copia local periódica para SQLite y conserva un historial limitado."""
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite' or not url.database:
        return None
    source = Path(url.database)
    if not source.is_file():
        return None
    folder = source.parent / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob('puntos-eccos-*.db'), key=lambda item: item.stat().st_mtime,
                      reverse=True)
    if existing:
        last = datetime.fromtimestamp(existing[0].stat().st_mtime)
        if datetime.now() - last < timedelta(days=max(1, interval_days)):
            return existing[0]
    destination = folder / f'puntos-eccos-{datetime.now():%Y%m%d-%H%M%S}.db'
    backup_database(str(source), str(destination))
    for old in existing[max(0, keep - 1):]:
        old.unlink(missing_ok=True)
    return destination


def restore_database_bytes(database_url: str, content: bytes):
    """Valida y restaura un SQLite subido; se publica junto con la interfaz web."""
    require_role('superuser')
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite' or not url.database:
        raise ValueError('La restauración directa sólo está disponible para SQLite.')
    if not content or len(content) > 512 * 1024 * 1024 or not content.startswith(b'SQLite format 3\x00'):
        raise ValueError('El archivo no es una base SQLite válida o excede 512 MB.')
    handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temporary = Path(handle.name)
    try:
        handle.write(content); handle.close()
        with closing(sqlite3.connect(str(temporary))) as uploaded:
            if uploaded.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('La copia está dañada y no puede restaurarse.')
            with closing(sqlite3.connect(url.database)) as current:
                uploaded.backup(current)
        return Path(url.database)
    finally:
        try: handle.close()
        except Exception: pass
        temporary.unlink(missing_ok=True)
