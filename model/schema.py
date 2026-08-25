"""Creación y migración de esquema, compartida entre la app de escritorio y la web."""
import os
from datetime import datetime

from sqlalchemy import create_engine, inspect, text

from model.entity.models import AuthSession, Base, User
from model.repository.factory import DB_URL, RepositoryFactory


DEMO_CLEANUP_MIGRATION = 'clean_demo_2026_08_24_v1'


def _clean_demo_operational_data_once(engine):
    """Limpia datos de prueba una sola vez sin eliminar accesos ni perfil comercial."""
    operational_tables = (
        'held_sale_items', 'held_sales', 'quote_items', 'quotes', 'stock_movements',
        'audit_logs', 'cash_movements', 'cash_closes', 'cash_openings', 'expenses',
        'sales', 'products', 'customers', 'catalog_settings',
    )
    existing_tables = set(inspect(engine).get_table_names())
    with engine.begin() as connection:
        connection.execute(text(
            'CREATE TABLE IF NOT EXISTS deployment_migrations ('
            'migration_key VARCHAR(100) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)'))
        already_applied = connection.execute(
            text('SELECT migration_key FROM deployment_migrations WHERE migration_key = :key'),
            {'key': DEMO_CLEANUP_MIGRATION}).first()
        if already_applied:
            return False

        for table_name in operational_tables:
            if table_name in existing_tables:
                connection.execute(text(f'DELETE FROM {table_name}'))

        if engine.dialect.name == 'sqlite' and 'sqlite_sequence' in existing_tables:
            for table_name in operational_tables:
                connection.execute(
                    text('DELETE FROM sqlite_sequence WHERE name = :table_name'),
                    {'table_name': table_name})

        connection.execute(
            text('INSERT INTO deployment_migrations (migration_key, applied_at) '
                 'VALUES (:key, :applied_at)'),
            {'key': DEMO_CLEANUP_MIGRATION, 'applied_at': datetime.utcnow().isoformat()})
    return True


