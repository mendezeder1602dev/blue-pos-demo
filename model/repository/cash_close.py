from sqlalchemy import FLOAT, cast, func, select

from model.entity.models import CashClose, CashOpening
from model.util.monetary_types import CUPMoney
from model.authorization import require_role


class CashCloseRepository:
    """Persiste cierres diarios y consultas de conciliación de efectivo."""
    def __init__(self, session):
        self.__session = session

    def insert(self, cash_close: CashClose) -> CashClose:
        require_role('superuser', 'seller')
        if cash_close.opening_id is not None and self.get_for_opening(cash_close.opening_id):
            raise ValueError('Este turno ya tiene un cierre de caja.')
        if cash_close.opening_id is not None:
            opening = self.__session.get(CashOpening, int(cash_close.opening_id))
            if opening is not None:
                cash_close.register_id = opening.register_id
                cash_close.register_name = opening.register_name
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
        try:
            self.__session.add(cash_close)
            self.__session.commit()
        except Exception:
            # SQLAlchemy bloquea toda consulta posterior hasta revertir el flush
            # fallido. El repositorio debe devolver la sesión en estado utilizable.
            self.__session.rollback()
            raise
        return cash_close

    def get_by_date(self, close_date):
        """Conserva compatibilidad y devuelve el cierre más reciente del día."""
        return self.__session.scalar(
            select(CashClose).where(CashClose.date == close_date)
            .order_by(CashClose.created_at.desc(), CashClose.id.desc()).limit(1)
        )

    def get_for_opening(self, opening_id):
        if opening_id is None:
            return None
        return self.__session.scalar(
            select(CashClose).where(CashClose.opening_id == opening_id).limit(1)
        )

    def get_for_date(self, close_date):
        return self.__session.scalars(
            select(CashClose).where(CashClose.date == close_date)
            .order_by(CashClose.created_at.asc(), CashClose.id.asc())
        ).all()

    def get_all(self):
        return self.__session.scalars(
            select(CashClose).order_by(CashClose.date.desc(), CashClose.id.desc())
        ).all()

    def get_difference_between(self, initial_date, final_date) -> float:
        """Suma sobrantes y faltantes en SQL para el periodo solicitado."""
        value = self.__session.scalar(
            select(func.sum(cast(CashClose.difference, FLOAT))).where(
                CashClose.date >= initial_date, CashClose.date <= final_date)
        )
        return float(value or 0)

    def get_latest_before(self, close_date):
        """Devuelve el último cierre anterior a la fecha solicitada."""
        return self.__session.scalar(
            select(CashClose)
            .where(CashClose.date < close_date)
            .order_by(CashClose.date.desc(), CashClose.id.desc())
            .limit(1)
        )

    def get_latest(self):
        return self.__session.scalar(
            select(CashClose)
            .order_by(CashClose.created_at.desc(), CashClose.id.desc())
            .limit(1)
        )
