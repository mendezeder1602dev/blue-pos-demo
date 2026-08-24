"""Creación y migración de esquema, compartida entre la app de escritorio y la web."""
from sqlalchemy import create_engine, inspect, text

from model.entity.models import AuthSession, Base, User
from model.repository.factory import DB_URL, RepositoryFactory


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
            'customer': "VARCHAR(120) DEFAULT 'Público general'",
        })
        add_columns(connection, 'expenses', {
            'created_at': 'DATETIME', 'is_active': 'BOOLEAN DEFAULT 1',
        })
        add_columns(connection, 'cash_openings', {
            'denomination_details': "TEXT DEFAULT '{}'",
            'source_close_id': 'INTEGER',
        })
        add_columns(connection, 'cash_closes', {
            'denomination_details': "TEXT DEFAULT '{}'",
        })


def create_auth_database():
    """La base de credenciales está separada de las bases operativas."""
    repository = RepositoryFactory.get_user_repository()
    engine = repository._UserRepository__session.bind
    User.__table__.create(engine, checkfirst=True)
    AuthSession.__table__.create(engine, checkfirst=True)
    with engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text('PRAGMA table_info(users)'))}
        if 'workspace_key' not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN workspace_key VARCHAR(180) DEFAULT 'primary'"))
        if 'credential_version' not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN credential_version INTEGER DEFAULT 0"))
    repository.bootstrap_administrator()


def activate_user_workspace(user):
    """Activa el espacio de trabajo del usuario y garantiza que su esquema esté migrado."""
    workspace_url = RepositoryFactory.workspace_url(user.workspace_key)
    RepositoryFactory.activate_workspace(workspace_url)
    create_database(workspace_url)
