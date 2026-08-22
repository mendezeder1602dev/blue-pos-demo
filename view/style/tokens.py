"""Tokens de diseño del sistema ECCOS.

Fuente única de verdad para color, tipografía, espaciado y radios. Las hojas de
estilo, la portada y el tablero se construyen a partir de estos valores, de modo
que un ajuste de marca se hace en un solo lugar.

La paleta de datos (SERIES_*) fue validada con el verificador de accesibilidad en
tema claro y oscuro: banda de luminosidad, piso de croma, separación para
daltonismo (peor par ΔE 9.2 claro / 9.4 oscuro, objetivo ≥ 8) y contraste contra
la superficie. El verde claro queda en 2.82:1, por debajo de 3:1, así que sólo se
usa acompañado de una etiqueta de texto visible: nunca identifica un dato por
color solo.
"""

# --- Tipografía ---------------------------------------------------------------

FONT_STACK = '"Inter", "Segoe UI", "Roboto", "Noto Sans", "DejaVu Sans", Arial, sans-serif'

FONT_DISPLAY = '26pt'
FONT_H1 = '20pt'
FONT_H2 = '15pt'
FONT_H3 = '12pt'
FONT_BODY = '10pt'
FONT_SMALL = '9pt'
FONT_CAPTION = '8pt'
FONT_EYEBROW = '8pt'

WEIGHT_REGULAR = '400'
WEIGHT_MEDIUM = '500'
WEIGHT_SEMIBOLD = '600'
WEIGHT_BOLD = '700'

# --- Espaciado y radios ------------------------------------------------------

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6, SPACE_7 = 4, 8, 12, 16, 20, 24, 32

RADIUS_SM = '6px'
RADIUS_MD = '10px'
RADIUS_LG = '14px'
RADIUS_PILL = '18px'

# --- Paleta de datos (validada) ----------------------------------------------

SERIES_SALES_LIGHT = '#2A78D6'
SERIES_EXPENSE_LIGHT = '#EB6834'
SERIES_PROFIT_LIGHT = '#1BAF7A'

SERIES_SALES_DARK = '#3987E5'
SERIES_EXPENSE_DARK = '#D95926'
SERIES_PROFIT_DARK = '#199E70'

# --- Tema claro --------------------------------------------------------------

LIGHT = {
    'canvas': '#F2F5F9',
    'surface': '#FFFFFF',
    'surface_sunken': '#F7F9FC',
    'surface_hover': '#EDF3FA',
    'border': '#E1E8F0',
    'border_strong': '#CBD6E3',

    'ink': '#0E1F30',
    'ink_2': '#41586F',
    'ink_3': '#75899C',
    'ink_inverse': '#FFFFFF',

    'brand_deep': '#0D2942',
    'brand_mid': '#123A5C',
    'brand_soft_ink': '#B9CFE4',
    'brass': '#C08A2E',

    'primary': '#2A78D6',
    'primary_hover': '#1C64BC',
    'primary_pressed': '#17539E',
    'primary_soft': '#E8F1FC',
    'primary_soft_hover': '#D8E7F9',

    'danger': '#C6403B',
    'danger_hover': '#AB332F',

    'series_sales': SERIES_SALES_LIGHT,
    'series_expense': SERIES_EXPENSE_LIGHT,
    'series_profit': SERIES_PROFIT_LIGHT,

    'grid': '#E7EDF4',
    'disabled_bg': '#D9E1EA',
    'disabled_ink': '#94A6B6',
    'scroll_handle': '#C2D0DE',
}

# --- Tema oscuro (escalonado para su propia superficie, no un simple invertido)

DARK = {
    'canvas': '#12161B',
    'surface': '#1B2027',
    'surface_sunken': '#161A20',
    'surface_hover': '#232A33',
    'border': '#2C333C',
    'border_strong': '#3A434E',

    'ink': '#F2F5F8',
    'ink_2': '#A9B7C6',
    'ink_3': '#7C8B9B',
    'ink_inverse': '#0E1F30',

    'brand_deep': '#0B1926',
    'brand_mid': '#12293D',
    'brand_soft_ink': '#9DB8D2',
    'brass': '#D2A44C',

    'primary': '#3987E5',
    'primary_hover': '#5A9DEC',
    'primary_pressed': '#2A6FC4',
    'primary_soft': '#1B2C42',
    'primary_soft_hover': '#243851',

    'danger': '#E06B66',
    'danger_hover': '#EA8480',

    'series_sales': SERIES_SALES_DARK,
    'series_expense': SERIES_EXPENSE_DARK,
    'series_profit': SERIES_PROFIT_DARK,

    'grid': '#252C34',
    'disabled_bg': '#2C333C',
    'disabled_ink': '#6B7885',
    'scroll_handle': '#3E4855',
}

# --- Marca -------------------------------------------------------------------

BRAND_NAME = 'GRUPO ECCOS'
BRAND_PRODUCT = 'Punto de Venta'
BRAND_TAGLINE = 'Control ejecutivo de ventas, inventario y resultados.'
CURRENCY_CODE = 'MXN'
CURRENCY_SUFFIX = ' MXN'
