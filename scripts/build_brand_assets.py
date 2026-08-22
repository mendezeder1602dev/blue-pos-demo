"""Genera los activos de marca del sistema ECCOS a partir de los tokens de diseño.

Escribe el monograma, el logotipo, el juego de iconos de línea y los galones de
los controles numéricos en ``view/ui/images/``, y además rasteriza el icono de la
aplicación. Al derivar todo de ``view.style.tokens`` la iconografía nunca queda
desfasada de la paleta.

Uso:
    python scripts/build_brand_assets.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from view.style import tokens as t  # noqa: E402

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'view', 'ui', 'images')

NAVY = t.LIGHT['brand_deep']
NAVY_MID = t.LIGHT['brand_mid']
BRASS = t.LIGHT['brass']
PRIMARY = t.LIGHT['primary']
SOFT = t.LIGHT['primary_soft']

# Glifos de línea sobre una retícula de 24 px, trazo de 1.6 px y extremos
# redondeados: un solo peso visual para toda la navegación.
LINE_GLYPHS = {
    'home': '<path d="M3.2 10.4 12 3.4l8.8 7v9.3a1.3 1.3 0 0 1-1.3 1.3h-4.4v-6.6H8.9v6.6H4.5a1.3 1.3 0 0 1-1.3-1.3v-9.3Z"/>',
    'cart': ('<path d="M2.8 3.6h2.4l2.6 10.6h9.5l2.1-7.4H6.4"/>'
             '<circle cx="9.4" cy="19" r="1.5"/><circle cx="17.2" cy="19" r="1.5"/>'),
    'bolt': '<path d="M13.4 2.6 5.6 13.4h5.1l-1 8 7.8-11h-5.1l1-7.8Z"/>',
    'boxes': ('<path d="M3.4 8.1 12 4l8.6 4.1L12 12.3 3.4 8.1Z"/>'
              '<path d="M3.4 8.1v7.8L12 20v-7.7"/><path d="M20.6 8.1v7.8L12 20"/>'),
    'document': ('<path d="M6.2 2.9h7.4l4.2 4.2v14H6.2a.9.9 0 0 1-.9-.9V3.8a.9.9 0 0 1 .9-.9Z"/>'
                 '<path d="M13.4 3.1v4.3h4.3"/><path d="M8.6 12.2h6.8M8.6 15.6h6.8M8.6 18.4h4.3"/>'),
    'chat': ('<path d="M4 5.2h16a.9.9 0 0 1 .9.9v8.6a.9.9 0 0 1-.9.9h-9L6.6 19.6v-4H4a.9.9 0 0 1-.9-.9V6.1A.9.9 0 0 1 4 5.2Z"/>'
             '<path d="M7.6 9.1h8.8M7.6 12.1h5.6"/>'),
    'bars': ('<path d="M4.2 19.6V13M9.4 19.6V6.4M14.6 19.6v-8.4M19.8 19.6V9"/>'),
    'trend': ('<path d="M3.4 20.2h17.2"/><path d="m4.6 15.4 5-5.4 4 2.2 5.8-6.4"/>'
              '<path d="M15.8 5.8h3.6v3.6"/>'),
    'receipt': ('<path d="M5.6 3.2h12.8v17.6l-2.1-1.4-2.1 1.4-2.2-1.4-2.1 1.4-2.2-1.4-2.1 1.4V3.2Z"/>'
                '<path d="M9 8.4h6M9 12.2h6"/>'),
    'building': ('<path d="M4.6 20.6V5a.9.9 0 0 1 .9-.9h8.2a.9.9 0 0 1 .9.9v15.6"/>'
                 '<path d="M14.6 9.8h4a.9.9 0 0 1 .9.9v9.9"/>'
                 '<path d="M3.2 20.6h17.6"/><path d="M7.8 8h3.4M7.8 12h3.4M7.8 16h3.4"/>'),
    'sparkles': ('<path d="M12 3.2l1.7 4.6 4.6 1.7-4.6 1.7L12 15.8l-1.7-4.6L5.7 9.5l4.6-1.7L12 3.2Z"/>'
                 '<path d="M18.4 15.4l.8 2.1 2.1.8-2.1.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8.8-2.1Z"/>'),
}

# Los rótulos del inicio usan un azulejo de 96 px: fondo suave con el glifo
# encima, para que la retícula de accesos se lea como un solo conjunto.
TILE_GLYPHS = {
    'inventory': 'boxes',
    'expenses': 'receipt',
    'report': 'document',
    'analytics': 'trend',
    'sales': 'cart',
    'quote': 'sparkles',
}


def _line_icon(glyph: str, color: str, size: int = 24) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{glyph}</svg>')


def _tile_icon(glyph: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
            f'<rect width="96" height="96" rx="22" fill="{SOFT}"/>'
            f'<rect x="0.75" y="0.75" width="94.5" height="94.5" rx="21.25" fill="none" '
            f'stroke="{PRIMARY}" stroke-opacity="0.22" stroke-width="1.5"/>'
            f'<g transform="translate(24 24) scale(2)" fill="none" stroke="{NAVY}" '
            f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>')


def _monogram(size: int = 128) -> str:
    """Monograma ECCOS: cuadrado redondeado en degradado con una 'E' geométrica."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="eccos_navy" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{NAVY_MID}"/>
      <stop offset="1" stop-color="{NAVY}"/>
    </linearGradient>
  </defs>
  <rect width="128" height="128" rx="30" fill="url(#eccos_navy)"/>
  <rect x="34" y="34" width="46" height="9" rx="4.5" fill="#FFFFFF"/>
  <rect x="34" y="59.5" width="34" height="9" rx="4.5" fill="#FFFFFF"/>
  <rect x="34" y="85" width="46" height="9" rx="4.5" fill="#FFFFFF"/>
  <rect x="88" y="34" width="9" height="60" rx="4.5" fill="{BRASS}"/>
