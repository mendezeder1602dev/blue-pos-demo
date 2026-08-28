"""Persistencia y reglas de integridad del inventario de productos."""

from sqlalchemy.orm import Session
from model.entity.models import AuditLog, Product, Sale, StockMovement
from sqlalchemy import select, delete, update, cast, Float

from model.repository.exc.product import UniqueProductNameException, NonExistentProductException, \
    InvalidProductQuantityException, NoPositivePriceException, EmptyProductNameException, NegativeCostException, UniqueProductBarcodeException
from model.repository.observer import RepositoryObserver
from model.util.monetary_types import CUPMoney
from model.authorization import require_role


class ProductFilter:

    def __init__(self):
        self.id = None
        self.name = None
        self.description = None
        self.__less_than_price = None
        self.__more_than_price = None
        self.__less_than_profit = None
        self.__more_than_profit = None
        self.__less_than_quantity = None
        self.__more_than_quantity = None

    @property
    def less_than_price(self):
        return self.__less_than_price

    @less_than_price.setter
    def less_than_price(self, value: CUPMoney):
        self.__check_price_correctness(value)
        self.__less_than_price = value

    def __check_price_correctness(self, value: CUPMoney):
        if value is not None and value <= CUPMoney('0'):
            raise NoPositivePriceException()

    @property
    def more_than_price(self):
        return self.__more_than_price

    @more_than_price.setter
    def more_than_price(self, value: CUPMoney):
        self.__check_price_correctness(value)
        self.__more_than_price = value

    @property
    def less_than_profit(self):
        return self.__less_than_profit

    @less_than_profit.setter
    def less_than_profit(self, value: CUPMoney):
        self.__less_than_profit = value

    @property
    def more_than_profit(self):
        return self.__more_than_profit

    @more_than_profit.setter
    def more_than_profit(self, value: CUPMoney):
        self.__more_than_profit = value

    @property
    def less_than_quantity(self):
        return self.__less_than_quantity

    @less_than_quantity.setter
    def less_than_quantity(self, value: int):
        self.__check_quantity_correctness(value)
        self.__less_than_quantity = value

    def __check_quantity_correctness(self, value: int):
        if value is not None and value < 0:
            raise InvalidProductQuantityException()

    @property
    def more_than_quantity(self):
        return self.__more_than_quantity

    @more_than_quantity.setter
    def more_than_quantity(self, value: int):
        self.__check_quantity_correctness(value)
        self.__more_than_quantity = value


