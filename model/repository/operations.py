"""Casos de uso transversales: Kardex, auditoría, clientes y ventas suspendidas."""

import json
from datetime import datetime, time, timedelta

from sqlalchemy import or_, select

from model.entity.models import (AuditLog, Customer, HeldSale, HeldSaleItem,
                                 OperationalIncident, Product, ReturnLossRequest,
                                 Sale, StockMovement)
from model.customer_contact import (
    normalize_country, normalize_email, normalize_phone, normalize_postal_code,
)
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

    def get_audit_logs(self, limit=300, initial_date=None, final_date=None,
                       event_types=None, actors=None, entity_types=None, search=''):
        """Consulta la bitácora sin alterar sus registros.

        Los filtros se aplican en la base de datos para que la auditoría siga siendo
        útil incluso cuando el historial crece durante la operación del negocio.
        """
        statement = select(AuditLog)
        if initial_date is not None:
            statement = statement.where(
                AuditLog.created_at >= datetime.combine(initial_date, time.min))
        if final_date is not None:
            statement = statement.where(
                AuditLog.created_at < datetime.combine(
                    final_date + timedelta(days=1), time.min))
        if event_types:
            statement = statement.where(AuditLog.event_type.in_(event_types))
        if actors:
            statement = statement.where(AuditLog.actor.in_(actors))
        if entity_types:
            statement = statement.where(AuditLog.entity_type.in_(entity_types))
        term = (search or '').strip()
        if term:
            pattern = f'%{term}%'
            statement = statement.where(or_(
                AuditLog.event_type.ilike(pattern), AuditLog.actor.ilike(pattern),
                AuditLog.entity_type.ilike(pattern), AuditLog.entity_id.ilike(pattern),
                AuditLog.detail.ilike(pattern),
            ))
        statement = statement.order_by(AuditLog.created_at.desc()).limit(int(limit))
        return list(self.__session.scalars(statement).all())

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

    def get_incidents(self, status=None, limit=500):
        statement = select(OperationalIncident).order_by(
            OperationalIncident.status.asc(), OperationalIncident.created_at.desc())
        if status:
            statement = statement.where(OperationalIncident.status == status)
        return list(self.__session.scalars(statement.limit(limit)).all())

    def create_incident(self, category, title, detail, priority, actor,
                        responsible='', source_key=''):
        require_role('superuser', 'seller')
        if priority not in ('Crítica', 'Alta', 'Media', 'Informativa'):
            raise ValueError('Selecciona una prioridad válida.')
        if len((title or '').strip()) < 4:
            raise ValueError('Escribe un título de al menos 4 caracteres.')
        incident = OperationalIncident(
            source_key=(source_key or '').strip(), category=(category or 'General').strip(),
            title=title.strip(), detail=(detail or '').strip(), priority=priority,
            responsible=(responsible or '').strip(), created_by=actor or 'Sistema')
        self.__session.add(incident)
        self.__session.flush()
        self.__session.add(AuditLog(
            event_type='incidencia_creada', actor=actor or 'Sistema',
            entity_type='operational_incident', entity_id=str(incident.id),
            detail=f'{priority} · {incident.category} · {incident.title}'))
        self.__session.commit()
        return incident

    def update_incident(self, incident_id, status, responsible, resolution, actor):
        require_role('superuser')
        incident = self.__session.get(OperationalIncident, int(incident_id))
        if incident is None:
            raise ValueError('La incidencia ya no existe.')
        if status not in ('Nueva', 'En revisión', 'Resuelta'):
            raise ValueError('El estado no es válido.')
        if status == 'Resuelta' and len((resolution or '').strip()) < 5:
            raise ValueError('Describe la solución antes de cerrar la incidencia.')
        incident.status = status
        incident.responsible = (responsible or '').strip()
        incident.resolution = (resolution or '').strip()
        incident.updated_at = mexico_now()
        incident.resolved_at = mexico_now() if status == 'Resuelta' else None
        self.__session.add(AuditLog(
            event_type='incidencia_actualizada', actor=actor or 'Administrador',
            entity_type='operational_incident', entity_id=str(incident.id),
            detail=f'{incident.title} · {status} · {incident.responsible or "Sin responsable"}'))
        self.__session.commit()
        return incident

    def ensure_incident(self, source_key, category, title, detail, priority='Alta'):
        """Crea una alerta automática sólo si no hay otra abierta con la misma fuente."""
        incident = self.__session.scalar(select(OperationalIncident).where(
            OperationalIncident.source_key == source_key,
            OperationalIncident.status != 'Resuelta'))
        if incident is not None:
            incident.detail, incident.priority, incident.updated_at = detail, priority, mexico_now()
            self.__session.commit()
            return incident
        incident = OperationalIncident(
            source_key=source_key, category=category, title=title, detail=detail,
            priority=priority, created_by='Sistema')
        self.__session.add(incident); self.__session.commit(); return incident

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

    def hold_sale(self, label, notes, actor, cart, prices, register_id=None,
                  register_name='Caja principal'):
        """Guarda un carrito para continuarlo después sin modificar existencias."""
        if not cart:
            raise ValueError('No hay productos en la venta.')
        held = HeldSale(
            label=label.strip() or 'Venta en espera', notes=notes.strip(),
            created_by=actor, register_id=register_id,
            register_name=(register_name or 'Caja principal').strip(),
        )
        for product_id, quantity in cart.items():
            held.items.append(HeldSaleItem(
                product_id=product_id, quantity=int(quantity),
                unit_price=CUPMoney(f'{float(prices[product_id]):.2f}'),
            ))
        self.__session.add(held)
        self.__session.commit()
        self.audit('venta_suspendida', actor, 'held_sale', held.id, held.label)
        return held

    def get_held_sales(self, register_id):
        """Devuelve únicamente las ventas suspendidas de la caja indicada."""
        return list(self.__session.scalars(
            select(HeldSale).where(HeldSale.register_id == register_id)
            .order_by(HeldSale.created_at.desc())
        ).unique().all())

    def delete_held_sale(self, held_sale_id, register_id):
        """Elimina una espera sólo si pertenece a la caja activa."""
        held = self.__session.scalar(select(HeldSale).where(
            HeldSale.id == held_sale_id, HeldSale.register_id == register_id))
        if held is None:
            return False
        self.__session.delete(held)
        self.__session.commit()
        return True

    @staticmethod
    def _validated_customer_data(name, phone, address, email='', tax_id='', notes='',
                                 phone_country='MX', postal_code=''):
        name = (name or '').strip()
        address = (address or '').strip()
        if len(name) < 2:
            raise ValueError('Escribe el nombre completo del cliente.')
        if len(name) > 120:
            raise ValueError('El nombre del cliente no puede superar 120 caracteres.')
        if len(address) < 5:
            raise ValueError('Captura la dirección completa del cliente.')
        if len(address) > 300:
            raise ValueError('La dirección no puede superar 300 caracteres.')
        phone_country = normalize_country(phone_country)
        phone = normalize_phone(phone, phone_country)
        email = normalize_email(email)
        postal_code = normalize_postal_code(postal_code, phone_country)
        tax_id = (tax_id or '').strip().upper()
        notes = (notes or '').strip()
        if len(tax_id) > 40:
            raise ValueError('El RFC o identificación no puede superar 40 caracteres.')
        if len(notes) > 400:
            raise ValueError('Las notas no pueden superar 400 caracteres.')
        return {
            'name': name, 'phone': phone, 'phone_country': phone_country,
            'address': address, 'postal_code': postal_code, 'email': email,
            'tax_id': tax_id, 'notes': notes,
        }

    def add_customer(self, name, phone='', email='', tax_id='', notes='', address='',
                     phone_country='MX', postal_code=''):
        require_role('superuser', 'seller')
        data = self._validated_customer_data(
            name, phone, address, email, tax_id, notes, phone_country, postal_code)
        existing = self.__session.scalar(
            select(Customer).where(Customer.name.ilike(data['name'])))
        if existing is not None:
            raise ValueError('Ya existe un cliente con ese nombre.')
        customer = Customer(**data, updated_at=mexico_now())
        self.__session.add(customer)
        self.__session.commit()
        return customer

    def update_customer(self, customer_id, name, phone, address, email='', tax_id='',
                        notes='', actor='Administrador', phone_country='MX', postal_code=''):
        require_role('superuser', 'seller')
        customer = self.__session.get(Customer, int(customer_id))
        if customer is None or not customer.is_active:
            raise ValueError('El cliente ya no está disponible.')
        data = self._validated_customer_data(
            name, phone, address, email, tax_id, notes, phone_country, postal_code)
        duplicate = self.__session.scalar(select(Customer).where(
            Customer.name.ilike(data['name']), Customer.id != customer.id))
        if duplicate is not None:
            raise ValueError('Ya existe otro cliente con ese nombre.')
        for field, value in data.items():
            setattr(customer, field, value)
        customer.updated_at = mexico_now()
        self.__session.add(AuditLog(
            event_type='cliente_actualizado', actor=(actor or 'Sistema').strip(),
            entity_type='customer', entity_id=str(customer.id),
            detail=f'Datos de contacto actualizados para {customer.name}.'))
        self.__session.commit()
        return customer

    def get_customers(self):
        return list(self.__session.scalars(
            select(Customer).where(Customer.is_active == True).order_by(Customer.name)
        ).all())

    def search_customers(self, term='', limit=20):
        """Filtra el directorio activo para autocompletado sin cargar historiales."""
        clean_term = (term or '').strip()
        statement = select(Customer).where(Customer.is_active == True)
        if clean_term:
            pattern = f'%{clean_term}%'
            statement = statement.where(or_(
                Customer.name.ilike(pattern), Customer.phone.ilike(pattern),
                Customer.email.ilike(pattern), Customer.address.ilike(pattern),
                Customer.postal_code.ilike(pattern), Customer.tax_id.ilike(pattern),
            ))
        return list(self.__session.scalars(
            statement.order_by(Customer.name).limit(max(1, min(int(limit), 50)))
        ).all())

    def archive_customer(self, customer_id):
        require_role('superuser')
        customer = self.__session.get(Customer, customer_id)
        if customer is not None:
            customer.is_active = False
            self.__session.commit()

    def record_customer_purchase(self, customer_name, amount, transaction_id, actor):
        """Acumula un punto por cada $10 completos; no crea perfiles para público general."""
        name = (customer_name or '').strip()
        if not name or name.casefold() in ('público general', 'publico general'):
            return 0
        customer = self.__session.scalar(select(Customer).where(Customer.name.ilike(name)))
        if customer is None:
            return 0
        value = max(0.0, round(float(amount), 2))
        earned = int(value // 10)
        customer.loyalty_points = int(customer.loyalty_points or 0) + earned
        customer.lifetime_spend = CUPMoney(
            f'{float(customer.lifetime_spend.amount if customer.lifetime_spend else 0)+value:.2f}')
        self.__session.add(AuditLog(
            event_type='puntos_cliente_acumulados', actor=actor,
            entity_type='customer', entity_id=str(customer.id),
            detail=f'{transaction_id} · +{earned} punto(s) · compra ${value:.2f}'))
        self.__session.commit()
        return earned

    def adjust_customer_points(self, customer_id, delta, reason, actor):
        require_role('superuser')
        customer = self.__session.get(Customer, int(customer_id))
        if customer is None: raise ValueError('El cliente ya no existe.')
        resulting = int(customer.loyalty_points or 0) + int(delta)
        if resulting < 0: raise ValueError('El ajuste dejaría un saldo negativo.')
        if len((reason or '').strip()) < 4: raise ValueError('Indica el motivo del ajuste.')
        customer.loyalty_points = resulting
        self.__session.add(AuditLog(event_type='puntos_cliente_ajustados', actor=actor,
            entity_type='customer', entity_id=str(customer.id),
            detail=f'{int(delta):+d} punto(s) · saldo {resulting} · {reason.strip()}'))
        self.__session.commit(); return customer
