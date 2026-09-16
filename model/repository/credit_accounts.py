"""Cartera local de cuentas por cobrar y por pagar."""
from datetime import date
from sqlalchemy import select
from model.authorization import require_role
from model.entity.models import AuditLog, CashClose, CashMovement, CashOpening, CreditAccount, CreditPayment
from model.timezone import mexico_now, mexico_today
from model.util.monetary_types import CUPMoney


class CreditAccountRepository:
    TYPES = ('Cobrar', 'Pagar')
    METHODS = ('Efectivo', 'Transferencia', 'Tarjeta', 'Otro')
    def __init__(self, session): self._session = session
    def create(self, account_type, party_name, concept, amount, due_date, actor, reference='',
               initial_payment=0, commit=True, register_id=None):
        if account_type not in self.TYPES: raise ValueError('El tipo de cuenta no es válido.')
        require_role('superuser', 'seller')
        if account_type == 'Pagar': require_role('superuser')
        total, down = round(float(amount), 2), round(float(initial_payment or 0), 2)
        if total <= 0 or down < 0 or down >= total: raise ValueError('Revisa el importe y el enganche.')
        if not party_name.strip() or not concept.strip(): raise ValueError('Indica responsable y concepto.')
        if not isinstance(due_date, date) or due_date < mexico_today(): raise ValueError('El vencimiento debe ser hoy o posterior.')
        if account_type == 'Pagar' and down: raise ValueError('Los pagos a proveedor se registran como abonos.')
        account = CreditAccount(account_type=account_type, party_name=party_name.strip(), concept=concept.strip(), reference=(reference or '').strip(), original_amount=CUPMoney(f'{total:.2f}'), balance=CUPMoney(f'{total-down:.2f}'), initial_payment=CUPMoney(f'{down:.2f}'), due_date=due_date, status='Abonada' if down else 'Pendiente', created_by=(actor or 'Administrador').strip())
        try:
            self._session.add(account); self._session.flush()
            if down:
                opening = self._open_cash(register_id)
                if opening is None: raise ValueError('Abre la caja antes de registrar un enganche.')
                self._session.add(CreditPayment(account_id=account.id, amount=CUPMoney(f'{down:.2f}'), amount_received=CUPMoney(f'{down:.2f}'), change_amount=CUPMoney('0.00'), payment_method='Efectivo', reference='Enganche inicial', received_by=actor))
                self._cash(opening, 'Entrada', down, f'Enganche crédito: {account.party_name} · Cuenta #{account.id}', actor)
            self._audit('cuenta_credito_creada', account.id, f'{account_type}: {account.party_name}; total ${total:.2f}', actor)
            if commit:
                self._session.commit()
        except Exception:
            if commit:
                self._session.rollback()
            raise
        return account
    def active_accounts(self, account_type=None):
        query = select(CreditAccount).where(CreditAccount.status != 'Pagada')
        if account_type: query = query.where(CreditAccount.account_type == account_type)
        return list(self._session.scalars(query.order_by(CreditAccount.due_date, CreditAccount.id.desc())).all())
    def payments_for(self, account_id): return list(self._session.scalars(select(CreditPayment).where(CreditPayment.account_id == int(account_id)).order_by(CreditPayment.created_at.desc())).all())
    def summary(self):
        accounts, today = self.active_accounts(), mexico_today()
        return {'to_collect': sum(float(a.balance.amount) for a in accounts if a.account_type == 'Cobrar'), 'to_pay': sum(float(a.balance.amount) for a in accounts if a.account_type == 'Pagar'), 'overdue': [a for a in accounts if a.due_date < today], 'due_soon': [a for a in accounts if 0 <= (a.due_date-today).days <= 3]}
    def register_payment(self, account_id, amount, method, actor, reference='', received=None,
                         register_id=None):
        account = self._session.get(CreditAccount, int(account_id))
        if account is None or account.status == 'Pagada': raise ValueError('La cuenta no está disponible.')
        require_role('superuser', 'seller')
        if account.account_type == 'Pagar': require_role('superuser')
        value = round(float(amount), 2); received = value if received is None else round(float(received), 2)
        if method not in self.METHODS or value <= 0 or value > float(account.balance.amount)+.001: raise ValueError('El abono no es válido.')
        if received < value or (method != 'Efectivo' and received != value): raise ValueError('El importe recibido no es válido.')
        try:
            change = received-value if method == 'Efectivo' else 0
            payment = CreditPayment(account_id=account.id, amount=CUPMoney(f'{value:.2f}'), amount_received=CUPMoney(f'{received:.2f}'), change_amount=CUPMoney(f'{change:.2f}'), payment_method=method, reference=(reference or '').strip(), received_by=actor)
            self._session.add(payment); account.balance=CUPMoney(f'{max(0,float(account.balance.amount)-value):.2f}'); account.status='Pagada' if float(account.balance.amount) <= .001 else 'Abonada'
            if method == 'Efectivo':
                opening=self._open_cash(register_id)
                if opening is None: raise ValueError('Abre la caja antes de registrar efectivo.')
                self._cash(opening, 'Entrada' if account.account_type == 'Cobrar' else 'Retiro', value, f'Abono {account.account_type.lower()}: {account.party_name} · Cuenta #{account.id}', actor)
            self._audit('abono_credito_registrado', account.id, f'Abono ${value:.2f}; saldo ${float(account.balance.amount):.2f}', actor); self._session.commit(); return payment
        except Exception: self._session.rollback(); raise
    def _open_cash(self, register_id=None):
        statement = select(CashOpening).where(CashOpening.date == mexico_today(), ~select(CashClose.id).where(CashClose.opening_id == CashOpening.id).exists())
        if register_id is not None: statement = statement.where(CashOpening.register_id == int(register_id))
        return self._session.scalar(statement.order_by(CashOpening.created_at.desc()).limit(1))
    def _cash(self, opening, movement_type, amount, reason, actor): self._session.add(CashMovement(opening_id=opening.id, date=mexico_today(), movement_type=movement_type, amount=CUPMoney(f'{amount:.2f}'), reason=reason, authorized_by=actor, created_at=mexico_now(), register_id=opening.register_id, register_name=opening.register_name))
    def _audit(self, event, entity_id, detail, actor): self._session.add(AuditLog(event_type=event, actor=(actor or 'Administrador').strip(), entity_type='credit_account', entity_id=str(entity_id), detail=detail))
