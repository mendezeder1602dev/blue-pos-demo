from sqlalchemy import TypeDecorator, Text
from money import Money
from model.util.monetary_types import MONEY_CURRENCY


class MoneyColumn(TypeDecorator):

    impl = Text

    cache_ok = True

    def process_bind_param(self, money: Money, dialect):
        return '{}'.format(money.amount)

    def process_result_value(self, money_as_str: str, dialect) -> Money:
        if money_as_str is None:
            return None

        return Money(money_as_str, MONEY_CURRENCY)

    def copy(self, **kw):
        return MoneyColumn()
