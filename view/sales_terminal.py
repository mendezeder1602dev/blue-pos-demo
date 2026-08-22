from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFrame, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


class SalesTerminalView(QFrame):
    def __init__(self, presenter):
        super().__init__()
        self.__presenter = presenter
        self.__build()

    def __build(self):
        self.setObjectName('sale_checkout')
        self.setMinimumSize(980, 680)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(16)

        header = QFrame()
        header.setObjectName('page_header')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        back = QPushButton('←  Volver al inicio')
        back.setObjectName('secondary_pos_action')
        heading = QVBoxLayout()
        eyebrow = QLabel('OPERACIÓN  /  PUNTO DE VENTA')
        eyebrow.setObjectName('sale_checkout_business')
        title = QLabel('Nueva venta')
        title.setObjectName('sale_checkout_title')
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        badge = QLabel('CAJA ABIERTA')
        badge.setObjectName('header_badge')
        header_layout.addWidget(back)
        header_layout.addSpacing(12)
        header_layout.addLayout(heading)
        header_layout.addStretch()
        header_layout.addWidget(badge)
        root.addWidget(header)

        search_card = QFrame()
        search_card.setObjectName('sale_search_card')
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 12, 16, 12)
        search_copy = QVBoxLayout()
        search_title = QLabel('Buscar o escanear producto')
        search_title.setObjectName('sale_panel_title')
        hint = QLabel('Escribe el nombre o escanea el código de barras para agregarlo rápidamente.')
        hint.setObjectName('sale_checkout_help')
        search_copy.addWidget(search_title)
        search_copy.addWidget(hint)
        self.search_input = QLineEdit()
        self.search_input.setObjectName('barcode_input')
        self.search_input.setPlaceholderText('Código de barras o nombre')
        self.search_input.setClearButtonEnabled(True)
        find = QPushButton('Buscar')
        find.setObjectName('secondary_pos_action')
        search_layout.addLayout(search_copy, 1)
        search_layout.addWidget(self.search_input, 2)
        search_layout.addWidget(find)
        root.addWidget(search_card)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        product_card, left = self.__panel('CATÁLOGO', 'Productos con existencias disponibles')
        self.products = self.__table(['Producto', 'Precio', 'Stock'])
        self.products.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        left.addWidget(self.products)
        product_actions = QHBoxLayout()
        self.qty = QSpinBox()
        self.qty.setObjectName('sale_quantity_input')
        self.qty.setRange(1, 999)
        self.qty.setValue(1)
        add = QPushButton('+  Agregar al carrito')
        add.setObjectName('primary_pos_action')
        product_actions.addWidget(QLabel('Cantidad', objectName='sale_field_label'))
        product_actions.addWidget(self.qty)
        product_actions.addStretch()
        product_actions.addWidget(add)
        left.addLayout(product_actions)
        columns.addWidget(product_card, 1)

        cart_card, right = self.__panel('CARRITO', 'Revisa cantidades e importes antes de cobrar')
        self.cart = self.__table(['Producto', 'Cant.', 'P. unit.', 'Importe'])
        self.cart.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        right.addWidget(self.cart)
        remove = QPushButton('Quitar seleccionado')
        remove.setObjectName('secondary_pos_action')
        right.addWidget(remove, 0, Qt.AlignRight)
        columns.addWidget(cart_card, 1)
        root.addLayout(columns, 1)

        payment_panel = QFrame()
        payment_panel.setObjectName('sale_payment_panel')
        payment_layout = QHBoxLayout(payment_panel)
        payment_layout.setContentsMargins(16, 12, 16, 12)
        payment_layout.setSpacing(12)
        payment_copy = QVBoxLayout()
        payment_title = QLabel('PAGO Y COBRO')
        payment_title.setObjectName('sale_panel_title')
        payment_help = QLabel('Selecciona cómo pagará el cliente')
        payment_help.setObjectName('sale_checkout_help')
        payment_copy.addWidget(payment_title)
        payment_copy.addWidget(payment_help)
        payment_layout.addLayout(payment_copy, 1)
        self.payment_method = QComboBox()
        self.payment_method.addItems(['Efectivo', 'Transferencia', 'Tarjeta', 'Mixto'])
        self.payment_method.setObjectName('sale_payment_method')
        self.payment_method.setMinimumWidth(180)
        payment_layout.addWidget(self.payment_method)
        self.split_values = QFrame()
        self.split_values.setObjectName('sale_split_frame')
        split_layout = QHBoxLayout(self.split_values)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(8)
        self.cash_split = QDoubleSpinBox(); self.cash_split.setPrefix('Efectivo: $ '); self.cash_split.setRange(0, 999999); self.cash_split.setDecimals(2)
        self.transfer_split = QDoubleSpinBox(); self.transfer_split.setPrefix('Transferencia: $ '); self.transfer_split.setRange(0, 999999); self.transfer_split.setDecimals(2)
        self.card_split = QDoubleSpinBox(); self.card_split.setPrefix('Tarjeta: $ '); self.card_split.setRange(0, 999999); self.card_split.setDecimals(2)
        for widget in (self.cash_split, self.transfer_split, self.card_split):
            widget.setSingleStep(1.0)
            split_layout.addWidget(widget)
        self.split_values.setVisible(False)
        payment_layout.addWidget(self.split_values)
        root.addWidget(payment_panel)

        self.payment_method.currentIndexChanged.connect(self.__update_payment_visibility)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.status = QLabel('Selecciona productos para iniciar la venta')
        self.status.setObjectName('state_bar_label')
        self.status.setWordWrap(True)
        total_card = QFrame()
        total_card.setObjectName('sale_total_card')
        total_layout = QVBoxLayout(total_card)
        total_layout.setContentsMargins(22, 10, 22, 10)
        total_caption = QLabel('TOTAL A COBRAR')
        total_caption.setObjectName('sale_total_caption')
        self.total = QLabel('$ 0.00 MXN')
        self.total.setObjectName('sale_total_value')
        total_layout.addWidget(total_caption)
        total_layout.addWidget(self.total)
        self.ticket = QPushButton('Abrir último ticket')
        self.ticket.setObjectName('secondary_pos_action')
        self.ticket.setEnabled(False)
        self.sell = QPushButton('Cobrar venta  →')
        self.sell.setObjectName('primary_pos_action')
        self.sell.setEnabled(False)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.ticket)
        bottom.addWidget(total_card)
        bottom.addWidget(self.sell)
        root.addLayout(bottom)
        back.clicked.connect(self.__presenter.return_to_main); find.clicked.connect(self.__presenter.search_products); self.search_input.returnPressed.connect(self.__presenter.search_products); add.clicked.connect(self.__presenter.add_selected_product); remove.clicked.connect(self.__presenter.remove_selected_item); self.sell.clicked.connect(self.__presenter.sell_cart); self.ticket.clicked.connect(self.__presenter.generate_ticket_for_last_sale)

    @staticmethod
    def __panel(title, help_text):
        panel = QFrame()
        panel.setObjectName('sale_panel')
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName('sale_panel_title')
        helper = QLabel(help_text)
        helper.setObjectName('sale_checkout_help')
        layout.addWidget(heading)
        layout.addWidget(helper)
        return panel, layout

    @staticmethod
    def __table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        return table

    def __update_payment_visibility(self):
        self.split_values.setVisible(self.payment_method.currentText() == 'Mixto')

    def set_products(self, products):
        self.products.setRowCount(0)
        for product in products:
            row=self.products.rowCount(); self.products.insertRow(row); self.products.setItem(row,0,QTableWidgetItem(product.name)); self.products.setItem(row,1,QTableWidgetItem(f'$ {float(product.price.amount):,.2f}')); self.products.setItem(row,2,QTableWidgetItem(str(product.quantity))); self.products.item(row,0).setData(Qt.UserRole,product.id)
        self.products.resizeColumnsToContents()

    def selected_product_id(self):
        row=self.products.currentRow(); return self.products.item(row,0).data(Qt.UserRole) if row >= 0 else None

    def select_product(self, product_id):
        for row in range(self.products.rowCount()):
            if self.products.item(row, 0).data(Qt.UserRole) == product_id:
                self.products.selectRow(row)
                return

    def quantity(self): return self.qty.value()

    def set_cart(self, items, total):
        self.cart.setRowCount(0)
        for item in items:
            row=self.cart.rowCount(); self.cart.insertRow(row)
            for col,value in enumerate((item['name'],str(item['quantity']),f"$ {item['unit_price']:,.2f}",f"$ {item['total']:,.2f}")): self.cart.setItem(row,col,QTableWidgetItem(value))
            self.cart.item(row,0).setData(Qt.UserRole,item['product_id'])
        self.cart.resizeColumnsToContents(); self.total.setText(f'$ {total:,.2f} MXN'); self.sell.setEnabled(bool(items))

    def enable_last_ticket(self):
        self.ticket.setEnabled(True)

    def selected_cart_product_id(self):
        row=self.cart.currentRow(); return self.cart.item(row,0).data(Qt.UserRole) if row >= 0 else None

    def collect_payment_data(self, total_amount):
        method = self.payment_method.currentText()
        if method == 'Mixto':
            cash = self.cash_split.value(); transfer = self.transfer_split.value(); card = self.card_split.value()
            payment_total = cash + transfer + card
            if abs(payment_total - total_amount) > 0.01:
                raise ValueError('La suma del pago mixto debe cubrir exactamente el total de la venta.')
            return {'method': 'mixed', 'details': f'Efectivo ${cash:,.2f}; Transferencia ${transfer:,.2f}; Tarjeta ${card:,.2f}', 'label': 'Mixto'}
        labels = {'Efectivo': 'Efectivo', 'Transferencia': 'Transferencia', 'Tarjeta': 'Tarjeta'}
        return {'method': method.lower().replace(' ', '_'), 'details': labels[method], 'label': labels[method]}

    def show_message(self,text): self.status.setText(text)
    def clear_search(self): self.search_input.clear(); self.search_input.setFocus()
