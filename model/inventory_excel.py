"""Plantilla, lectura y validación segura para importar inventario desde Excel."""
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import unicodedata

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


MAX_IMPORT_ROWS = 2000
MAX_IMPORT_BYTES = 5 * 1024 * 1024

ACTION_CREATE = 'Crear producto'
ACTION_ADD = 'Actualizar y sumar existencias'
ACTION_REPLACE = 'Actualizar y reemplazar existencias'
ACTION_SKIP = 'Omitir'
IMPORT_ACTIONS = (ACTION_CREATE, ACTION_ADD, ACTION_REPLACE, ACTION_SKIP)

COLUMNS = (
    'Nombre', 'Descripción', 'Código de barras', 'Precio de costo',
    'Precio de venta', 'Cantidad disponible', 'Categoría', 'Proveedor',
    'Unidad de medida', 'Existencia mínima', 'Existencia máxima',
)
REQUIRED_COLUMNS = (
    'Nombre', 'Descripción', 'Precio de costo', 'Precio de venta',
    'Cantidad disponible', 'Categoría',
)


def _normalized_text(value):
    normalized = unicodedata.normalize('NFKD', str(value or '').strip().lower())
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', normalized).strip()


def inventory_field_options(products, field):
    """Return unique, display-ready inventory values preserving first spelling."""
    unique = {}
    for product in products:
        value = ' '.join(str(getattr(product, field, '') or '').split())
        normalized = _normalized_text(value)
        if normalized and normalized not in unique:
            unique[normalized] = value
    return tuple(sorted(unique.values(), key=_normalized_text))


def canonical_inventory_value(value, options):
    """Reuse an existing display value when a new value is only a spelling variant."""
    cleaned = ' '.join(str(value or '').split())
    normalized = _normalized_text(cleaned)
    if not normalized:
        return ''
    return next(
        (option for option in options if _normalized_text(option) == normalized),
        cleaned,
    )


HEADER_MAP = {_normalized_text(column): column for column in COLUMNS}


def generate_inventory_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Inventario'
    sheet.append(COLUMNS)
    header_fill = PatternFill('solid', fgColor='123B6D')
    for cell in sheet[1]:
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    widths = (28, 38, 20, 18, 18, 20, 22, 24, 20, 18, 18)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.column_dimensions['C'].number_format = '@'
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = 'A1:K1'

    instructions = workbook.create_sheet('Instrucciones')
    instructions.append(('Cómo preparar el archivo',))
    instructions['A1'].font = Font(size=14, bold=True, color='123B6D')
    guidance = (
        'No cambies los encabezados de la hoja Inventario.',
        'Nombre, descripción, costo, precio, cantidad y categoría son obligatorios.',
        'Precio de costo y precio de venta deben ser mayores que cero.',
        'Cantidad disponible y existencias mínima/máxima deben ser enteros de cero o más.',
        'Código de barras, proveedor y unidad de medida son opcionales; si se omite se usa Unidad.',
        'Configura los códigos de barras como texto para conservar ceros iniciales.',
        f'Puedes importar hasta {MAX_IMPORT_ROWS:,} productos por archivo.',
        'Puntos ECCOS mostrará una vista previa editable antes de guardar cualquier dato.',
    )
    for line in guidance:
        instructions.append((line,))
    instructions.column_dimensions['A'].width = 105
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_inventory_workbook(content):
    if not content:
        raise ValueError('El archivo está vacío.')
    if len(content) > MAX_IMPORT_BYTES:
        raise ValueError('El archivo supera el límite de 5 MB.')
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as error:
        raise ValueError('No se pudo leer el archivo. Utiliza la plantilla .xlsx de Puntos ECCOS.') from error
    if 'Inventario' not in workbook.sheetnames:
        raise ValueError('El archivo debe contener una hoja llamada “Inventario”.')
    sheet = workbook['Inventario']
    raw_headers = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    headers = [HEADER_MAP.get(_normalized_text(value)) for value in raw_headers]
    missing_headers = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_headers:
        raise ValueError(f'Faltan columnas obligatorias: {", ".join(missing_headers)}.')

    rows = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        mapped = {header: value for header, value in zip(headers, values) if header}
        if not any(value not in (None, '') for value in mapped.values()):
            continue
        rows.append({column: _cell_text(mapped.get(column)) for column in COLUMNS})
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValueError(f'El archivo contiene más de {MAX_IMPORT_ROWS:,} productos.')
    if not rows:
        raise ValueError('La hoja Inventario no contiene productos.')
    return rows