</svg>
'''


def _chevron(direction: str, color: str) -> str:
    path = 'm3 7.5 4.5-4 4.5 4' if direction == 'up' else 'm3 4.5 4.5 4 4.5-4'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="15" height="12" viewBox="0 0 15 12" '
            f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round"><path d="{path}"/></svg>')


def _write(name: str, content: str):
    with open(os.path.join(IMAGES_DIR, name), 'w', encoding='utf-8') as file:
        file.write(content)
    return name


def build_svg_assets() -> list:
    written = [_write('eccos_monogram.svg', _monogram())]

    for name, glyph in LINE_GLYPHS.items():
        written.append(_write(f'nav_{name}.svg', _line_icon(glyph, '#D6E4F1')))
        written.append(_write(f'ink_{name}.svg', _line_icon(glyph, NAVY)))

    for tile_name, glyph_name in TILE_GLYPHS.items():
        written.append(_write(f'eccos_{tile_name}.svg', _tile_icon(LINE_GLYPHS[glyph_name])))

    for direction in ('up', 'down'):
        written.append(_write(f'chevron_{direction}_dark.svg',
                              _chevron(direction, t.LIGHT['ink_3'])))
        written.append(_write(f'chevron_{direction}_light.svg',
                              _chevron(direction, t.DARK['ink_2'])))
    return written


def build_app_icon() -> str:
    """Rasteriza el monograma como icono de ventana en varios tamaños."""
    from PyQt5.QtGui import QGuiApplication, QIcon, QPixmap

    app = QGuiApplication.instance() or QGuiApplication(['build-brand-assets'])
    source = os.path.join(IMAGES_DIR, 'eccos_monogram.svg')
    icon = QIcon(source)
    target = os.path.join(IMAGES_DIR, 'eccos_icon.png')
    pixmap: QPixmap = icon.pixmap(256, 256)
    if pixmap.isNull():
        raise RuntimeError('No se pudo rasterizar el monograma; falta el plugin SVG de Qt.')
    pixmap.save(target, 'PNG')
    del app
    return 'eccos_icon.png'


if __name__ == '__main__':
    assets = build_svg_assets()
    assets.append(build_app_icon())
    print(f'{len(assets)} activos de marca generados en view/ui/images/')
