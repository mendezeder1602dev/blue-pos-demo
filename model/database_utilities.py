import sqlite3
from contextlib import closing
from pathlib import Path
import shutil


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
