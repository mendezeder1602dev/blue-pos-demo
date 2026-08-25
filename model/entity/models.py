from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey
from sqlalchemy import Integer, Boolean
from sqlalchemy import String, Text
from sqlalchemy import Date, DateTime
from model.util.money_colum import MoneyColumn
from model.util.monetary_types import CUPMoney
from datetime import date, datetime

Base = declarative_base()

PRODUCT_DESCRIPTION_MAX_LENGTH = 300
PRODUCT_NAME_MAX_LENGTH = 80

class Product(Base):

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
    minimum_stock = Column(Integer, nullable=False, default=5)
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
    date = Column(Date, nullable=False, default=date.today)
    price = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    cost = Column(MoneyColumn(), nullable=False, default=CUPMoney('1.00'))
    payment_method = Column(String(length=50), nullable=False, default='cash')
    payment_details = Column(String(length=250), nullable=True, default='')
    transaction_id = Column(String(length=36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    product_name = Column(String(length=80), nullable=True, default='')
    cashier = Column(String(length=120), nullable=False, default='Vendedor')
    status = Column(String(length=30), nullable=False, default='Completada', index=True)
    reversal_reason = Column(String(length=300), nullable=True, default='')
    reversed_at = Column(DateTime, nullable=True)
    customer = Column(String(length=120), nullable=True, default='Público general')
    # Las eliminaciones físicas sólo se reservan para mantenimiento/pruebas. La
    # aplicación usa archivado lógico y nunca invoca este borrado sobre ventas reales.
    product = relationship('Product', backref=backref('sales', cascade='all,delete'))

    @property
    def profit(self):
        if self.price is None or self.cost is None:
            return None
        return self.price - self.cost


class Quote(Base):
    __tablename__ = 'quotes'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=date.today)
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
    date = Column(Date, nullable=False, default=date.today)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    is_active = Column(Boolean, nullable=False, default=True)


class HeldSale(Base):
    """Carrito suspendido que puede recuperarse sin afectar existencias."""
    __tablename__ = 'held_sales'
    id = Column(Integer, primary_key=True)
    label = Column(String(length=120), nullable=False)
    notes = Column(String(length=300), nullable=True, default='')
    created_by = Column(String(length=120), nullable=False, default='Vendedor')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
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
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)


class AuditLog(Base):
    """Bitácora operativa inmutable para acciones sensibles."""
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(length=50), nullable=False, index=True)
    actor = Column(String(length=120), nullable=False)
    entity_type = Column(String(length=50), nullable=False)
    entity_id = Column(String(length=80), nullable=True, default='')
    detail = Column(String(length=600), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)


class Customer(Base):
    """Directorio comercial opcional; vender a público general sigue siendo válido."""
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=120), nullable=False, unique=True)
    phone = Column(String(length=40), nullable=True, default='')
    email = Column(String(length=120), nullable=True, default='')
    tax_id = Column(String(length=40), nullable=True, default='')
    notes = Column(String(length=400), nullable=True, default='')
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CashOpening(Base):
    """Apertura diaria definida exclusivamente por administración."""
    __tablename__ = 'cash_openings'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    opening_amount = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_limit = Column(MoneyColumn(), nullable=False, default=CUPMoney('3000.00'))
    opened_by = Column(String(length=120), nullable=False)
    notes = Column(String(length=400), nullable=True, default='')
    denomination_details = Column(Text, nullable=True, default='{}')
    source_close_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CashMovement(Base):
    """Entrada o retiro autorizado que modifica el efectivo físico de caja."""
    __tablename__ = 'cash_movements'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    movement_type = Column(String(length=20), nullable=False)
    amount = Column(MoneyColumn(), nullable=False)
    reason = Column(String(length=300), nullable=False)
    authorized_by = Column(String(length=120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class CashClose(Base):
    """Fotografía inmutable de la conciliación diaria de caja."""
    __tablename__ = 'cash_closes'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
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
    created_at = Column(DateTime, nullable=False, default=datetime.now)


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
    receipt_footer = Column(String(length=500), nullable=True, default='Gracias por su compra.')
    return_policy = Column(String(length=500), nullable=True, default='')
    brand_color = Column(String(length=7), nullable=True, default='#123B6D')
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
    # El usuario sólo vive en la base de autenticación.  Los datos operativos
    # se guardan en la base indicada por esta clave, nunca mezclados aquí.
    workspace_key = Column(String(length=180), nullable=True, default='primary')
    credential_version = Column(Integer, nullable=False, default=0)

class AuthSession(Base):
    """Sesión web revocable; nunca almacena contraseñas ni el token original."""
    __tablename__ = 'auth_sessions'
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(length=64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    expires_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = relationship('User')