class ProductRepository(RepositoryObserver):
    """Valida duplicados, precios y existencias antes de confirmar cambios."""

    def __init__(self, session: Session):
        super().__init__()
        self.__session = session

    def insert_product(self, product: Product):
        product.name = self.__normalize_name(product.name)
        self.__check_name_is_not_empty_or_whitespaces(product.name)
        self.__check_correctness_of_quantity(product)
        self.__check_correctness_of_price(product)
        self.__check_correctness_of_cost(product)
        self.__check_name_is_not_used(product)
        self.__check_barcode_can_be_used(product)

        self.__session.add(product)
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    @staticmethod
    def __check_name_is_not_empty_or_whitespaces(name: str):
        if not name or not name.strip():
            raise EmptyProductNameException()

    @staticmethod
    def __check_correctness_of_quantity(product: Product):
        if product.quantity < 0:
            raise InvalidProductQuantityException()

    @staticmethod
    def __check_correctness_of_price(product: Product):
        if product.price <= CUPMoney('0.00'):
            raise NoPositivePriceException()

    @staticmethod
    def __check_correctness_of_cost(product: Product):
        if product.cost < CUPMoney('0.00'):
            raise NegativeCostException(product.cost)

    def __check_name_is_not_used(self, product: Product):
        found_product = self.__find_product_by_name(product.name)
        if found_product is not None:
            raise UniqueProductNameException(found_product.name)

    def __find_product_by_name(self, name: str) -> Product:
        normalized_name = self.__normalize_name(name).casefold()
        return next((existing for existing in self.__session.scalars(select(Product)).all()
                     if self.__normalize_name(existing.name).casefold() == normalized_name), None)

    @staticmethod
    def __normalize_name(name: str) -> str:
        return ' '.join((name or '').split())

    def get_product_by_barcode(self, barcode: str) -> Product:
        return self.__session.scalar(select(Product).where(Product.barcode == barcode.strip()))

    def __check_barcode_can_be_used(self, product: Product):
        barcode = (product.barcode or '').strip()
        product.barcode = barcode
        if not barcode:
            return
        found_product = self.get_product_by_barcode(barcode)
        if found_product is not None and found_product.id != product.id:
            raise UniqueProductBarcodeException(barcode, found_product.name)

    def delete_product(self, product: Product):
        require_role('superuser')
        found_product = self.__check_product_exists(product)
        self.__session.delete(found_product)
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def archive_product(self, product: Product):
        """Baja segura usada por el POS: oculta el producto y conserva sus ventas."""
        require_role('superuser')
        found_product = self.__check_product_exists(product)
        found_product.is_active = False
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def import_inventory(self, plans, actor):
        """Crea o actualiza un lote completo; cualquier error revierte toda la importación."""
        require_role('superuser')
        created = updated = added_units = 0
        try:
            for item in plans:
                existing_id = item.get('existing_id')
                if existing_id is None:
                    product = Product(
                        name=item['name'], description=item['description'],
                        price=CUPMoney(f"{item['price']:.2f}"),
                        cost=CUPMoney(f"{item['cost']:.2f}"), quantity=item['quantity'],
                        barcode=item['barcode'], category=item['category'],
                        supplier=item['supplier'], minimum_stock=item['minimum_stock'])
                    self.__check_name_is_not_used(product)
                    self.__check_barcode_can_be_used(product)
                    self.__session.add(product)
                    created += 1
                    added_units += item['quantity']
                    continue

                product = self.__session.get(Product, existing_id)
                if product is None or not product.is_active:
                    raise ValueError(f'El producto “{item["name"]}” ya no está disponible.')
                previous_stock = product.quantity
                if item['action'] == 'Actualizar y sumar existencias':
                    resulting_stock = previous_stock + item['quantity']
                elif item['action'] == 'Actualizar y reemplazar existencias':
                    resulting_stock = item['quantity']
                else:
                    raise ValueError(f'Acción no válida para “{item["name"]}”.')

                product.name = item['name']
                product.description = item['description']
                product.price = CUPMoney(f"{item['price']:.2f}")
                product.cost = CUPMoney(f"{item['cost']:.2f}")
                product.quantity = resulting_stock
                product.barcode = item['barcode']
                product.category = item['category']
                product.supplier = item['supplier']
                product.minimum_stock = item['minimum_stock']
                delta = resulting_stock - previous_stock
                if delta:
                    self.__session.add(StockMovement(
                        product_id=product.id, movement_type='Importación Excel', quantity=delta,
                        previous_stock=previous_stock, resulting_stock=resulting_stock,
                        reason='Carga masiva de inventario validada por administrador',
                        reference='Excel', performed_by=actor))
                updated += 1
                added_units += delta

            self.__session.flush()
            self.__session.add(AuditLog(
                event_type='inventario_importado', actor=actor, entity_type='inventory',
                detail=(f'Importación Excel: {created} nuevos, {updated} actualizados, '
                        f'variación neta {added_units:+d} unidades.'),
            ))
            self.__session.commit()
        except Exception:
            self.__session.rollback()
            raise
        self._notify_on_data_changed_listeners()
        return {'created': created, 'updated': updated, 'unit_delta': added_units}

    def __check_product_exists(self, product) -> Product:
        found_product = self.__find_product_by_id(product.id)
        if found_product is None:
            raise NonExistentProductException(product)
        return found_product

    def __find_product_by_id(self, product_id: int) -> Product:
        return self.__session.scalars(
            select(Product).where(Product.id == product_id)
        ).first()

    def delete_products(self, product_id_list: list):
        require_role('superuser')
        if not product_id_list:
            return
        self.__check_product_ids_exist(product_id_list)

        self.__execute_sale_deletion_by_product_ids(product_id_list)
        self.__execute_product_deletion_by_id(product_id_list)
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def __check_product_ids_exist(self, product_id_list: list):
        found_ids = set(self.__session.scalars(
            select(Product.id).where(Product.id.in_(product_id_list))
        ).all())
        for product_id in product_id_list:
            if product_id not in found_ids:
                raise NonExistentProductException(Product(id=product_id))

    def __execute_sale_deletion_by_product_ids(self, product_id_list: list):
        self.__session.execute(
            delete(Sale)
            .where(Sale.product_id.in_(product_id_list))
        )

    def __execute_product_deletion_by_id(self, product_id_list: list):
        self.__session.execute(delete(Product)
                               .where(Product.id.in_(product_id_list)))

    def update_product(self, new: Product):
        require_role('superuser')
        new.name = self.__normalize_name(new.name)
        self.__check_name_is_not_empty_or_whitespaces(new.name)
        self.__check_correctness_of_quantity(new)
        self.__check_correctness_of_price(new)
        self.__check_correctness_of_cost(new)
        old = self.__check_product_exists(new)
        self.__check_name_can_be_used(old, new)
        self.__check_barcode_can_be_used(new)

        old.name = new.name
        old.description = new.description
        old.price = new.price
        old.cost = new.cost
        old.quantity = new.quantity
        old.barcode = new.barcode
        old.image_path = new.image_path if new.image_path is not None else old.image_path
        old.category = new.category if new.category is not None else old.category
        old.supplier = new.supplier if new.supplier is not None else old.supplier
        old.minimum_stock = (new.minimum_stock if new.minimum_stock is not None
                             else old.minimum_stock)
        old.is_active = new.is_active if new.is_active is not None else old.is_active

        self.__session.flush()
        self.__session.commit()
        self._notify_on_data_changed_listeners()

    def __check_name_can_be_used(self, old: Product, new: Product):
        found_product = self.__find_product_by_name(new.name)
        if found_product is not None and found_product.id != old.id:
            raise UniqueProductNameException(new.name)

    def get_all_products(self) -> list:
        return self.__session.scalars(select(Product).where(
            Product.is_temporary == False, Product.is_active == True)).all()

    def get_products_by_filter(self, the_filter: ProductFilter) -> list:
        filter_query = self.__create_filter_query(the_filter)
        return self.__session.scalars(filter_query).all()

    def __create_filter_query(self, the_filter: ProductFilter):
        query = select(Product).where(Product.is_active == True)
        if the_filter.id is not None:
            query = query.where(Product.id == the_filter.id)

        if the_filter.name is not None:
            query = query.where(Product.name.ilike('%{}%'.format(the_filter.name)))

        if the_filter.description is not None:
            query = query.where(Product.description.ilike('%{}%'.format(the_filter.description)))

        if the_filter.more_than_price is not None:
            query = query.where(Product.price >= the_filter.more_than_price)
        if the_filter.less_than_price is not None:
            query = query.where(Product.price <= the_filter.less_than_price)

        if the_filter.more_than_profit is not None:
            more_than_profit = float(the_filter.more_than_profit.amount)
            query = query.where(cast(Product.price, Float) - cast(Product.cost, Float) >= more_than_profit)
        if the_filter.less_than_profit is not None:
            less_than_profit = float(the_filter.less_than_profit.amount)
            query = query.where(cast(Product.price, Float) - cast(Product.cost, Float) <= less_than_profit)

        if the_filter.more_than_quantity is not None:
            query = query.where(Product.quantity >= the_filter.more_than_quantity)
        if the_filter.less_than_quantity is not None:
            query = query.where(Product.quantity <= the_filter.less_than_quantity)
        return query
