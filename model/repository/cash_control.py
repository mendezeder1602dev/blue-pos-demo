from sqlalchemy import exists, select

from model.entity.models import CashClose, CashMovement, CashOpening, CashRegister
from model.timezone import mexico_today
from model.util.monetary_types import CUPMoney


class CashControlRepository:
    ADMIN_ROLE = 'superuser'
    CASHIER_ROLES = ('superuser', 'seller')
    MOVEMENT_TYPES = ('Retiro', 'Entrada')

    def __init__(self, session):
        self.__session = session

    @staticmethod
    def _require_administrator(role):
        if role != CashControlRepository.ADMIN_ROLE:
            raise PermissionError('Solo el administrador puede realizar esta operación.')

    @staticmethod
    def _require_cashier(role):
        if role not in CashControlRepository.CASHIER_ROLES:
            raise PermissionError('La cuenta actual no puede abrir una caja.')

    def ensure_default_register(self):
        register = self.__session.scalar(
            select(CashRegister).where(CashRegister.code == 'MAIN'))
        if register is None:
            register = CashRegister(
                name='Caja principal', code='MAIN', location='Mostrador',
                is_active=True)
            self.__session.add(register)
            self.__session.commit()
        return register

    def get_registers(self, include_inactive=False):
        self.ensure_default_register()
        statement = select(CashRegister)
        if not include_inactive:
            statement = statement.where(CashRegister.is_active == True)
        return list(self.__session.scalars(statement.order_by(CashRegister.name)).all())

    def create_register(self, name, code='', location='', authorized_role=''):
        self._require_administrator(authorized_role)
        clean_name = (name or '').strip()
        clean_code = (code or clean_name[:12] or 'CAJA').strip().upper().replace(' ', '-')
        if not clean_name:
            raise ValueError('Indica el nombre de la caja.')
        if self.__session.scalar(select(CashRegister).where(CashRegister.name == clean_name)):
            raise ValueError('Ya existe una caja con ese nombre.')
        if self.__session.scalar(select(CashRegister).where(CashRegister.code == clean_code)):
            raise ValueError('Ya existe una caja con ese código.')
        register = CashRegister(
            name=clean_name, code=clean_code, location=(location or '').strip(),
            is_active=True)
        self.__session.add(register)
        self.__session.commit()
        return register

    def open_day(self, opening: CashOpening, authorized_role: str) -> CashOpening:
        self._require_cashier(authorized_role)
        if opening.date != mexico_today():
            raise ValueError('La apertura solo puede registrarse para el día actual.')
        register = self._resolve_register(opening.register_id)
        opening.register_id = register.id
        opening.register_name = register.name
        pending = self.get_unclosed_opening(register.id)
        if pending is not None:
            raise ValueError(
                f'La caja mantiene abierto el turno #{pending.id} del {pending.date}. '
                'Ciérralo antes de iniciar otro.')
        if not opening.opened_by.strip():
            raise ValueError('Indica quién autoriza la apertura.')
        opening.shift_responsible = (opening.shift_responsible or 'Vendedor').strip()
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
        if movement.date != mexico_today():
            raise ValueError('Los movimientos solo pueden registrarse en la caja del día actual.')
        register = self._resolve_register(movement.register_id)
        active_opening = self.get_opening(movement.date, register.id)
        if active_opening is None:
            raise ValueError('Primero abre esta caja del día.')
        movement.opening_id = active_opening.id
        movement.register_id = register.id
        movement.register_name = register.name
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
        if movement.movement_type == 'Retiro' and available_cash is None:
            raise ValueError(
                'No se pudo comprobar el efectivo disponible para autorizar el retiro.')
        self.__session.add(movement)
        self.__session.commit()
        return movement

    def get_opening(self, opening_date, register_id=None):
        """Devuelve el turno activo de la fecha, no una apertura ya cerrada."""
        statement = select(CashOpening).where(
            CashOpening.date == opening_date,
            ~exists().where(CashClose.opening_id == CashOpening.id),
        )
        if register_id is not None:
            statement = statement.where(CashOpening.register_id == int(register_id))
        return self.__session.scalar(
            statement.order_by(CashOpening.created_at.desc(), CashOpening.id.desc()).limit(1))

    def get_unclosed_opening(self, register_id=None):
        """Devuelve el turno pendiente más antiguo, incluso si pertenece a otro día."""
        statement = select(CashOpening).where(
            ~exists().where(CashClose.opening_id == CashOpening.id))
        if register_id is not None:
            statement = statement.where(CashOpening.register_id == int(register_id))
        return self.__session.scalar(statement.order_by(
            CashOpening.date.asc(), CashOpening.created_at.asc(), CashOpening.id.asc()
        ).limit(1))

    def get_unclosed_openings(self, register_id=None):
        """Lista todos los turnos sin corte para alertas e historial."""
        statement = select(CashOpening).where(
            ~exists().where(CashClose.opening_id == CashOpening.id))
        if register_id is not None:
            statement = statement.where(CashOpening.register_id == int(register_id))
        return list(self.__session.scalars(statement.order_by(
            CashOpening.date.asc(), CashOpening.created_at.asc(), CashOpening.id.asc()
        )).all())

    def get_openings(self, opening_date, register_id=None):
        statement = select(CashOpening).where(CashOpening.date == opening_date)
        if register_id is not None:
            statement = statement.where(CashOpening.register_id == int(register_id))
        return self.__session.scalars(
            statement.order_by(CashOpening.created_at.asc(), CashOpening.id.asc())
        ).all()

    def get_all_openings(self, register_id=None):
        """Devuelve los turnos para consulta histórica, incluidos los ya cerrados."""
        statement = select(CashOpening)
        if register_id is not None:
            statement = statement.where(CashOpening.register_id == int(register_id))
        return self.__session.scalars(
            statement.order_by(
                CashOpening.date.desc(), CashOpening.created_at.desc(), CashOpening.id.desc())
        ).all()

    def get_movements(self, movement_date, opening_id=None, register_id=None):
        statement = select(CashMovement).where(CashMovement.date == movement_date)
        if opening_id is not None:
            statement = statement.where(CashMovement.opening_id == opening_id)
        if register_id is not None:
            statement = statement.where(CashMovement.register_id == int(register_id))
        return self.__session.scalars(
            statement.order_by(CashMovement.created_at.asc(), CashMovement.id.asc())
        ).all()

    def totals_for_date(self, movement_date, opening_id=None, register_id=None):
        totals = {'Retiro': 0.0, 'Entrada': 0.0}
        for movement in self.get_movements(movement_date, opening_id, register_id):
            totals[movement.movement_type] += float(movement.amount.amount)
        return totals

    def _resolve_register(self, register_id=None):
        if register_id is None:
            return self.ensure_default_register()
        register = self.__session.get(CashRegister, int(register_id))
        if register is None or not register.is_active:
            raise ValueError('La caja seleccionada no está disponible.')
        return register
