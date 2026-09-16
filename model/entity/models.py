"""Entidades persistentes de Puntos ECCOS.

Los cambios de columnas deben acompañarse de una migración compatible en
``model/schema.py`` para no romper bases ya existentes.
"""

from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey
from sqlalchemy import Integer, Boolean
from sqlalchemy import String, Text
from sqlalchemy import Date, DateTime
from model.util.money_colum import MoneyColumn
from model.util.monetary_types import CUPMoney
from datetime import date, datetime
from model.timezone import mexico_now, mexico_today

Base = declarative_base()

PRODUCT_DESCRIPTION_MAX_LENGTH = 300
PRODUCT_NAME_MAX_LENGTH = 80

class Product(Base):
    """Producto vendible con precio, costo, existencia y presentación de catálogo."""

    def __repr__(self):
        return '[id: {}, name: "{}", description: "{}", price: {}, cost: {},' \
               'profit: {}, quantity: {}]'\
            .format(self.id, self.name, self.description, self.price, self.cost, self.profit, self.quantity)

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return (self.id == other.id and self.name == other.name and self.description == other.description
                and self.price == other.price and self.cost == other.cost and self.profit == other.profit
                and self.quantity == other.quantity)

    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=PRODUCT_NAME_MAX_LENGTH), nullable=False, unique=True)
    description = Column(String(length=PRODUCT_DESCRIPTION_MAX_LENGTH), nullable=True, default='')
    price = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    cost = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    quantity = Column(Integer, nullable=False, default=0)
    barcode = Column(String(length=100), nullable=True, default='')
    is_temporary = Column(Boolean, nullable=False, default=False)
    image_path = Column(String(length=500), nullable=True, default='')
    category = Column(String(length=80), nullable=True, default='General')
    supplier = Column(String(length=120), nullable=True, default='')
    unit_of_measure = Column(String(length=40), nullable=False, default='Unidad')
    minimum_stock = Column(Integer, nullable=False, default=5)
    maximum_stock = Column(Integer, nullable=False, default=0)
    wholesale_min_quantity = Column(Integer, nullable=False, default=0)
    wholesale_price = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    catalog_visible = Column(Boolean, nullable=False, default=False, index=True)
    catalog_featured = Column(Boolean, nullable=False, default=False)
    catalog_description = Column(String(length=500), nullable=True, default='')
    catalog_image_data = Column(Text, nullable=True, default='')
    catalog_image_mime = Column(String(length=40), nullable=True, default='')

    @property
    def profit(self):
        if self.price is None or self.cost is None:
            return None
        return self.price - self.cost


class Sale(Base):
    """Línea de un ticket; varias líneas comparten el mismo ``transaction_id``."""

    def __repr__(self):
        return 'Sale(id: {}, product_id: "{}", date: "{}", price: {}, cost: {}, profit: {})'\
            .format(self.id, self.product_id, self.date, self.price, self.cost, self.profit)

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return (self.id == other.id and self.product_id == other.product_id
                and self.date == other.date and self.price == other.price
                and self.cost == other.cost and self.profit == other.profit
                and self.payment_method == getattr(other, 'payment_method', '')
                and self.payment_details == getattr(other, 'payment_details', ''))

    __tablename__ = 'sales'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False, default=mexico_today, index=True)
    price = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    cost = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    payment_method = Column(String(length=50), nullable=False, default='cash')
    payment_details = Column(String(length=250), nullable=True, default='')
    transaction_id = Column(String(length=36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)
    product_name = Column(String(length=80), nullable=True, default='')
    cashier = Column(String(length=120), nullable=False, default='Vendedor')
    status = Column(String(length=30), nullable=False, default='Completada', index=True)
    reversal_reason = Column(String(length=300), nullable=True, default='')
    reversed_at = Column(DateTime, nullable=True)
    returned_at = Column(DateTime, nullable=True)
    return_reason = Column(String(length=300), nullable=True, default='')
    refund_method = Column(String(length=50), nullable=True, default='')
    # Destino físico de la unidad devuelta: vuelve a venta o queda dada de baja.
    return_disposition = Column(String(length=30), nullable=True, default='')
    register_id = Column(Integer, ForeignKey('cash_registers.id'), nullable=True, index=True)
    register_name = Column(String(length=80), nullable=True, default='Caja principal')
    customer = Column(String(length=120), nullable=True, default='Público general')
    # Las eliminaciones físicas sólo se reservan para mantenimiento/pruebas. La
    # aplicación usa archivado lógico y nunca invoca este borrado sobre ventas reales.
    product = relationship('Product', backref=backref('sales', cascade='all,delete'))
    register = relationship('CashRegister')

    @property
    def profit(self):
        if self.price is None or self.cost is None:
            return None
        return self.price - self.cost


class Quote(Base):
    """Cotización editable que agrupa uno o más conceptos antes de vender."""
    __tablename__ = 'quotes'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=mexico_today, index=True)
    customer = Column(String(length=120), nullable=False, default='Público general')
    notes = Column(String(length=500), nullable=True, default='')
    status = Column(String(length=30), nullable=False, default='Pendiente')
    items = relationship('QuoteItem', backref='quote', cascade='all,delete-orphan')

    @property
    def total(self):
        return sum((item.unit_price.amount * item.quantity for item in self.items), 0)


