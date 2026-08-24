from sqlalchemy import select

from model.entity.models import CashClose
from model.util.monetary_types import CUPMoney


class CashCloseRepository:
    def __init__(self, session):
        self.__session = session

    def insert(self, cash_close: CashClose) -> CashClose:
        if self.get_by_date(cash_close.date) is not None:
            raise ValueError(f'Ya existe un corte de caja para {cash_close.date}.')
        if not cash_close.cashier.strip():
            raise ValueError('Indica el responsable del corte.')
        money_fields = (
            'total_sales', 'cash_sales', 'card_sales', 'transfer_sales', 'other_sales',
            'total_expenses', 'cash_expenses', 'opening_cash', 'cash_additions',
            'cash_withdrawals', 'expected_cash', 'counted_cash', 'difference',
        )
        for field in money_fields:
            if getattr(cash_close, field) is None:
                setattr(cash_close, field, CUPMoney('0.00'))
        for field in ('opening_cash', 'cash_additions', 'cash_withdrawals',
                      'cash_expenses', 'counted_cash'):
            if getattr(cash_close, field).amount < 0:
                raise ValueError('Los importes capturados no pueden ser negativos.')
        self.__session.add(cash_close)
        self.__session.commit()
        return cash_close

    def get_by_date(self, close_date):
        return self.__session.scalar(
            select(CashClose).where(CashClose.date == close_date)
        )

    def get_all(self):
        return self.__session.scalars(
            select(CashClose).order_by(CashClose.date.desc(), CashClose.id.desc())
        ).all()
