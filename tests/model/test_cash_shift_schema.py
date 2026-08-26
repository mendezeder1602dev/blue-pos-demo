import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from model.entity.models import Base
from model.schema import create_database


class CashShiftSchemaMigrationTest(unittest.TestCase):
    """Protege la reparación de una migración parcial de caja por turnos."""

    def test_removes_close_date_unique_even_if_opening_was_already_migrated(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / 'partial-shift.db'
            url = f"sqlite:///{database_path.as_posix()}"
            engine = create_engine(url, future=True)
            Base.metadata.create_all(engine)
            with engine.begin() as connection:
                connection.execute(text('DROP TABLE cash_closes'))
                connection.execute(text(
                    'CREATE TABLE cash_closes ('
                    'id INTEGER PRIMARY KEY, date DATE NOT NULL)'))
                connection.execute(text(
                    'CREATE UNIQUE INDEX ix_cash_closes_date ON cash_closes(date)'))
            engine.dispose()

            create_database(url)

            migrated = inspect(create_engine(url, future=True))
            unique_dates = [
                constraint for constraint in migrated.get_unique_constraints('cash_closes')
                if constraint.get('column_names') == ['date']
            ]
            self.assertEqual(unique_dates, [])
            self.assertIn(
                'opening_id',
                {column['name'] for column in migrated.get_columns('cash_closes')},
            )


if __name__ == '__main__':
    unittest.main()
