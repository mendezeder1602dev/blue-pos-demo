"""Persistencia transaccional de tickets, devoluciones y existencias vendidas."""

import json
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import update, select, delete, cast, Numeric, asc, desc, Float, func

from model.entity.models import Product, ReturnLossRequest, Sale, StockMovement
from sqlalchemy.orm import Session, aliased

from model.repository.exc.product import NonExistentProductException, NoPositivePriceException, NegativeCostException
from model.repository.exc.sale import NoEnoughProductQuantityException, NonExistentSaleException, \
    ChangeProductIdInSaleException
from model.repository.observer import RepositoryObserver
from model.util.monetary_types import CUPMoney
from model.authorization import require_role
from model.timezone import mexico_now


class SaleFilter:

    ID = 'id'
    PRODUCT_ID = 'product_id'
    SALE_DATE = 'sale_date'
    PRICE = 'price'
    COST = 'cost'
    PROFIT = 'profit'

    def __init__(self):
        self.__product_id_list = None
        self.__minimum_date = None
        self.__maximum_date = None
        self.__sale_id_list = None
        self.__sorted_by = None
        self.__ascending_order = True

    @property
    def sale_id_list(self):
        return self.__sale_id_list

    @sale_id_list.setter
    def sale_id_list(self, value: list):
        self.__sale_id_list = value

    @property
    def product_id_list(self) -> list:
        return self.__product_id_list

    @product_id_list.setter
    def product_id_list(self, value: list):
        self.__product_id_list = value

    @property
    def minimum_date(self) -> date:
        return self.__minimum_date

    @minimum_date.setter
    def minimum_date(self, value: date):
        self.__minimum_date = value

    @property
    def maximum_date(self) -> date:
        return self.__maximum_date

    @maximum_date.setter
    def maximum_date(self, value: date):
        self.__maximum_date = value

    @property
    def sorted_by(self) -> str:
        return self.__sorted_by

    @sorted_by.setter
    def sorted_by(self, value: str):
        self.__sorted_by = value

    @property
    def ascending_order(self) -> bool:
        return self.__ascending_order

    @ascending_order.setter
    def ascending_order(self, value: bool):
        self.__ascending_order = value


