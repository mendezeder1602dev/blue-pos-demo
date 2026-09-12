"""Órdenes de compra locales y recepción de inventario."""
from sqlalchemy import select
from model.authorization import require_role
from model.entity.models import AuditLog, Product, PurchaseOrder, PurchaseOrderItem, StockMovement
from model.timezone import mexico_now
from model.util.monetary_types import CUPMoney


class PurchaseOrderRepository:
    def __init__(self, session): self._session = session
    def create(self, supplier, items, expected_date, notes, actor):
        require_role('superuser')
        supplier = (supplier or '').strip()
        if not supplier: raise ValueError('Indica el proveedor.')
        if not items: raise ValueError('La orden no contiene productos.')
        order = PurchaseOrder(supplier=supplier, expected_date=expected_date,
                              notes=(notes or '').strip(), created_by=actor,
                              total=CUPMoney('0.00'))
        total = 0.0
        for item in items:
            product = self._session.get(Product, int(item['product_id']))
            quantity, cost = int(item['quantity']), round(float(item['unit_cost']), 2)
            if product is None or quantity <= 0 or cost < 0:
                raise ValueError('La orden contiene un producto, cantidad o costo inválido.')
            order.items.append(PurchaseOrderItem(product_id=product.id,
                product_name=product.name, quantity=quantity,
                unit_cost=CUPMoney(f'{cost:.2f}')))
            total += quantity * cost
        order.total = CUPMoney(f'{total:.2f}')
        self._session.add(order); self._session.flush()
        self._session.add(AuditLog(event_type='orden_compra_creada', actor=actor,
            entity_type='purchase_order', entity_id=str(order.id),
            detail=f'{supplier} · {len(order.items)} producto(s) · ${total:.2f}'))
        self._session.commit(); return order
    def list(self, status=None):
        statement = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
        if status: statement = statement.where(PurchaseOrder.status == status)
        return list(self._session.scalars(statement).unique().all())
    def receive(self, order_id, actor):
        require_role('superuser')
        order = self._session.get(PurchaseOrder, int(order_id))
        if order is None or order.status != 'Pendiente': raise ValueError('La orden ya no está pendiente.')
        try:
            for item in order.items:
                product = self._session.get(Product, item.product_id)
                if product is None: raise ValueError(f'Ya no existe {item.product_name}.')
                previous, incoming = product.quantity, item.quantity
                old_cost, new_cost = float(product.cost.amount), float(item.unit_cost.amount)
                resulting = previous + incoming
                product.quantity = resulting
                if resulting > 0: product.cost = CUPMoney(f'{((previous*old_cost)+(incoming*new_cost))/resulting:.2f}')
                self._session.add(StockMovement(product_id=product.id,
                    movement_type='Compra recibida', quantity=incoming,
                    previous_stock=previous, resulting_stock=resulting,
                    reason=f'Orden de compra #{order.id}', reference=str(order.id),
                    performed_by=actor))
            order.status, order.received_at = 'Recibida', mexico_now()
            self._session.add(AuditLog(event_type='orden_compra_recibida', actor=actor,
                entity_type='purchase_order', entity_id=str(order.id),
                detail=f'{order.supplier} · ${float(order.total.amount):.2f}'))
            self._session.commit(); return order
        except Exception: self._session.rollback(); raise
