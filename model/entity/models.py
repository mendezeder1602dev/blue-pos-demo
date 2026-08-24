from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, ForeignKey
from sqlalchemy import Integer, Boolean
from sqlalchemy import String
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


class CashOpening(Base):
    """Apertura diaria definida exclusivamente por administración."""
    __tablename__ = 'cash_openings'
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    opening_amount = Column(MoneyColumn(), nullable=False, default=CUPMoney('0.00'))
    cash_limit = Column(MoneyColumn(), nullable=False, default=CUPMoney('3000.00'))
    opened_by = Column(String(length=120), nullable=False)
    notes = Column(String(length=400), nullable=True, default='')
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