def _decimal_value(value, label):
    cleaned = str(value or '').strip().replace('$', '').replace('MXN', '').replace(',', '')
    try:
        result = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label} debe ser un número válido.')
    if result <= 0:
        raise ValueError(f'{label} debe ser mayor que cero.')
    return result.quantize(Decimal('0.01'))


def _integer_value(value, label, default=None):
    if value in (None, '') and default is not None:
        return default
    try:
        decimal = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label} debe ser un número entero.')
    if decimal != decimal.to_integral_value() or decimal < 0:
        raise ValueError(f'{label} debe ser un entero de cero o más.')
    return int(decimal)


def _existing_match(row, products):
    normalized_name = _normalized_text(row.get('Nombre'))
    barcode = _cell_text(row.get('Código de barras'))
    by_name = next((product for product in products
                    if _normalized_text(product.name) == normalized_name), None)
    by_barcode = next((product for product in products
                       if barcode and (product.barcode or '').strip() == barcode), None)
    if by_name is not None and by_barcode is not None and by_name.id != by_barcode.id:
        raise ValueError('el nombre y el código pertenecen a productos existentes diferentes.')
    return by_barcode or by_name


def build_import_preview(rows, products):
    preview = []
    for row in rows:
        item = {column: row.get(column, '') for column in COLUMNS}
        try:
            existing = _existing_match(item, products)
            item['Estado'] = f'Existente · {existing.name}' if existing else 'Producto nuevo'
            item['Acción'] = ACTION_ADD if existing else ACTION_CREATE
        except ValueError as error:
            item['Estado'] = f'Revisar: {error}'
            item['Acción'] = ACTION_SKIP
        preview.append(item)
    return preview


def validate_import_rows(rows, products):
    plans, errors = [], []
    seen_names, seen_barcodes = set(), set()
    category_options = list(inventory_field_options(products, 'category'))
    supplier_options = list(inventory_field_options(products, 'supplier'))
    for index, source in enumerate(rows, start=2):
        action = str(source.get('Acción') or '').strip()
        if action == ACTION_SKIP:
            continue
        try:
            name = ' '.join(str(source.get('Nombre') or '').split())
            description = str(source.get('Descripción') or '').strip()
            category = canonical_inventory_value(source.get('Categoría'), category_options)
            if not name or not description or not category:
                raise ValueError('nombre, descripción y categoría son obligatorios.')
            if category not in category_options:
                category_options.append(category)
            supplier = canonical_inventory_value(source.get('Proveedor'), supplier_options)
            if supplier and supplier not in supplier_options:
                supplier_options.append(supplier)
            barcode = _cell_text(source.get('Código de barras'))
            normalized_name = _normalized_text(name)
            if normalized_name in seen_names:
                raise ValueError('el nombre está repetido dentro del Excel.')
            if barcode and barcode in seen_barcodes:
                raise ValueError('el código de barras está repetido dentro del Excel.')
            seen_names.add(normalized_name)
            if barcode:
                seen_barcodes.add(barcode)

            existing = _existing_match(source, products)
            if existing is None and action != ACTION_CREATE:
                raise ValueError('selecciona “Crear producto” para un artículo nuevo.')
            if existing is not None and action == ACTION_CREATE:
                raise ValueError('el producto ya existe; elige sumar, reemplazar u omitir.')
            if action not in IMPORT_ACTIONS:
                raise ValueError('selecciona una acción válida.')

            plans.append({
                'existing_id': existing.id if existing else None,
                'action': action, 'name': name, 'description': description,
                'barcode': barcode,
                'cost': _decimal_value(source.get('Precio de costo'), 'el precio de costo'),
                'price': _decimal_value(source.get('Precio de venta'), 'el precio de venta'),
                'quantity': _integer_value(
                    source.get('Cantidad disponible'), 'la cantidad disponible'),
                'category': category,
                'supplier': supplier,
                'unit_of_measure': ' '.join(str(source.get('Unidad de medida') or 'Unidad').split()) or 'Unidad',
                'minimum_stock': _integer_value(
                    source.get('Existencia mínima'), 'la existencia mínima', default=5),
                'maximum_stock': _integer_value(
                    source.get('Existencia máxima'), 'la existencia máxima', default=0),
            })
        except ValueError as error:
            errors.append(f'Fila {index}: {error}')
    if not plans and not errors:
        errors.append('No hay productos seleccionados para importar.')
    return plans, errors
