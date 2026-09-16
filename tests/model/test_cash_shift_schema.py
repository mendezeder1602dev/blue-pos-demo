import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from model.entity.models import Base
from model.schema import CURRENT_SCHEMA_MIGRATION, create_database


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

    def test_adds_expected_date_to_existing_purchase_orders(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / 'legacy-purchase-orders.db'
            url = f"sqlite:///{database_path.as_posix()}"
            engine = create_engine(url, future=True)
            with engine.begin() as connection:
                connection.execute(text(
                    'CREATE TABLE purchase_orders ('
                    'id INTEGER PRIMARY KEY, supplier VARCHAR(120) NOT NULL, '
                    "status VARCHAR(20) NOT NULL DEFAULT 'Pendiente', "
                    "total TEXT NOT NULL DEFAULT '0.00', notes VARCHAR(500), "
                    "created_by VARCHAR(120) NOT NULL DEFAULT 'Administrador', "
                    'created_at DATETIME, received_at DATETIME)'))
            engine.dispose()

            create_database(url)

            migrated = inspect(create_engine(url, future=True))
            self.assertIn(
                'expected_date',
                {column['name'] for column in migrated.get_columns('purchase_orders')},
            )

    def test_records_the_schema_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / 'versioned.db'
            url = f"sqlite:///{database_path.as_posix()}"
            create_database(url)

            engine = create_engine(url, future=True)
            with engine.connect() as connection:
                applied = connection.execute(text(
                    'SELECT COUNT(*) FROM schema_migrations '
                    'WHERE migration_key = :key'),
                    {'key': CURRENT_SCHEMA_MIGRATION}).scalar_one()
            engine.dispose()
            self.assertEqual(applied, 1)

    def test_adds_customer_country_and_postal_code_to_existing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / 'legacy-customers.db'
            url = f"sqlite:///{database_path.as_posix()}"
            engine = create_engine(url, future=True)
            with engine.begin() as connection:
                connection.execute(text(
                    'CREATE TABLE customers ('
                    'id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE, '
                    "phone VARCHAR(40) DEFAULT '', address VARCHAR(300) DEFAULT '', "
                    "email VARCHAR(120) DEFAULT '', tax_id VARCHAR(40) DEFAULT '', "
                    "notes VARCHAR(400) DEFAULT '', is_active BOOLEAN DEFAULT 1, "
                    "loyalty_points INTEGER DEFAULT 0, lifetime_spend TEXT DEFAULT '0.00', "
                    'created_at DATETIME, updated_at DATETIME)'))
                connection.execute(text(
                    "INSERT INTO customers (name, phone, created_at) "
                    "VALUES ('Cliente heredado', '9931234567', CURRENT_TIMESTAMP)"))
            engine.dispose()

            create_database(url)

            migrated_engine = create_engine(url, future=True)
            columns = {
                column['name'] for column in inspect(migrated_engine).get_columns('customers')
            }
            with migrated_engine.connect() as connection:
                country = connection.execute(text(
                    "SELECT phone_country FROM customers WHERE name = 'Cliente heredado'"
                )).scalar_one()
            migrated_engine.dispose()
            self.assertIn('phone_country', columns)
            self.assertIn('postal_code', columns)
            self.assertEqual(country, 'MX')


if __name__ == '__main__':
    unittest.main()
