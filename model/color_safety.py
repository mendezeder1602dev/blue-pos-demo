"""Utilidades de color para personalización segura y legible."""

import re


HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
DEFAULT_BRAND_COLOR = '#123B6D'
DEFAULT_APP_BACKGROUND = '#F1F3F6'
DEFAULT_APP_SURFACE = '#FFFFFF'
DEFAULT_APP_TEXT = '#111820'
DEFAULT_DOCUMENT_TEXT = '#111820'


def default_color_palette():
    """Devuelve la paleta segura que acompaña a una instalación nueva."""
    return {
        'brand_color': DEFAULT_BRAND_COLOR,
        'app_background_color': DEFAULT_APP_BACKGROUND,
        'app_surface_color': DEFAULT_APP_SURFACE,
        'app_text_color': DEFAULT_APP_TEXT,
        'document_primary_color': DEFAULT_BRAND_COLOR,
        'document_text_color': DEFAULT_DOCUMENT_TEXT,
    }


def normalize_hex_color(value, fallback=DEFAULT_BRAND_COLOR):
    """Devuelve un color #RRGGBB válido o el fallback normalizado."""
    candidate = (value or '').strip()
    if candidate and not candidate.startswith('#'):
        candidate = f'#{candidate}'
    if HEX_COLOR_RE.fullmatch(candidate):
        return candidate.upper()
    return fallback.upper()


def _blend_with_white(color, white_weight=0.94):
    """Aclara un color de marca para usarlo como fondo sin perder su identidad."""
    normalized = normalize_hex_color(color)
    channels = (int(normalized[index:index + 2], 16) for index in (1, 3, 5))
    blended = tuple(round(channel * (1 - white_weight) + 255 * white_weight)
                    for channel in channels)
    return '#{:02X}{:02X}{:02X}'.format(*blended)


def suggested_color_palette(brand_color):
    """Crea una paleta legible a partir del color principal del negocio."""
    brand = normalize_hex_color(brand_color)
    return {
        'brand_color': brand,
        'app_background_color': _blend_with_white(brand),
        'app_surface_color': DEFAULT_APP_SURFACE,
        'app_text_color': DEFAULT_APP_TEXT,
        'document_primary_color': brand,
        'document_text_color': DEFAULT_DOCUMENT_TEXT,
    }


def _channel_to_linear(channel):
    channel = channel / 255
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(color):
    """Calcula luminancia relativa WCAG para un color #RRGGBB."""
    normalized = normalize_hex_color(color)
    red = int(normalized[1:3], 16)
    green = int(normalized[3:5], 16)
    blue = int(normalized[5:7], 16)
    return (
        0.2126 * _channel_to_linear(red)
        + 0.7152 * _channel_to_linear(green)
        + 0.0722 * _channel_to_linear(blue)
    )


def contrast_ratio(foreground, background):
    """Relación de contraste WCAG entre texto y fondo."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter = max(first, second)
    darker = min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background, light='#FFFFFF', dark='#111820'):
    """Escoge automáticamente texto claro u oscuro, el que más contraste dé."""
    light_ratio = contrast_ratio(light, background)
    dark_ratio = contrast_ratio(dark, background)
    return normalize_hex_color(light if light_ratio >= dark_ratio else dark)


def ensure_contrast(foreground, background, label, minimum=4.5):
    """Lanza ValueError si una combinación de texto/fondo no es legible."""
    ratio = contrast_ratio(foreground, background)
    if ratio < minimum:
        raise ValueError(
            f'{label} no tiene suficiente contraste ({ratio:.2f}:1). '
            f'Usa colores con al menos {minimum:.1f}:1 para que se puedan leer.'
        )
    return ratio
