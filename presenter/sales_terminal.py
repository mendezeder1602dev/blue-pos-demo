from datetime import date
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from easy_mvp.abstract_presenter import AbstractPresenter
from model.entity.models import Sale
from model.report.ticket import generate_ticket_pdf
from model.repository.factory import RepositoryFactory
from view.sales_terminal import SalesTerminalView


class SalesTerminalPresenter(AbstractPresenter):
    def _on_initialize(self):
        self._set_view(SalesTerminalView(self)); self.__products=RepositoryFactory.get_product_repository(); self.__sales=RepositoryFactory.get_sale_repository(); self.__cart={}; self.__last_ticket_path=None
        profile=RepositoryFactory.get_business_profile_repository().get_profile(); self.__business={f:getattr(profile,f,'') or '' for f in ('business_name','owner_name','phone','address','whatsapp','email','tax_id')}
    def get_default_window_title(self): return 'Nueva venta'
    def on_view_shown(self): self.search_products()
    def return_to_main(self): self._close_this_presenter()
    def search_products(self):
        phrase=self.get_view().search_input.text().strip().lower()
        products=[p for p in self.__products.get_all_products() if p.quantity > 0]
        matches=[p for p in products if phrase and (phrase in (p.barcode or '').lower() or phrase in p.name.lower())]
        # El catálogo de existencias se mantiene fijo; buscar o escanear nunca lo reemplaza.
        self.get_view().set_products(products)
        if phrase and len(matches) == 1 and phrase == (matches[0].barcode or '').lower():
            self.add_product(matches[0].id, 1)
            self.get_view().select_product(matches[0].id)
            self.get_view().clear_search()
            return
        if phrase:
            self.get_view().show_message(f'{len(matches)} coincidencia(s). Selecciona el producto en el catálogo.')
        else:
            self.get_view().show_message(f'{len(products)} producto(s) disponibles')
    def add_selected_product(self):
        product_id=self.get_view().selected_product_id()
        if product_id is None: self.get_view().show_message('Selecciona un producto disponible.'); return
        self.add_product(product_id,self.get_view().quantity())
    def add_product(self,product_id,quantity):
        product=next((p for p in self.__products.get_all_products() if p.id==product_id),None)
        if not product: return
        old=self.__cart.get(product_id,{'quantity':0})['quantity']
        if old+quantity>product.quantity: self.get_view().show_message(f'Sólo hay {product.quantity} unidades de {product.name}.'); return
        self.__cart[product_id]={'product':product,'quantity':old+quantity}; self.__refresh_cart(); self.get_view().show_message(f'{product.name} agregado al carrito.')
    def remove_selected_item(self):
        product_id=self.get_view().selected_cart_product_id()
        if product_id is None: return
        self.__cart.pop(product_id,None); self.__refresh_cart(); self.get_view().show_message('Producto retirado del carrito.')
    def __refresh_cart(self):
        items=[]; total=0
        for product_id,row in self.__cart.items():
            product=row['product']; qty=row['quantity']; price=float(product.price.amount); line=qty*price; total+=line; items.append({'product_id':product_id,'name':product.name,'quantity':qty,'unit_price':price,'total':line})
        self.get_view().set_cart(items,total)
    def sell_cart(self):
        all_sales=[]; ticket_items=[]
        try:
            total = sum(float(row['product'].price.amount) * row['quantity'] for row in self.__cart.values())
            payment_data = self.get_view().collect_payment_data(total)
            for row in self.__cart.values():
                product=row['product']; qty=row['quantity']; sale = Sale(
                    product_id=product.id,
                    price=product.price,
                    cost=product.cost,
                    date=date.today(),
                    payment_method=payment_data['method'],
                    payment_details=payment_data['details'],
                )
                sales=self.__sales.insert_sales(sale,qty); all_sales.extend(sales); ticket_items.append({'name':product.name,'quantity':qty,'unit_price':product.price.amount})
            if not all_sales:
                self.get_view().show_message('Agrega productos al carrito antes de vender.')
                return
            self.__last_ticket_path = generate_ticket_pdf(
                self.__business,
                ticket_items,
                [sale.id for sale in all_sales],
                date.today(),
                payment_method=payment_data['label'],
                payment_details=payment_data['details'],
            )
            self.get_view().enable_last_ticket()
            self.__cart={}; self.__refresh_cart(); self.search_products(); self.get_view().show_message('Venta registrada. Ya puedes generar el ticket cuando lo necesites.')
        except Exception as error: self.get_view().show_message(f'No se pudo completar la venta: {error}')

    def generate_ticket_for_last_sale(self):
        if not getattr(self, '_SalesTerminalPresenter__last_ticket_path', None):
            self.get_view().show_message('Primero registra una venta para generar su ticket.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.__last_ticket_path)))
        self.get_view().show_message('Ticket PDF abierto.')

    def checkout_cart(self):
        self.sell_cart()
