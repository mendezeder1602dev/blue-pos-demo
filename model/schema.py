"""Creación y migración de esquema, compartida entre la app de escritorio y la web."""
import os
from datetime import datetime

from sqlalchemy import create_engine, inspect, text

from model.entity.models import (AuthSession, Base, CashClose, CashMovement,
                                 CashOpening, User)
from model.repository.factory import DB_URL, RepositoryFactory
from model.timezone import mexico_now


DEMO_CLEANUP_MIGRATION = 'clean_demo_2026_08_25_release_v2'
CURRENT_SCHEMA_MIGRATION = '2026_09_10_multicaja_local_v1'


def _record_schema_migration(connection, migration_key):
    """Deja evidencia de la versión de esquema aplicada a cada negocio.

    Las migraciones históricas son idempotentes para poder reparar instalaciones
    antiguas. Al terminar correctamente se registra su versión; las siguientes
    migraciones deben agregarse como nuevas claves, nunca reutilizar ésta.
    """
    connection.execute(text(
        'CREATE TABLE IF NOT EXISTS schema_migrations ('
        'migration_key VARCHAR(120) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)'))
    already_applied = connection.execute(text(
        'SELECT 1 FROM schema_migrations WHERE migration_key = :key'),
        {'key': migration_key}).first()
    if not already_applied:
        connection.execute(text(
            'INSERT INTO schema_migrations (migration_key, applied_at) '
            'VALUES (:key, :applied_at)'),
            {'key': migration_key, 'applied_at': mexico_now().isoformat()})


def _allow_multiple_cash_shifts(engine):
    """Migra el esquema diario anterior a uno que admite varios turnos por fecha.

    SQLite no permite retirar una restricción UNIQUE con ``ALTER TABLE``. En ese
    motor reconstruimos solamente las tres tablas de caja y preservamos sus filas.
    En PostgreSQL basta con eliminar las restricciones únicas antiguas por fecha.
    """
    inspector = inspect(engine)
    target_tables = ('cash_openings', 'cash_movements', 'cash_closes')
    if 'cash_openings' not in inspector.get_table_names():
        return
    # Una ejecución interrumpida puede dejar sólo una de las dos tablas con la
    # restricción diaria. Revisarlas por separado permite reparar ese estado.
    tables_with_unique_date = []
    for table_name in ('cash_openings', 'cash_closes'):
        if table_name not in inspector.get_table_names():
            continue
        unique_constraint = any(
            constraint.get('column_names') == ['date']
            for constraint in inspector.get_unique_constraints(table_name)
        )
        unique_index = any(
            index.get('column_names') == ['date'] and bool(index.get('unique'))
            for index in inspector.get_indexes(table_name)
        )
        if unique_constraint or unique_index:
            tables_with_unique_date.append(table_name)
    if not tables_with_unique_date:
        return

    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            for table_name in ('cash_openings', 'cash_closes'):
                for constraint in inspect(connection).get_unique_constraints(table_name):
                    if constraint.get('column_names') == ['date'] and constraint.get('name'):
                        safe_name = constraint['name'].replace('"', '""')
                        connection.execute(text(
                            f'ALTER TABLE {table_name} DROP CONSTRAINT "{safe_name}"'))
                for index in inspect(connection).get_indexes(table_name):
                    if (index.get('column_names') == ['date'] and index.get('unique')
                            and index.get('name')):
                        safe_name = index['name'].replace('"', '""')
                        connection.execute(text(f'DROP INDEX IF EXISTS "{safe_name}"'))
        return
    if engine.dialect.name != 'sqlite':
        return

    table_models = (CashOpening.__table__, CashMovement.__table__, CashClose.__table__)
    connection = engine.connect()
    try:
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        transaction = connection.begin()
        for table_name in target_tables:
            for index in inspect(connection).get_indexes(table_name):
                if index.get('name'):
                    connection.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))
        # Renombrar primero libera los nombres para que SQLAlchemy cree el esquema nuevo.
        for table_name in ('cash_movements', 'cash_closes', 'cash_openings'):
            connection.execute(text(
                f'ALTER TABLE {table_name} RENAME TO {table_name}_legacy_shift'))
        for table in table_models:
            table.create(connection)
        for table in table_models:
            legacy = f'{table.name}_legacy_shift'
            old_columns = {column['name'] for column in inspect(connection).get_columns(legacy)}
            common = [column.name for column in table.columns if column.name in old_columns]
            columns_sql = ', '.join(f'"{column}"' for column in common)
            connection.execute(text(
                f'INSERT INTO {table.name} ({columns_sql}) '
                f'SELECT {columns_sql} FROM {legacy}'))
        # Los datos históricos eran un turno por día; se vinculan de forma inequívoca.
        connection.execute(text(
            'UPDATE cash_closes SET opening_id = ('
            'SELECT id FROM cash_openings WHERE cash_openings.date = cash_closes.date '
            'ORDER BY id DESC LIMIT 1) WHERE opening_id IS NULL'))
        connection.execute(text(
            'UPDATE cash_movements SET opening_id = ('
            'SELECT id FROM cash_openings WHERE cash_openings.date = cash_movements.date '
            'ORDER BY id DESC LIMIT 1) WHERE opening_id IS NULL'))
        for table_name in ('cash_movements', 'cash_closes', 'cash_openings'):
            connection.execute(text(f'DROP TABLE {table_name}_legacy_shift'))
        transaction.commit()
    finally:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        connection.commit()
        connection.close()