class QuoteItem(Base):
    __tablename__ = 'quote_items'
    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey('quotes.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='SET NULL'), nullable=True)
    description = Column(String(length=120), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))


EXPENSE_NAME_MAX_LENGTH = 100
EXPENSE_DESCRIPTION_MAX_LENGTH = 600

class Expense(Base):
    """Salida operativa; ``affects_cash`` indica si reduce el efectivo esperado."""

    def __repr__(self):
        return 'Expense(id: {}, name: {}, description: {}, spent_money: {}, date: {})'\
            .format(self.id, self.name, self.description, self.spent_money, self.date)

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return (self.id == other.id and self.name == other.name and self.description == other.description
                and self.spent_money == other.spent_money and self.date == other.date)

    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=EXPENSE_NAME_MAX_LENGTH), nullable=False)
    description = Column(String(length=EXPENSE_DESCRIPTION_MAX_LENGTH), nullable=True, default='')
    spent_money = Column(MoneyColumn(), nullable=False, default=CUPMoney('-1.00'))
    date = Column(Date, nullable=False, default=mexico_today)
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    payment_method = Column(String(length=30), nullable=False, default='Efectivo')
    category = Column(String(length=80), nullable=False, default='Operación')
    beneficiary = Column(String(length=120), nullable=True, default='')
    reference = Column(String(length=120), nullable=True, default='')
    affects_cash = Column(Boolean, nullable=False, default=True)


class HeldSale(Base):
    """Carrito suspendido que puede recuperarse sin afectar existencias."""
    __tablename__ = 'held_sales'
    id = Column(Integer, primary_key=True)
    label = Column(String(length=120), nullable=False)
    notes = Column(String(length=300), nullable=True, default='')
    created_by = Column(String(length=120), nullable=False, default='Vendedor')
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    items = relationship('HeldSaleItem', backref='held_sale', cascade='all,delete-orphan')


