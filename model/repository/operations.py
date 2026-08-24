from sqlalchemy import select

from model.entity.models import AuditLog, Customer, HeldSale, HeldSaleItem, Product, StockMovement
from model.util.monetary_types import CUPMoney


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

    def adjust_stock(self, product_id, delta, movement_type, reason, actor, reference=''):
        product = self.__session.scalar(select(Product).where(Product.id == product_id))
        if product is None:
            raise ValueError('El producto ya no existe.')
        previous = product.quantity
        resulting = previous + int(delta)
        if resulting < 0:
            raise ValueError('El ajuste dejaría existencias negativas.')
        product.quantity = resulting
        self.__session.add(StockMovement(
            product_id=product.id, movement_type=movement_type, quantity=int(delta),
            previous_stock=previous, resulting_stock=resulting, reason=reason,
            reference=reference, performed_by=actor,
        ))
        self.__session.add(AuditLog(
            event_type='inventario_ajustado', actor=actor, entity_type='product',
            entity_id=str(product.id),
            detail=f'{movement_type}: {delta:+d}. {previous} → {resulting}. {reason}',
        ))
        self.__session.commit()
        return product

    def get_stock_movements(self, limit=500):
        return list(self.__session.scalars(
            select(StockMovement).order_by(StockMovement.created_at.desc()).limit(limit)
        ).all())

    def hold_sale(self, label, notes, actor, cart, prices):
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
        customer = self.__session.get(Customer, customer_id)
        if customer is not None:
            customer.is_active = False
            self.__session.commit()
