from datetime import date

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import QComboBox, QDateEdit, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout


class MakeSaleView(QFrame):
    """Pantalla de cobro enfocada en una sola decisión: cantidad y confirmar."""

    def __init__(self, presenter):
        super().__init__()
        self.__presenter = presenter
        self.__build_ui()

    def __build_ui(self):
        self.setObjectName('sale_checkout')
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self); layout.setContentsMargins(28, 26, 28, 22); layout.setSpacing(14)
        self.business_label = QLabel('PUNTO DE VENTA'); self.business_label.setObjectName('sale_checkout_business'); layout.addWidget(self.business_label)
        heading = QLabel('Nueva venta'); heading.setObjectName('sale_checkout_title'); layout.addWidget(heading)
        helper = QLabel('Confirma la cantidad y revisa el total antes de registrar la operación.'); helper.setObjectName('sale_checkout_help'); helper.setWordWrap(True); layout.addWidget(helper)
        self.product_card = QFrame(); self.product_card.setObjectName('sale_product_card')
        card_layout = QVBoxLayout(self.product_card); card_layout.setContentsMargins(18, 16, 18, 16); card_layout.setSpacing(4)
        self.product_name_label = QLabel('Producto'); self.product_name_label.setObjectName('sale_product_name')
        self.product_meta_label = QLabel(); self.product_meta_label.setObjectName('sale_product_meta')
        card_layout.addWidget(self.product_name_label); card_layout.addWidget(self.product_meta_label); layout.addWidget(self.product_card)
        form = QGridLayout(); form.setHorizontalSpacing(14); form.setVerticalSpacing(8)
        quantity_label = QLabel('Cantidad'); quantity_label.setObjectName('sale_field_label'); form.addWidget(quantity_label, 0, 0)
        self.sale_quantity_spin_box = QSpinBox(); self.sale_quantity_spin_box.setObjectName('sale_quantity_input'); self.sale_quantity_spin_box.setAlignment(Qt.AlignCenter); form.addWidget(self.sale_quantity_spin_box, 1, 0)
        date_label = QLabel('Fecha de venta'); date_label.setObjectName('sale_field_label'); form.addWidget(date_label, 0, 1)
        self.sale_date_edit = QDateEdit(); self.sale_date_edit.setCalendarPopup(True); form.addWidget(self.sale_date_edit, 1, 1); layout.addLayout(form)

        self.payment_method = QComboBox(); self.payment_method.addItems(['Efectivo', 'Transferencia', 'Tarjeta', 'Mixto']); self.payment_method.setObjectName('sale_payment_method')
        self.split_values = QFrame(); self.split_values.setObjectName('sale_split_frame'); split_layout = QVBoxLayout(self.split_values); split_layout.setContentsMargins(0, 0, 0, 0); split_layout.setSpacing(8)
        self.cash_split = QDoubleSpinBox(); self.cash_split.setPrefix('Efectivo: $ '); self.cash_split.setRange(0, 999999); self.cash_split.setDecimals(2)
        self.transfer_split = QDoubleSpinBox(); self.transfer_split.setPrefix('Transferencia: $ '); self.transfer_split.setRange(0, 999999); self.transfer_split.setDecimals(2)
        self.card_split = QDoubleSpinBox(); self.card_split.setPrefix('Tarjeta: $ '); self.card_split.setRange(0, 999999); self.card_split.setDecimals(2)
        for widget in (self.cash_split, self.transfer_split, self.card_split):
            widget.setSingleStep(1.0); split_layout.addWidget(widget)
        self.split_values.setVisible(False)
        layout.addWidget(self.payment_method); layout.addWidget(self.split_values)

        summary = QFrame(); summary.setObjectName('sale_total_card'); summary_layout = QHBoxLayout(summary); summary_layout.setContentsMargins(18, 15, 18, 15)
        caption = QLabel('Total a cobrar'); caption.setObjectName('sale_total_caption')
        self.money_to_pay_label = QLabel('$ 0.00 MXN'); self.money_to_pay_label.setObjectName('sale_total_value')
        summary_layout.addWidget(caption); summary_layout.addStretch(); summary_layout.addWidget(self.money_to_pay_label); layout.addWidget(summary)
        note = QLabel('Al confirmar se guardará la venta y se abrirá su ticket PDF listo para imprimir.'); note.setObjectName('sale_checkout_note'); note.setWordWrap(True); layout.addWidget(note)
        self.main_content_frame = QFrame(); actions = QHBoxLayout(self.main_content_frame); actions.setContentsMargins(0, 4, 0, 0)
        self.cancel_button = QPushButton('Cancelar'); self.cancel_button.setObjectName('secondary_pos_action')
        self.confirm_button = QPushButton('Vender'); self.confirm_button.setObjectName('primary_pos_action'); self.confirm_button.setDefault(True)
        self.ticket_button = QPushButton('Generar ticket'); self.ticket_button.setObjectName('secondary_pos_action')
        actions.addWidget(self.cancel_button); actions.addWidget(self.confirm_button, 1); actions.addWidget(self.ticket_button); layout.addWidget(self.main_content_frame)
        self.state_bar_label = QLabel(); self.state_bar_label.setObjectName('state_bar_label'); layout.addWidget(self.state_bar_label)
        self.sale_date_edit.setDate(QDate.currentDate()); self.sale_date_edit.setMaximumDate(QDate.currentDate())
        self.sale_quantity_spin_box.valueChanged.connect(self.__presenter.set_sale_result_by_quantity)
        self.payment_method.currentIndexChanged.connect(self.__update_payment_visibility)
        self.cancel_button.clicked.connect(self.__presenter.cancel_sale)
        self.confirm_button.clicked.connect(self.__presenter.make_sales_and_close_presenter)
        self.ticket_button.clicked.connect(self.__presenter.generate_ticket)

    def __update_payment_visibility(self):
        self.split_values.setVisible(self.payment_method.currentText() == 'Mixto')

    def collect_payment_data(self, total_amount):
        method = self.payment_method.currentText()
        if method == 'Mixto':
            cash = self.cash_split.value(); transfer = self.transfer_split.value(); card = self.card_split.value();
            payment_total = cash + transfer + card
            if abs(payment_total - total_amount) > 0.01:
                raise ValueError('La suma del pago mixto debe cubrir exactamente el total de la venta.')
            return {'method': 'mixed', 'details': f'Efectivo ${cash:,.2f}; Transferencia ${transfer:,.2f}; Tarjeta ${card:,.2f}', 'label': 'Mixto'}
        labels = {'Efectivo': 'Efectivo', 'Transferencia': 'Transferencia', 'Tarjeta': 'Tarjeta'}
        return {'method': method.lower().replace(' ', '_'), 'details': labels[method], 'label': labels[method]}

    def set_business_name(self, name: str): self.business_label.setText((name or 'PUNTO DE VENTA').upper())
    def set_product_summary(self, name: str, unit_price, available_quantity: int): self.product_name_label.setText(name); self.product_meta_label.setText(f'$ {float(unit_price.amount):,.2f} MXN por unidad · {available_quantity} disponibles')
    def set_limit_of_sales(self, available_quantity: int): self.sale_quantity_spin_box.setRange(1, available_quantity)
    def get_sale_quantity(self) -> int: return self.sale_quantity_spin_box.value()
    def get_sale_date(self) -> date:
        q_date = self.sale_date_edit.date(); return date(q_date.year(), q_date.month(), q_date.day())
    def set_money_to_pay(self, amount: str): self.money_to_pay_label.setText(f'$ {float(amount):,.2f} MXN')
    def hide_status_bar(self, set_hidden: bool): self.state_bar_label.setHidden(set_hidden)
    def set_status_bar_message(self, message: str): self.state_bar_label.setText(message)
    def disable_all_view_except_status_bar(self, disabled: bool):
        self.main_content_frame.setDisabled(disabled); self.product_card.setDisabled(disabled); self.sale_quantity_spin_box.setDisabled(disabled); self.sale_date_edit.setDisabled(disabled); self.payment_method.setDisabled(disabled)