class HeldSaleItem(Base):
    __tablename__ = 'held_sale_items'
    id = Column(Integer, primary_key=True)
    held_sale_id = Column(Integer, ForeignKey('held_sales.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))


class StockMovement(Base):
    """Kardex: toda entrada, salida o ajuste de inventario queda registrado."""
    __tablename__ = 'stock_movements'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    movement_type = Column(String(length=30), nullable=False)
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    resulting_stock = Column(Integer, nullable=False)
    reason = Column(String(length=300), nullable=False)
    reference = Column(String(length=80), nullable=True, default='')
    performed_by = Column(String(length=120), nullable=False, default='Administrador')
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)


class ReturnLossRequest(Base):
    """Producto devuelto no vendible, retenido hasta que administración lo dictamine."""
    __tablename__ = 'return_loss_requests'
    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(length=36), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    product_name = Column(String(length=80), nullable=False)
    quantity = Column(Integer, nullable=False)
    sale_ids = Column(Text, nullable=False, default='[]')
    concept = Column(String(length=160), nullable=False)
    reason = Column(String(length=300), nullable=False)
    status = Column(String(length=30), nullable=False, default='Pendiente', index=True)
    requested_by = Column(String(length=120), nullable=False, default='Administrador')
    requested_at = Column(DateTime, nullable=False, default=mexico_now, index=True)
    resolved_by = Column(String(length=120), nullable=True, default='')
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(String(length=300), nullable=True, default='')


class StoreCreditVoucher(Base):
    """Saldo a favor emitido por una devolución; el código funciona como portador."""
    __tablename__ = 'store_credit_vouchers'
    id = Column(Integer, primary_key=True)
    code = Column(String(length=32), nullable=False, unique=True, index=True)
    original_transaction_id = Column(String(length=36), nullable=False, index=True)
    initial_amount = Column(MoneyColumn(), nullable=False)
    balance = Column(MoneyColumn(), nullable=False)
    status = Column(String(length=20), nullable=False, default='Activo', index=True)
    customer = Column(String(length=120), nullable=True, default='Público general')
    reason = Column(String(length=300), nullable=False)
    issued_by = Column(String(length=120), nullable=False)
    issued_at = Column(DateTime, nullable=False, default=mexico_now, index=True)


class StoreCreditMovement(Base):
    """Libro inmutable de emisiones, usos y restituciones de un vale."""
    __tablename__ = 'store_credit_movements'
    id = Column(Integer, primary_key=True)
    voucher_id = Column(Integer, ForeignKey('store_credit_vouchers.id', ondelete='RESTRICT'),
                        nullable=False, index=True)
    movement_type = Column(String(length=20), nullable=False)
    amount = Column(MoneyColumn(), nullable=False)
    sale_transaction_id = Column(String(length=36), nullable=True, index=True)
    performed_by = Column(String(length=120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)
    voucher = relationship('StoreCreditVoucher', backref='movements')


class CreditAccount(Base):
    __tablename__ = 'credit_accounts'
    id = Column(Integer, primary_key=True)
    account_type = Column(String(length=20), nullable=False, index=True)
    party_name = Column(String(length=120), nullable=False, index=True)
    concept = Column(String(length=250), nullable=False)
    reference = Column(String(length=80), nullable=True, default='')
    original_amount = Column(MoneyColumn(), nullable=False)
    balance = Column(MoneyColumn(), nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    status = Column(String(length=20), nullable=False, default='Pendiente', index=True)
    created_by = Column(String(length=120), nullable=False, default='Administrador')
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    initial_payment = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))


class CreditPayment(Base):
    __tablename__ = 'credit_payments'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('credit_accounts.id', ondelete='RESTRICT'), nullable=False, index=True)
    amount = Column(MoneyColumn(), nullable=False)
    amount_received = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    change_amount = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    payment_method = Column(String(length=30), nullable=False)
    reference = Column(String(length=120), nullable=True, default='')
    received_by = Column(String(length=120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    account = relationship('CreditAccount', backref='payments')


class OperationalIncident(Base):
    """Alerta operativa persistente con seguimiento y cierre auditable."""
    __tablename__ = 'operational_incidents'
    id = Column(Integer, primary_key=True)
    source_key = Column(String(length=160), nullable=True, index=True, default='')
    category = Column(String(length=40), nullable=False, index=True)
    title = Column(String(length=180), nullable=False)
    detail = Column(String(length=800), nullable=True, default='')
    priority = Column(String(length=20), nullable=False, default='Media', index=True)
    status = Column(String(length=20), nullable=False, default='Nueva', index=True)
    responsible = Column(String(length=120), nullable=True, default='')
    resolution = Column(String(length=800), nullable=True, default='')
    created_by = Column(String(length=120), nullable=False, default='Sistema')
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)
    updated_at = Column(DateTime, nullable=False, default=mexico_now)
    resolved_at = Column(DateTime, nullable=True)


class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    id = Column(Integer, primary_key=True)
    supplier = Column(String(length=120), nullable=False, index=True)
    status = Column(String(length=20), nullable=False, default='Pendiente', index=True)
    expected_date = Column(Date, nullable=True)
    total = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    notes = Column(String(length=500), nullable=True, default='')
    created_by = Column(String(length=120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)
    received_at = Column(DateTime, nullable=True)
    items = relationship('PurchaseOrderItem', back_populates='order', cascade='all, delete-orphan')


class PurchaseOrderItem(Base):
    __tablename__ = 'purchase_order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    product_name = Column(String(length=80), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(MoneyColumn(), nullable=False)
    order = relationship('PurchaseOrder', back_populates='items')


class AuditLog(Base):
    """Bitácora operativa inmutable para acciones sensibles."""
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(length=50), nullable=False, index=True)
    actor = Column(String(length=120), nullable=False)
    entity_type = Column(String(length=50), nullable=False)
    entity_id = Column(String(length=80), nullable=True, default='')
    detail = Column(String(length=600), nullable=False)
    created_at = Column(DateTime, nullable=False, default=mexico_now, index=True)


class Customer(Base):
    """Directorio comercial opcional; vender a público general sigue siendo válido."""
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=120), nullable=False, unique=True)
    phone = Column(String(length=40), nullable=True, default='')
    phone_country = Column(String(length=2), nullable=False, default='MX')
    address = Column(String(length=300), nullable=True, default='')
    postal_code = Column(String(length=12), nullable=True, default='')
    email = Column(String(length=120), nullable=True, default='')
    tax_id = Column(String(length=40), nullable=True, default='')
    notes = Column(String(length=400), nullable=True, default='')
    is_active = Column(Boolean, nullable=False, default=True)
    loyalty_points = Column(Integer, nullable=False, default=0)
    lifetime_spend = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    updated_at = Column(DateTime, nullable=False, default=mexico_now)


