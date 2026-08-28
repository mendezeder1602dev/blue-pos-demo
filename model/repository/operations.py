"""Casos de uso transversales: Kardex, auditoría, clientes y ventas suspendidas."""

import json

from sqlalchemy import select

from model.entity.models import (AuditLog, Customer, HeldSale, HeldSaleItem, Product,
                                 ReturnLossRequest, Sale, StockMovement)
from model.util.monetary_types import CUPMoney
from model.authorization import require_role
from model.timezone import mexico_now


class OperationsRepository:
    """Operaciones transversales: auditoría, kardex y ventas suspendidas."""

    def __init__(self, session):
        self.__session = session

    def audit(self, event_type, actor, entity_type, entity_id='', detail=''):
        self.__session.add(AuditLog(
            event_type=event_type, actor=actor, entity_type=entity_type,
            entity_id=str(entity_id or ''), detail=detail,
        ))
        self.__session.commit()

    def get_audit_logs(self, limit=300):
        return list(self.__session.scalars(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).all())

    def adjust_stock(self, product_id, delta, movement_type, reason, actor, reference='',
                     unit_cost=None, update_average_cost=False):
        """Aplica el movimiento y registra Kardex y auditoría en la misma operación."""
        require_role('superuser')
        product = self.__session.scalar(select(Product).where(Product.id == product_id))
        if product is None:
            raise ValueError('El producto ya no existe.')
        previous = product.quantity
        resulting = previous + int(delta)
        if resulting < 0:
            raise ValueError('El ajuste dejaría existencias negativas.')
        cost_detail = ''
        if unit_cost is not None:
            unit_cost = float(unit_cost)
            if int(delta) <= 0:
                raise ValueError('El costo de compra solo puede registrarse en una entrada.')
            if unit_cost <= 0:
                raise ValueError('El costo unitario debe ser mayor que cero.')
            previous_cost = float(product.cost.amount)
            if update_average_cost:
                average_cost = (
                    (previous * previous_cost) + (int(delta) * unit_cost)
                ) / resulting
                product.cost = CUPMoney(f'{average_cost:.2f}')
                cost_detail = (
                    f' Costo ${previous_cost:.2f} → ${average_cost:.2f} MXN; '
                    f'compra ${unit_cost:.2f} MXN por unidad.')
            else:
                cost_detail = (
                    f' Costo de compra ${unit_cost:.2f} MXN por unidad; '
                    'costo del producto conservado.')
        product.quantity = resulting
        self.__session.add(StockMovement(
            product_id=product.id, movement_type=movement_type, quantity=int(delta),
            previous_stock=previous, resulting_stock=resulting, reason=reason,
            reference=reference, performed_by=actor,
        ))
        self.__session.add(AuditLog(
            event_type='inventario_ajustado', actor=actor, entity_type='product',
            entity_id=str(product.id),
            detail=(f'{movement_type}: {delta:+d}. {previous} → {resulting}. '
                    f'{reason}.{cost_detail}'),
        ))
        self.__session.commit()
        return product

    def get_stock_movements(self, limit=500):
        return list(self.__session.scalars(
            select(StockMovement).order_by(StockMovement.created_at.desc()).limit(limit)
        ).all())

    def get_return_loss_requests(self, status=None):
        """Lista artículos devueltos retenidos para dictamen de inventario."""
        statement = select(ReturnLossRequest).order_by(
            ReturnLossRequest.requested_at.desc())
        if status:
            statement = statement.where(ReturnLossRequest.status == status)
        return list(self.__session.scalars(statement).all())

    def resolve_return_loss_request(self, request_id, resolution, actor, notes=''):
        """Autoriza la baja física o reintegra la devolución si finalmente es vendible."""
        require_role('superuser')
        if resolution not in ('Autorizar baja', 'Reintegrar a inventario'):
            raise ValueError('Selecciona un dictamen válido.')
        request = self.__session.get(ReturnLossRequest, int(request_id))
        if request is None:
            raise ValueError('La solicitud ya no existe.')
        if request.status != 'Pendiente':
            raise ValueError('La solicitud ya fue atendida.')
        product = self.__session.get(Product, request.product_id)
        if product is None:
            raise ValueError('El producto ya no existe en el inventario.')
        previous_stock = product.quantity
        delta = 0
        movement_type = 'Baja por devolución'
        try:
            if resolution == 'Reintegrar a inventario':
                delta = request.quantity
                product.quantity += delta
                movement_type = 'Devolución reintegrada'
                sale_ids = json.loads(request.sale_ids or '[]')
                for sale in self.__session.scalars(
                        select(Sale).where(Sale.id.in_(sale_ids))).all():
                    sale.return_disposition = 'Reintegrado tras revisión'
            request.status = ('Baja autorizada' if resolution == 'Autorizar baja'
                              else 'Reintegrado')
            request.resolved_by = actor
            request.resolved_at = mexico_now()
            request.resolution_notes = (notes or '').strip()
            self.__session.add(StockMovement(
                product_id=product.id, movement_type=movement_type, quantity=delta,
                previous_stock=previous_stock, resulting_stock=product.quantity,
                reason=(f'{request.concept}. {request.reason}. '
                        f'Dictamen: {request.resolution_notes or resolution}'),
                reference=request.transaction_id, performed_by=actor,
            ))
            self.__session.add(AuditLog(
                event_type='devolucion_dictaminada', actor=actor,
                entity_type='return_loss_request', entity_id=str(request.id),
                detail=(f'{resolution}: {request.quantity} unidad(es) de '
                        f'{request.product_name}. Ticket {request.transaction_id}.'),
            ))
            self.__session.commit()
        except Exception:
            self.__session.rollback()
            raise
        return request

    def hold_sale(self, label, notes, actor, cart, prices):
        """Guarda un carrito para continuarlo después sin modificar existencias."""
        if not cart:
            raise ValueError('No hay productos en la venta.')
        held = HeldSale(label=label.strip() or 'Venta en espera', notes=notes.strip(), created_by=actor)
        for product_id, quantity in cart.items():
            held.items.append(HeldSaleItem(
                product_id=product_id, quantity=int(quantity),
                unit_price=CUPMoney(f'{float(prices[product_id]):.2f}'),
            ))
        self.__session.add(held)
        self.__session.commit()
        self.audit('venta_suspendida', actor, 'held_sale', held.id, held.label)
        return held

    def get_held_sales(self):
        return list(self.__session.scalars(
            select(HeldSale).order_by(HeldSale.created_at.desc())
        ).unique().all())

    def delete_held_sale(self, held_sale_id):
        held = self.__session.get(HeldSale, held_sale_id)
        if held is not None:
            self.__session.delete(held)
            self.__session.commit()

    def add_customer(self, name, phone='', email='', tax_id='', notes=''):
        require_role('superuser')
        name = (name or '').strip()
        if len(name) < 2:
            raise ValueError('Escribe el nombre del cliente.')
        existing = self.__session.scalar(select(Customer).where(Customer.name.ilike(name)))
        if existing is not None:
            raise ValueError('Ya existe un cliente con ese nombre.')
        customer = Customer(name=name, phone=phone.strip(), email=email.strip(),
                            tax_id=tax_id.strip(), notes=notes.strip())
        self.__session.add(customer)
        self.__session.commit()
        return customer

    def get_customers(self):
        return list(self.__session.scalars(
            select(Customer).where(Customer.is_active == True).order_by(Customer.name)
        ).all())

    def archive_customer(self, customer_id):
        require_role('superuser')
        customer = self.__session.get(Customer, customer_id)
        if customer is not None:
            customer.is_active = False
            self.__session.commit()