class SaleRepository(RepositoryObserver):

    def __init__(self, session: Session):
        super().__init__()
        self.__session = session

    def insert_sales(self, sale: Sale, quantity: int) -> list:
        self.__check_quantity_is_positive(quantity)
        self.__check_price_is_positive(sale)
        self.__check_cost_is_not_negative(sale)
        self.__check_product_exists(sale)
        self.__check_there_are_enough_products(sale, quantity)

        sales = self.__execute_insertion_and_return_sales(sale, quantity)
        self.__execute_product_quantity_update(sale, quantity)
        self.__session.commit()
        self._notify_on_data_changed_listeners()
        return sales

    def insert_transaction(self, entries: list) -> list:
        """Registra todos los renglones de un cobro como una operación atómica."""
        if not entries:
            raise ValueError('A transaction must contain at least one product.')
        transaction_id = uuid4().hex
        requested_by_product = {}
        for sale, quantity in entries:
            self.__check_quantity_is_positive(quantity)
            self.__check_price_is_positive(sale)
            self.__check_cost_is_not_negative(sale)
            self.__check_product_exists(sale)
            requested_by_product[sale.product_id] = requested_by_product.get(sale.product_id, 0) + quantity
        for product_id, quantity in requested_by_product.items():
            product = self.__get_product_by_id(product_id)
            if product.quantity < quantity:
                raise NoEnoughProductQuantityException(product.quantity)
        inserted_sales = []
        try:
            for sale, quantity in entries:
                sale.transaction_id = transaction_id
                inserted_sales.extend(self.__execute_insertion_and_return_sales(sale, quantity))
                result = self.__session.execute(
                    update(Product).where(
                        Product.id == sale.product_id,
                        Product.quantity >= quantity,
                    ).values(quantity=Product.quantity - quantity)
                )
                if result.rowcount != 1:
                    raise NoEnoughProductQuantityException(0)
            self.__session.commit()
        except Exception:
            self.__session.rollback()
            raise
        self._notify_on_data_changed_listeners()
        return inserted_sales
    def __check_quantity_is_positive(self, quantity: int):
        if quantity <= 0:
            raise ValueError('The quantity of sales must be positive.')

    def __check_price_is_positive(self, sale: Sale):
        if not sale.price > CUPMoney('0.00'):
            raise NoPositivePriceException()

    @staticmethod
    def __check_cost_is_not_negative(sale: Sale):
        if sale.cost < CUPMoney('0.00'):
            raise NegativeCostException(sale.cost)

    def __get_product_by_id(self, product_id: int) -> Product:
        return self.__session.scalar(select(Product).where(Product.id == product_id))

    def __check_product_exists(self, sale: Sale):
        read_product = self.__get_product_by_id(sale.product_id)
        if read_product is None:
            nonexistent_product = Product()
            nonexistent_product.id = sale.product_id
            raise NonExistentProductException(nonexistent_product)

    def __check_there_are_enough_products(self, sale: Sale, quantity_of_sales):
        read_product = self.__get_product_by_id(sale.product_id)
        if read_product.quantity - quantity_of_sales < 0:
            raise NoEnoughProductQuantityException(read_product.quantity)

    def __execute_insertion_and_return_sales(self, sale: Sale, quantity: int) -> list:
        sales = []
        for i in range(quantity):
            a_sale = Sale(
                product_id=sale.product_id,
                date=sale.date,
                price=sale.price,
                cost=sale.cost,
                payment_method=getattr(sale, 'payment_method', 'cash'),
                payment_details=getattr(sale, 'payment_details', ''),
                transaction_id=getattr(sale, 'transaction_id', None),
                product_name=getattr(sale, 'product_name', ''),
                cashier=getattr(sale, 'cashier', 'Vendedor'),
                status=getattr(sale, 'status', 'Completada'),
                customer=getattr(sale, 'customer', 'Público general'),
            )
            sales.append(a_sale)
        self.__session.add_all(sales)
        return sales

    def __execute_product_quantity_update(self, sale: Sale, sale_quantity: int):
        product = self.__session.scalar(select(Product).where(Product.id == sale.product_id))

        self.__session.execute(
            update(Product)
            .where(Product.id == sale.product_id)
            .values(quantity=product.quantity - sale_quantity)
        )

    def delete_sale(self, sale_to_delete: Sale):
        self.__check_sale_exists(sale_to_delete)
        self.__check_product_exists(sale_to_delete)
        self.__increase_product_quantity(sale_to_delete)

        self.__session.execute(
            delete(Sale)
            .where(Sale.id == sale_to_delete.id)
        )
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def delete_sales(self, sale_id_list: list):
        if not sale_id_list:
            return
        self.__check_sales_exists(sale_id_list)
        self.__increase_quantity_of_associated_products(sale_id_list)

        self.__execute_sale_deletion(sale_id_list)
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def reverse_transaction(self, transaction_id: str, reason: str, actor: str):
        require_role('superuser')
        """Anula una operación conservando evidencia y restaura existencias una sola vez."""
        reason = (reason or '').strip()
        if len(reason) < 5:
            raise ValueError('Escribe un motivo de al menos 5 caracteres.')
        sales = list(self.__session.scalars(
            select(Sale).where(Sale.transaction_id == transaction_id)
        ).all())
        if not sales:
            raise ValueError('La venta ya no existe.')
        if any(sale.status == 'Anulada' for sale in sales):
            raise ValueError('La venta ya fue anulada.')
        restored = {}
        for sale in sales:
            restored[sale.product_id] = restored.get(sale.product_id, 0) + 1
            sale.status = 'Anulada'
            sale.reversal_reason = reason
            sale.reversed_at = mexico_now()
        for product_id, quantity in restored.items():
            self.__session.execute(update(Product).where(Product.id == product_id).values(
                quantity=Product.quantity + quantity
            ))
        self.__session.commit()
        self._notify_on_data_changed_listeners()
        return sales

    def return_items(self, transaction_id: str, return_plan: list, reason: str,
                     refund_method: str, actor: str = 'Administrador'):
        require_role('superuser')
        """Devuelve unidades elegidas y concilia su destino físico de forma atómica."""
        reason = (reason or '').strip()
        if len(reason) < 5:
            raise ValueError('Escribe un motivo de devolución de al menos 5 caracteres.')
        if refund_method not in ('Efectivo', 'Tarjeta', 'Transferencia', 'Vale'):
            raise ValueError('Selecciona un método de reembolso válido.')

        allowed_dispositions = ('Reintegrar a inventario', 'Enviar a revisión de merma')
        selected = []
        groups = []
        seen_ids = set()
        for group in return_plan or []:
            disposition = group.get('disposition')
            if disposition not in allowed_dispositions:
                raise ValueError('Selecciona un destino válido para cada producto.')
            for raw_sale_id in group.get('sale_ids', []):
                sale_id = int(raw_sale_id)
                if sale_id in seen_ids:
                    raise ValueError('La selección contiene unidades duplicadas.')
                seen_ids.add(sale_id)
                selected.append((sale_id, disposition))
            groups.append(group)
        if not selected:
            raise ValueError('Selecciona al menos una unidad para devolver.')

        sales_by_id = {
            sale.id: sale for sale in self.__session.scalars(
                select(Sale).where(Sale.id.in_(seen_ids))
            ).all()
        }
        if len(sales_by_id) != len(seen_ids):
            raise ValueError('Una de las unidades seleccionadas ya no existe.')
        if any(sales_by_id[sale_id].transaction_id != transaction_id
               or sales_by_id[sale_id].status != 'Completada'
               for sale_id, _ in selected):
            raise ValueError('El ticket cambió o alguna unidad ya fue devuelta o anulada.')

        now = mexico_now()
        restored = {}
        try:
            for sale_id, disposition in selected:
                sale = sales_by_id[sale_id]
                sale.status = 'Devuelta'
                sale.returned_at = now
                sale.return_reason = reason
                sale.refund_method = refund_method
                sale.return_disposition = disposition
                if disposition == 'Reintegrar a inventario':
                    restored[sale.product_id] = restored.get(sale.product_id, 0) + 1

            for product_id, quantity in restored.items():
                product = self.__session.scalar(select(Product).where(Product.id == product_id))
                if product is None:
                    raise ValueError('Uno de los productos ya no existe en el inventario.')
                previous_stock = product.quantity
                product.quantity += quantity
                self.__session.add(StockMovement(
                    product_id=product_id, movement_type='Devolución', quantity=quantity,
                    previous_stock=previous_stock, resulting_stock=product.quantity,
                    reason=f'Reintegración por devolución: {reason}',
                    reference=transaction_id, performed_by=actor,
                ))
            for group in groups:
                if group.get('disposition') != 'Enviar a revisión de merma':
                    continue
                group_sale_ids = [int(sale_id) for sale_id in group.get('sale_ids', [])]
                if not group_sale_ids:
                    continue
                sample_sale = sales_by_id[group_sale_ids[0]]
                self.__session.add(ReturnLossRequest(
                    transaction_id=transaction_id,
                    product_id=sample_sale.product_id,
                    product_name=(sample_sale.product_name
                                  or group.get('product_name')
                                  or f'Producto #{sample_sale.product_id}'),
                    quantity=len(group_sale_ids),
                    sale_ids=json.dumps(group_sale_ids),
                    concept=str(group.get('concept') or 'Producto no apto para venta'),
                    reason=reason,
                    requested_by=actor,
                ))
            self.__session.commit()
        except Exception:
            self.__session.rollback()
            raise
        self._notify_on_data_changed_listeners()
        return [sales_by_id[sale_id] for sale_id, _ in selected]

    def return_transaction(self, transaction_id: str, reason: str, refund_method: str):
        """Compatibilidad: devuelve todo el ticket y reintegra sus existencias."""
        sales = list(self.__session.scalars(
            select(Sale).where(
                Sale.transaction_id == transaction_id,
                Sale.status == 'Completada',
            )
        ).all())
        return self.return_items(transaction_id, [{
            'sale_ids': [sale.id for sale in sales],
            'disposition': 'Reintegrar a inventario',
        }], reason, refund_method)

    def __check_sales_exists(self, sale_id_list: list):
        found_ids = set(self.__session.scalars(
            select(Sale.id).where(Sale.id.in_(sale_id_list))
        ).all())
        for sale_id in sale_id_list:
            if sale_id not in found_ids:
                raise NonExistentSaleException(Sale(id=sale_id))

    def __increase_quantity_of_associated_products(self, sale_id_list: list):
        restored_by_product = self.__session.execute(
            select(Sale.product_id, func.count(Sale.id))
            .where(Sale.id.in_(sale_id_list))
            .group_by(Sale.product_id)
        ).all()
        for product_id, restored_quantity in restored_by_product:
            self.__session.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(quantity=Product.quantity + restored_quantity)
            )

    def __execute_sale_deletion(self, sale_id_list: list):
        self.__session.execute(delete(Sale)
                               .where(Sale.id.in_(sale_id_list)))

    def __get_sale_by_id(self, sale_id: int):
        return self.__session.scalar(select(Sale).where(Sale.id == sale_id))

    def __check_sale_exists(self, a_sale):
        read_sale = self.__get_sale_by_id(a_sale.id)
        if read_sale is None:
            raise NonExistentSaleException(a_sale)

    def __increase_product_quantity(self, sale: Sale):
        product = self.__get_product_by_id(sale.product_id)

        self.__session.execute(
            update(Product)
            .where(Product.id == sale.product_id)
            .values(quantity=product.quantity + 1)
        )

    def update_sale(self, sale: Sale):
        self.__check_price_is_positive(sale)
        self.__check_cost_is_not_negative(sale)
        self.__check_sale_exists(sale)
        self.__check_product_id_is_not_changed_in_sale(sale)

        self.__execute_update_operation(sale)
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def __check_product_id_is_not_changed_in_sale(self, sale: Sale):
        read_sale = self.__get_sale_by_id(sale.id)
        if read_sale.product_id != sale.product_id:
            raise ChangeProductIdInSaleException()

    def __execute_update_operation(self, sale: Sale):
        self.__session.execute(
            update(Sale)
                .where(Sale.id == sale.id)
                .values(
                date=sale.date,
                price=sale.price,
                cost=sale.cost
            )
        )

    def get_all_sales(self) -> list:
        return self.__session.scalars(select(Sale).where(Sale.status == 'Completada')).all()

    def get_sales_by_filter(self, the_filter: SaleFilter) -> list:
        filter_query = SaleRepository.__create_filter_query(the_filter)
        return self.__session.scalars(filter_query).all()

    @staticmethod
    def __create_filter_query(the_filter: SaleFilter):
        query = select(Sale, ).where(Sale.status == 'Completada')

        if the_filter.minimum_date is not None:
            query = query.where(Sale.date >= the_filter.minimum_date)
        if the_filter.maximum_date is not None:
            query = query.where(Sale.date <= the_filter.maximum_date)

        if the_filter.product_id_list is not None:
            query = query.where(Sale.product_id.in_(the_filter.product_id_list))

        if the_filter.sale_id_list is not None:
            query = query.where(Sale.id.in_(the_filter.sale_id_list))

        query = SaleRepository.__add_order_by_clause(query, the_filter)

        return query

    @staticmethod
    def __add_order_by_clause(query, the_filter: SaleFilter):
        if the_filter.sorted_by is None:
            return query

        column = None
        is_money_column = False

        if the_filter.sorted_by == SaleFilter.ID:
            column = Sale.id
        elif the_filter.sorted_by == SaleFilter.PRODUCT_ID:
            column = Sale.product_id
        elif the_filter.sorted_by == SaleFilter.SALE_DATE:
            column = Sale.date
        elif the_filter.sorted_by == SaleFilter.PRODUCT_ID:
            column = Sale.product_id
        elif the_filter.sorted_by == SaleFilter.PRICE:
            column = Sale.price
            is_money_column = True
        elif the_filter.sorted_by == SaleFilter.COST:
            column = Sale.cost
            is_money_column = True
        elif the_filter.sorted_by == SaleFilter.PROFIT:
            column = cast(Sale.price, Float) - cast(Sale.cost, Float)
            query = query.add_columns(column)

        if is_money_column:
            if the_filter.ascending_order:
                return query.order_by(asc(cast(column, Numeric)))
            return query.order_by(desc(cast(column, Numeric)))

        if the_filter.ascending_order:
            column = column.asc()
        else:
            column = column.desc()

        return query.order_by(column)