class CashRegister(Base):
    """Caja/terminal física o lógica que puede tener su propio turno."""
    __tablename__ = 'cash_registers'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=80), nullable=False, unique=True, default='Caja principal')
    code = Column(String(length=30), nullable=False, unique=True, default='MAIN')
    location = Column(String(length=120), nullable=True, default='')
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=mexico_now)


class CashOpening(Base):
    """Apertura de un turno de caja definida exclusivamente por administración."""
    __tablename__ = 'cash_openings'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    opening_amount = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_limit = Column(MoneyColumn(), nullable=False, default=CUPMoney('3000.00'))
    opened_by = Column(String(length=120), nullable=False)
    shift_responsible = Column(String(length=120), nullable=False, default='Vendedor')
    notes = Column(String(length=400), nullable=True, default='')
    denomination_details = Column(Text, nullable=True, default='{}')
    source_close_id = Column(Integer, nullable=True)
    register_id = Column(Integer, ForeignKey('cash_registers.id'), nullable=True, index=True)
    register_name = Column(String(length=80), nullable=True, default='Caja principal')
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    register = relationship('CashRegister')


class CashMovement(Base):
    """Entrada o retiro autorizado que modifica el efectivo físico de caja."""
    __tablename__ = 'cash_movements'
    id = Column(Integer, primary_key=True)
    opening_id = Column(Integer, ForeignKey('cash_openings.id'), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    movement_type = Column(String(length=20), nullable=False)
    amount = Column(MoneyColumn(), nullable=False)
    reason = Column(String(length=300), nullable=False)
    authorized_by = Column(String(length=120), nullable=False)
    register_id = Column(Integer, ForeignKey('cash_registers.id'), nullable=True, index=True)
    register_name = Column(String(length=80), nullable=True, default='Caja principal')
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    register = relationship('CashRegister')


class CashClose(Base):
    """Fotografía inmutable de la conciliación de un turno de caja."""
    __tablename__ = 'cash_closes'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    opening_id = Column(Integer, ForeignKey('cash_openings.id'), nullable=True,
                        unique=True, index=True)
    cashier = Column(String(length=120), nullable=False)
    operation_count = Column(Integer, nullable=False, default=0)
    total_sales = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_sales = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    card_sales = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    transfer_sales = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    other_sales = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    total_expenses = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_expenses = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    opening_cash = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_additions = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_withdrawals = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    expected_cash = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    counted_cash = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    difference = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    notes = Column(String(length=600), nullable=True, default='')
    denomination_details = Column(Text, nullable=True, default='{}')
    register_id = Column(Integer, ForeignKey('cash_registers.id'), nullable=True, index=True)
    register_name = Column(String(length=80), nullable=True, default='Caja principal')
    created_at = Column(DateTime, nullable=False, default=mexico_now)
    register = relationship('CashRegister')


class BusinessProfile(Base):
    __tablename__ = 'business_profile'
    id = Column(Integer, primary_key=True)
    business_name = Column(String(length=120), nullable=False, default='Grupo ECCOS')
    owner_name = Column(String(length=120), nullable=True, default='')
    phone = Column(String(length=40), nullable=True, default='')
    address = Column(String(length=250), nullable=True, default='')
    whatsapp = Column(String(length=40), nullable=True, default='')
    email = Column(String(length=120), nullable=True, default='')
    tax_id = Column(String(length=60), nullable=True, default='')
    website = Column(String(length=180), nullable=True, default='')
    logo_path = Column(String(length=500), nullable=True, default='')
    legal_name = Column(String(length=160), nullable=True, default='')
    business_type = Column(String(length=80), nullable=True, default='Comercio minorista')
    slogan = Column(String(length=180), nullable=True, default='')
    city = Column(String(length=100), nullable=True, default='')
    state = Column(String(length=100), nullable=True, default='')
    postal_code = Column(String(length=12), nullable=True, default='')
    tax_regime = Column(String(length=160), nullable=True, default='')
    receipt_header = Column(String(length=300), nullable=True, default='')
    ticket_prefix = Column(String(length=12), nullable=True, default='V')
    receipt_footer = Column(String(length=500), nullable=True, default='Gracias por su compra.')
    enabled_payment_methods = Column(Text, nullable=True, default='')
    return_policy = Column(String(length=500), nullable=True, default='')
    brand_color = Column(String(length=7), nullable=True, default='#123B6D')
    app_background_color = Column(String(length=7), nullable=True, default='#F1F3F6')
    app_surface_color = Column(String(length=7), nullable=True, default='#FFFFFF')
    app_text_color = Column(String(length=7), nullable=True, default='#111820')
    document_primary_color = Column(String(length=7), nullable=True, default='#123B6D')
    document_text_color = Column(String(length=7), nullable=True, default='#111820')
    logo_data = Column(Text, nullable=True, default='')
    logo_mime = Column(String(length=40), nullable=True, default='')


class CatalogSettings(Base):
    """Configuración pública del micrositio; nunca contiene datos financieros."""
    __tablename__ = 'catalog_settings'
    id = Column(Integer, primary_key=True)
    slug = Column(String(length=80), nullable=False, unique=True, index=True, default='mi-negocio')
    is_published = Column(Boolean, nullable=False, default=False)
    headline = Column(String(length=180), nullable=True, default='')
    about = Column(String(length=800), nullable=True, default='')
    whatsapp = Column(String(length=40), nullable=True, default='')
    business_hours = Column(String(length=300), nullable=True, default='')
    service_message = Column(String(length=300), nullable=True, default='')
    show_out_of_stock = Column(Boolean, nullable=False, default=True)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(length=80), nullable=False, unique=True)
    password_hash = Column(String(length=300), nullable=False)
    recovery_hash = Column(String(length=300), nullable=False)
    role = Column(String(length=30), nullable=False, default='store')
    display_name = Column(String(length=120), nullable=True, default='')
    is_active = Column(Boolean, nullable=False, default=True)
    commission_bps = Column(Integer, nullable=False, default=0)
    # El usuario sólo vive en la base de autenticación.  Los datos operativos
    # se guardan en la base indicada por esta clave, nunca mezclados aquí.
    workspace_key = Column(String(length=180), nullable=True, default='primary')
    credential_version = Column(Integer, nullable=False, default=0)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    failed_recovery_attempts = Column(Integer, nullable=False, default=0)
    login_blocked_until = Column(DateTime, nullable=True)
    recovery_blocked_until = Column(DateTime, nullable=True)

class AuthSession(Base):
    """Sesión web revocable; nunca almacena contraseñas ni el token original."""
    __tablename__ = 'auth_sessions'
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(length=64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    expires_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = relationship('User')