def create_database(database_url=DB_URL):
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    def column_names(table):
        return {column['name'] for column in inspector.get_columns(table)} if inspector.has_table(table) else set()

    def add_columns(connection, table, definitions):
        existing = column_names(table)
        for field, definition in definitions.items():
            if field not in existing:
                connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {field} {definition}'))

    with engine.begin() as connection:
        add_columns(connection, 'products', {
            'image_path': "VARCHAR(500) DEFAULT ''", 'barcode': "VARCHAR(100) DEFAULT ''",
            'is_temporary': 'BOOLEAN DEFAULT 0', 'category': "VARCHAR(80) DEFAULT 'General'",
            'supplier': "VARCHAR(120) DEFAULT ''", 'minimum_stock': 'INTEGER DEFAULT 5',
            'is_active': 'BOOLEAN DEFAULT 1',
            'catalog_visible': 'BOOLEAN DEFAULT 0',
            'catalog_featured': 'BOOLEAN DEFAULT 0',
            'catalog_description': "VARCHAR(500) DEFAULT ''",
            'catalog_image_data': "TEXT DEFAULT ''",
            'catalog_image_mime': "VARCHAR(40) DEFAULT ''",
        })
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode) WHERE barcode <> ''"))
        add_columns(connection, 'business_profile', {
            field: "VARCHAR(500) DEFAULT ''" for field in ('email', 'tax_id', 'website', 'logo_path')
        })
        add_columns(connection, 'business_profile', {
            'legal_name': "VARCHAR(160) DEFAULT ''",
            'business_type': "VARCHAR(80) DEFAULT 'Comercio minorista'",
            'slogan': "VARCHAR(180) DEFAULT ''",
            'city': "VARCHAR(100) DEFAULT ''",
            'state': "VARCHAR(100) DEFAULT ''",
            'postal_code': "VARCHAR(12) DEFAULT ''",
            'tax_regime': "VARCHAR(160) DEFAULT ''",
            'receipt_header': "VARCHAR(300) DEFAULT ''",
            'receipt_footer': "VARCHAR(500) DEFAULT 'Gracias por su compra.'",
            'return_policy': "VARCHAR(500) DEFAULT ''",
            'brand_color': "VARCHAR(7) DEFAULT '#123B6D'",
            'logo_data': "TEXT DEFAULT ''",
            'logo_mime': "VARCHAR(40) DEFAULT ''",
        })
        add_columns(connection, 'quote_items', {'product_id': 'INTEGER'})
        add_columns(connection, 'sales', {
            'payment_method': 'VARCHAR(50)',
            'payment_details': 'VARCHAR(250)',
            'transaction_id': 'VARCHAR(36)',
            'created_at': 'DATETIME', 'product_name': "VARCHAR(80) DEFAULT ''",
            'cashier': "VARCHAR(120) DEFAULT 'Vendedor'",
            'status': "VARCHAR(30) DEFAULT 'Completada'",
            'reversal_reason': "VARCHAR(300) DEFAULT ''", 'reversed_at': 'DATETIME',
            'returned_at': 'DATETIME', 'return_reason': "VARCHAR(300) DEFAULT ''",
            'refund_method': "VARCHAR(50) DEFAULT ''",
            'customer': "VARCHAR(120) DEFAULT 'Público general'",
        })
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_sales_date_status ON sales(date, status)'))
        add_columns(connection, 'expenses', {
            'created_at': 'DATETIME', 'is_active': 'BOOLEAN DEFAULT 1',
            'payment_method': "VARCHAR(30) DEFAULT 'Efectivo'",
            'category': "VARCHAR(80) DEFAULT 'Operación'",
            'beneficiary': "VARCHAR(120) DEFAULT ''",
            'reference': "VARCHAR(120) DEFAULT ''",
            'affects_cash': 'BOOLEAN DEFAULT 1',
        })
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_expenses_date_active ON expenses(date, is_active)'))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_products_active_stock '
            'ON products(is_active, is_temporary, quantity)'))
        add_columns(connection, 'cash_openings', {
            'denomination_details': "TEXT DEFAULT '{}'",
            'source_close_id': 'INTEGER',
            'shift_responsible': "VARCHAR(120) DEFAULT 'Vendedor'",
        })
        add_columns(connection, 'cash_closes', {
            'denomination_details': "TEXT DEFAULT '{}'",
        })
    # Una limpieza nunca debe formar parte del arranque normal. Se conserva
    # exclusivamente para entornos demo creados de forma deliberada.
    if os.getenv('BLUE_POS_DEMO_RESET', '').strip().lower() in ('1', 'true', 'yes'):
        _clean_demo_operational_data_once(engine)


def create_auth_database():
    """La base de credenciales está separada de las bases operativas."""
    repository = RepositoryFactory.get_user_repository()
    engine = repository._UserRepository__session.bind
    User.__table__.create(engine, checkfirst=True)
    AuthSession.__table__.create(engine, checkfirst=True)
    with engine.begin() as connection:
        columns = {column['name'] for column in inspect(engine).get_columns('users')}
        definitions = {
            'workspace_key': "VARCHAR(180) DEFAULT 'primary'",
            'credential_version': 'INTEGER DEFAULT 0',
            'failed_login_attempts': 'INTEGER DEFAULT 0',
            'failed_recovery_attempts': 'INTEGER DEFAULT 0',
            'login_blocked_until': 'DATETIME',
            'recovery_blocked_until': 'DATETIME',
        }
        for field, definition in definitions.items():
            if field not in columns:
                connection.execute(text(f'ALTER TABLE users ADD COLUMN {field} {definition}'))
    repository.bootstrap_administrator()


def activate_user_workspace(user):
    """Activa el espacio de trabajo del usuario y garantiza que su esquema esté migrado."""
    workspace_url = RepositoryFactory.workspace_url(user.workspace_key)
    RepositoryFactory.activate_workspace(workspace_url)
    create_database(workspace_url)
