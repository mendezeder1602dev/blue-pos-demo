"""Emisión y consumo auditable de vales de saldo a favor."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from model.entity.models import StoreCreditMovement, StoreCreditVoucher
from model.util.monetary_types import CUPMoney


class StoreCreditRepository:
    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _new_code():
        token = secrets.token_hex(8).upper()
        return f'VALE-{token[:4]}-{token[4:8]}-{token[8:12]}-{token[12:]}'

    def issue(self, transaction_id, amount, reason, actor, customer='Público general'):
        value = float(amount)
        if value <= 0:
            raise ValueError('El importe del vale debe ser mayor que cero.')
        voucher = StoreCreditVoucher(
            code=self._new_code(), original_transaction_id=str(transaction_id),
            initial_amount=CUPMoney(f'{value:.2f}'), balance=CUPMoney(f'{value:.2f}'),
            customer=customer or 'Público general', reason=reason, issued_by=actor,
        )
        self._session.add(voucher)
        self._session.flush()
        self._session.add(StoreCreditMovement(
            voucher_id=voucher.id, movement_type='Emisión',
            amount=CUPMoney(f'{value:.2f}'), performed_by=actor,
        ))
        self._session.commit()
        return voucher

    def find_active(self, code):
        normalized = str(code or '').strip().upper()
        voucher = self._session.scalar(select(StoreCreditVoucher).where(
            StoreCreditVoucher.code == normalized))
        if voucher is None:
            raise ValueError('El vale no existe.')
        if voucher.status != 'Activo' or float(voucher.balance.amount) <= 0:
            raise ValueError('El vale ya no tiene saldo disponible.')
        return voucher

    def get_all(self):
        return list(self._session.scalars(
            select(StoreCreditVoucher).order_by(StoreCreditVoucher.issued_at.desc())
        ).all())

    def get_movements(self, voucher_id):
        return list(self._session.scalars(
            select(StoreCreditMovement).where(
                StoreCreditMovement.voucher_id == int(voucher_id)
            ).order_by(StoreCreditMovement.created_at.desc())
        ).all())

    def find_replacement_for_sale(self, transaction_id):
        """Devuelve el vale nuevo creado por un remanente, si lo hubo."""
        return self._session.scalar(
            select(StoreCreditVoucher).where(
                StoreCreditVoucher.original_transaction_id == str(transaction_id),
                StoreCreditVoucher.reason.like('Remanente del vale %'),
            ).order_by(StoreCreditVoucher.issued_at.desc(), StoreCreditVoucher.id.desc())
        )

    def rollover_existing_balance(self, code, transaction_id, actor):
        """Migra de forma segura un remanente legado a un código nuevo."""
        source = self.find_active(code)
        remaining = round(float(source.balance.amount), 2)
        source.balance = CUPMoney('0.00')
        source.status = 'Agotado'
        self._session.add(StoreCreditMovement(
            voucher_id=source.id, movement_type='Saldo transferido',
            amount=CUPMoney(f'{-remaining:.2f}'),
            sale_transaction_id=str(transaction_id), performed_by=actor,
        ))
        replacement = StoreCreditVoucher(
            code=self._new_code(), original_transaction_id=str(transaction_id),
            initial_amount=CUPMoney(f'{remaining:.2f}'),
            balance=CUPMoney(f'{remaining:.2f}'), status='Activo',
            customer=source.customer or 'Público general',
            reason=f'Remanente del vale {source.code}', issued_by=actor,
        )
        self._session.add(replacement)
        self._session.flush()
        self._session.add(StoreCreditMovement(
            voucher_id=replacement.id, movement_type='Emisión',
            amount=CUPMoney(f'{remaining:.2f}'),
            sale_transaction_id=str(transaction_id), performed_by=actor,
        ))
        self._session.commit()
        return replacement

    def redeem(self, code, amount, transaction_id, actor):
        voucher = self.find_active(code)
        value = round(float(amount), 2)
        balance = float(voucher.balance.amount)
        if value <= 0 or value > balance:
            raise ValueError('El importe solicitado supera el saldo del vale.')
        voucher.balance = CUPMoney(f'{balance - value:.2f}')
        if float(voucher.balance.amount) <= 0:
            voucher.status = 'Agotado'
        self._session.add(StoreCreditMovement(
            voucher_id=voucher.id, movement_type='Aplicación',
            amount=CUPMoney(f'{-value:.2f}'), sale_transaction_id=transaction_id,
            performed_by=actor,
        ))
        self._session.commit()
        return voucher