def _clean_demo_operational_data_once(engine):
    """Limpia datos de prueba una sola vez sin eliminar accesos ni perfil comercial."""
    operational_tables = (
        'purchase_order_items', 'purchase_orders', 'operational_incidents',
        'held_sale_items', 'held_sales', 'quote_items', 'quotes',
        'store_credit_movements', 'store_credit_vouchers',
        'return_loss_requests', 'stock_movements',
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
            {'key': DEMO_CLEANUP_MIGRATION, 'applied_at': mexico_now().isoformat()})
    return True


def create_database(database_url=DB_URL):
    engine = create_engine(database_url, future=True)
    _allow_multiple_cash_shifts(engine)
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
            'wholesale_min_quantity': 'INTEGER DEFAULT 0',
            'wholesale_price': "TEXT DEFAULT '0.00'",
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
            'app_background_color': "VARCHAR(7) DEFAULT '#F1F3F6'",
            'app_surface_color': "VARCHAR(7) DEFAULT '#FFFFFF'",
            'app_text_color': "VARCHAR(7) DEFAULT '#111820'",
            'document_primary_color': "VARCHAR(7) DEFAULT '#123B6D'",
            'document_text_color': "VARCHAR(7) DEFAULT '#111820'",
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
            'return_disposition': "VARCHAR(30) DEFAULT ''",
            'register_id': 'INTEGER',
            'register_name': "VARCHAR(80) DEFAULT 'Caja principal'",
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
            'register_id': 'INTEGER',
            'register_name': "VARCHAR(80) DEFAULT 'Caja principal'",
        })
        add_columns(connection, 'customers', {
            'loyalty_points': 'INTEGER DEFAULT 0',
            'lifetime_spend': "TEXT DEFAULT '0.00'",
        })
        add_columns(connection, 'cash_movements', {
            'opening_id': 'INTEGER',
            'register_id': 'INTEGER',
            'register_name': "VARCHAR(80) DEFAULT 'Caja principal'",
        })
        add_columns(connection, 'cash_closes', {
            'denomination_details': "TEXT DEFAULT '{}'",
            'opening_id': 'INTEGER',
            'register_id': 'INTEGER',
            'register_name': "VARCHAR(80) DEFAULT 'Caja principal'",
        })
        connection.execute(text(
            "INSERT INTO cash_registers (name, code, location, is_active, created_at) "
            "SELECT 'Caja principal', 'MAIN', 'Mostrador', 1, :created_at "
            "WHERE NOT EXISTS (SELECT 1 FROM cash_registers WHERE code = 'MAIN')"),
            {'created_at': mexico_now()})
        connection.execute(text(
            "UPDATE cash_openings SET register_id = (SELECT id FROM cash_registers WHERE code = 'MAIN'), "
            "register_name = 'Caja principal' WHERE register_id IS NULL"))
        connection.execute(text(
            "UPDATE cash_movements SET register_id = (SELECT id FROM cash_registers WHERE code = 'MAIN'), "
            "register_name = 'Caja principal' WHERE register_id IS NULL"))
        connection.execute(text(
            "UPDATE cash_closes SET register_id = (SELECT id FROM cash_registers WHERE code = 'MAIN'), "
            "register_name = 'Caja principal' WHERE register_id IS NULL"))
        connection.execute(text(
            "UPDATE sales SET register_id = (SELECT id FROM cash_registers WHERE code = 'MAIN'), "
            "register_name = 'Caja principal' WHERE register_id IS NULL"))
        # ``create_all`` crea las tablas nuevas pero no modifica las existentes.
        # Las instalaciones anteriores ya tenían órdenes de compra, sin fecha
        # prevista; conservarlas requiere agregar la columna por migración.
        add_columns(connection, 'purchase_orders', {
            'expected_date': 'DATE',
        })
        _record_schema_migration(connection, CURRENT_SCHEMA_MIGRATION)
    # Esta versión pública es una demo de Streamlit Community Cloud. La clave de
    # migración garantiza que la limpieza se ejecute una sola vez por despliegue,
    # sin tocar credenciales ni el perfil comercial y sin repetirse en cada rerun.
    demo_reset_requested = (
        os.getenv('BLUE_POS_DEMO_RESET', '').strip().lower() in ('1', 'true', 'yes')
    )
    community_cloud = (
        os.getenv('STREAMLIT_SHARING_MODE', '').strip().lower() in ('1', 'true', 'yes')
    )
    if demo_reset_requested or community_cloud:
        _clean_demo_operational_data_once(engine)
    # Este motor sólo se usa para migrar. Liberarlo evita conservar bloqueos de
    # SQLite cuando el proceso vuelve a comprobar el esquema.
    engine.dispose()


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
            'is_active': 'BOOLEAN DEFAULT 1',
            'commission_bps': 'INTEGER DEFAULT 0',
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
