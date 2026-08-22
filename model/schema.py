"""Creación y migración de esquema, compartida entre la app de escritorio y la web."""
from sqlalchemy import create_engine, text

from model.entity.models import AuthSession, Base, User
from model.repository.factory import DB_URL, RepositoryFactory


def create_database(database_url=DB_URL):
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text('PRAGMA table_info(products)'))}
        if 'image_path' not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN image_path VARCHAR(500) DEFAULT ''"))
        if 'barcode' not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN barcode VARCHAR(100) DEFAULT ''"))
        if 'is_temporary' not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN is_temporary BOOLEAN DEFAULT 0"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode) WHERE barcode <> ''"))
        profile_columns = {row[1] for row in connection.execute(text('PRAGMA table_info(business_profile)'))}
        for field in ('email', 'tax_id', 'website', 'logo_path'):
            if field not in profile_columns:
                connection.execute(text(f"ALTER TABLE business_profile ADD COLUMN {field} VARCHAR(500) DEFAULT ''"))
        quote_item_columns = {row[1] for row in connection.execute(text('PRAGMA table_info(quote_items)'))}
        if 'product_id' not in quote_item_columns:
            connection.execute(text("ALTER TABLE quote_items ADD COLUMN product_id INTEGER"))
        sales_columns = {row[1] for row in connection.execute(text('PRAGMA table_info(sales)'))}
        for field, column_type in {
            'payment_method': 'VARCHAR(50)',
            'payment_details': 'VARCHAR(250)',
            'transaction_id': 'VARCHAR(36)',
        }.items():
            if field not in sales_columns:
                connection.execute(text(f"ALTER TABLE sales ADD COLUMN {field} {column_type} DEFAULT ''"))


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
