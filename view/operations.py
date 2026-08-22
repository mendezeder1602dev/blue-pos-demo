from datetime import date
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QSpinBox, QTextEdit, QVBoxLayout)


class ExpressSaleDialog(QDialog):
    def __init__(self, submit, parent=None, allow_cost=True):
        super().__init__(parent); self.submit = submit; self.setWindowTitle('Venta exprés'); self.setMinimumWidth(420)
        layout = QVBoxLayout(self); layout.addWidget(QLabel('Ideal para artículos ocasionales, usados o ventas de mostrador.'))
        form = QFormLayout(); self.name = QLineEdit(); self.price = QDoubleSpinBox(); self.cost = QDoubleSpinBox(); self.qty = QSpinBox()
        for field in (self.price, self.cost): field.setMaximum(9999999); field.setDecimals(2); field.setSuffix(' MXN')
        self.qty.setRange(1, 9999); self.price.setValue(1)
        form.addRow('Artículo', self.name); form.addRow('Precio unitario', self.price)
        if allow_cost: form.addRow('Costo unitario', self.cost)
        form.addRow('Cantidad', self.qty); layout.addLayout(form)
        if not allow_cost: self.cost.setValue(0)
        self.add_to_inventory = QCheckBox('Agregar también al inventario para futuras ventas'); self.add_to_inventory.setChecked(False); self.add_to_inventory.setVisible(allow_cost); layout.addWidget(self.add_to_inventory)
        self.ticket_note = QLabel('Si no lo agregas al inventario se registrará como Venta temporal y tendrá su propio ticket.'); self.ticket_note.setWordWrap(True); layout.addWidget(self.ticket_note)
        row = QHBoxLayout(); sell_button = QPushButton('Vender'); ticket_button = QPushButton('Generar ticket'); sell_button.clicked.connect(lambda: self._save(generate_ticket=False)); ticket_button.clicked.connect(lambda: self._save(generate_ticket=True)); row.addWidget(sell_button); row.addWidget(ticket_button); layout.addLayout(row)
    def _save(self, generate_ticket=True):
        try:
            result = self.submit(self.name.text().strip(), self.price.value(), self.cost.value(), self.qty.value(), self.add_to_inventory.isChecked(), generate_ticket)
            QMessageBox.information(self, 'Venta registrada', result); self.accept()
        except Exception as error: QMessageBox.warning(self, 'No se pudo registrar', str(error))


class QuoteDialog(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent); self.profile = profile; self.items = []; self.setWindowTitle('Cotización'); self.setMinimumWidth(520)
        layout = QVBoxLayout(self); layout.addWidget(QLabel('Cotización · agrega los artículos que necesites y comparte el total'))
        form = QFormLayout(); self.client = QLineEdit(); self.item = QLineEdit(); self.price = QDoubleSpinBox(); self.qty = QSpinBox()
        self.price.setMaximum(9999999); self.price.setDecimals(2); self.price.setSuffix(' MXN'); self.qty.setRange(1, 9999); self.qty.setValue(1)
        form.addRow('Cliente', self.client); form.addRow('Producto / servicio', self.item); form.addRow('Precio unitario', self.price); form.addRow('Cantidad', self.qty); layout.addLayout(form)
        row = QHBoxLayout(); add = QPushButton('Agregar producto'); remove = QPushButton('Quitar último'); add.clicked.connect(self._add_item); remove.clicked.connect(self._remove_item); row.addWidget(add); row.addWidget(remove); layout.addLayout(row)
        self.items_label = QLabel('Sin productos agregados'); self.items_label.setWordWrap(True); layout.addWidget(self.items_label)
        self.output = QTextEdit(); self.output.setReadOnly(True); self.output.setMinimumHeight(130); layout.addWidget(self.output)
        row = QHBoxLayout(); generate = QPushButton('Generar cotización'); copy = QPushButton('Copiar'); generate.clicked.connect(self._generate); copy.clicked.connect(lambda: self.output.copy()); row.addWidget(generate); row.addWidget(copy); layout.addLayout(row)
    def _add_item(self):
        name = self.item.text().strip() or 'Artículo'; qty = self.qty.value(); price = self.price.value(); self.items.append((name, qty, price)); self._refresh_items()
        self.item.clear(); self.qty.setValue(1); self.price.setValue(0)
    def _remove_item(self):
        if self.items: self.items.pop(); self._refresh_items()
    def _refresh_items(self):
        if not self.items: self.items_label.setText('Sin productos agregados'); return
        self.items_label.setText('\n'.join(f'• {qty} × {name} — $ {qty*price:,.2f} MXN' for name, qty, price in self.items))
    def _generate(self):
        if not self.items: self._add_item()
        total = sum(qty * price for _, qty, price in self.items); name = self.profile.business_name
        lines = '\n'.join(f'{qty} × {item}  $ {qty*price:,.2f}' for item, qty, price in self.items)
        self.output.setPlainText(f'COTIZACIÓN\n{name}\nFecha: {date.today():%d/%m/%Y}\nCliente: {self.client.text() or "Público general"}\n\n{lines}\n\nTotal: $ {total:,.2f} MXN\n\nVigencia: 7 días.')


class BusinessProfileDialog(QDialog):
    def __init__(self, profile, save, parent=None):
        super().__init__(parent); self.save = save; self.setWindowTitle('Perfil del negocio'); self.setMinimumWidth(460)
        layout = QVBoxLayout(self); form = QFormLayout(); self.fields = {}
        for key, label in [('business_name','Nombre comercial'),('owner_name','Responsable'),('phone','Teléfono'),('whatsapp','WhatsApp'),('email','Correo'),('tax_id','RFC / identificación fiscal'),('website','Sitio web'),('address','Dirección')]:
            field = QLineEdit(getattr(profile, key) or ''); self.fields[key] = field; form.addRow(label, field)
        self.logo = QLineEdit(getattr(profile, 'logo_path', '') or ''); self.logo.setReadOnly(True); form.addRow('Logo', self.logo)
        layout.addLayout(form); logo_button = QPushButton('Cargar logo'); logo_button.clicked.connect(self._logo); layout.addWidget(logo_button); button = QPushButton('Guardar perfil'); button.clicked.connect(self._save); layout.addWidget(button)
    def _logo(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Logo del negocio', '', 'Imágenes (*.png *.jpg *.jpeg *.webp)')
        if path: self.logo.setText(path)
    def _save(self):
        values = {key: field.text().strip() for key, field in self.fields.items()}; values['logo_path'] = self.logo.text().strip(); self.save(values); self.accept()


class SalesChannelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle('Canal de ventas'); self.setMinimumWidth(430)
        layout = QVBoxLayout(self); title = QLabel('Canal de ventas digital'); layout.addWidget(title)
        text = QLabel('Conecta la operación con WhatsApp Web para recibir pedidos y compartir cotizaciones desde el canal de tu negocio.'); text.setWordWrap(True); layout.addWidget(text)
        button = QPushButton('Abrir WhatsApp Web'); button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://web.whatsapp.com/'))); layout.addWidget(button)
        layout.addWidget(QLabel('El canal se abre en el navegador para que inicies sesión con la cuenta del negocio.'))
