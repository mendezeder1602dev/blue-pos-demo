from sqlalchemy import select

from datetime import date

from model.entity.models import CashClose, CashMovement, CashOpening
from model.util.monetary_types import CUPMoney


class CashControlRepository:
    ADMIN_ROLE = 'superuser'
    MOVEMENT_TYPES = ('Retiro', 'Entrada')

    def __init__(self, session):
        self.__session = session

    @staticmethod
    def _require_administrator(role):
        if role != CashControlRepository.ADMIN_ROLE:
            raise PermissionError('Solo el administrador puede realizar esta operación.')

    def open_day(self, opening: CashOpening, authorized_role: str) -> CashOpening:
        self._require_administrator(authorized_role)
        if opening.date != date.today():
            raise ValueError('La apertura solo puede registrarse para el día actual.')
        if self.get_opening(opening.date) is not None:
            raise ValueError(f'La caja de {opening.date} ya fue abierta.')
        if not opening.opened_by.strip():
            raise ValueError('Indica quién autoriza la apertura.')
        if opening.opening_amount.amount < 0:
            raise ValueError('El fondo inicial no puede ser negativo.')
        if opening.cash_limit.amount <= 0:
            raise ValueError('El límite recomendado debe ser mayor que cero.')
        self.__session.add(opening)
        self.__session.commit()
        return opening

    def add_movement(self, movement: CashMovement, authorized_role: str,
                     available_cash: float = None) -> CashMovement:
        self._require_administrator(authorized_role)
        if movement.date != date.today():
            raise ValueError('Los movimientos solo pueden registrarse en la caja del día actual.')
        if self.get_opening(movement.date) is None:
            raise ValueError('Primero abre la caja del día.')
        if self.__session.scalar(
                select(CashClose).where(CashClose.date == movement.date)) is not None:
            raise ValueError('La caja ya está cerrada; no admite nuevos movimientos.')
        if movement.movement_type not in self.MOVEMENT_TYPES:
            raise ValueError('El tipo de movimiento no es válido.')
        if movement.amount is None or movement.amount <= CUPMoney('0.00'):
            raise ValueError('El importe debe ser mayor que cero.')
        if not movement.reason or not movement.reason.strip():
            raise ValueError('Es obligatorio indicar el motivo del movimiento.')
        if not movement.authorized_by or not movement.authorized_by.strip():
            raise ValueError('Indica quién autoriza el movimiento.')
        if (movement.movement_type == 'Retiro' and available_cash is not None
                and float(movement.amount.amount) > float(available_cash)):
            raise ValueError('El retiro no puede superar el efectivo estimado en caja.')
        self.__session.add(movement)
        self.__session.commit()
        return movement

    def get_opening(self, opening_date):
        return self.__session.scalar(
            select(CashOpening).where(CashOpening.date == opening_date)
        )

    def get_movements(self, movement_date):
        return self.__session.scalars(
            select(CashMovement)
            .where(CashMovement.date == movement_date)
            .order_by(CashMovement.created_at.asc(), CashMovement.id.asc())
        ).all()

    def totals_for_date(self, movement_date):
        totals = {'Retiro': 0.0, 'Entrada': 0.0}
        for movement in self.get_movements(movement_date):
            totals[movement.movement_type] += float(movement.amount.amount)
        return totals
