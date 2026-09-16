"""Normalización y validación de datos de contacto de clientes."""
from __future__ import annotations

import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email


COUNTRY_NAMES = {
    'MX': 'México', 'US': 'Estados Unidos', 'CA': 'Canadá',
    'GT': 'Guatemala', 'BZ': 'Belice', 'SV': 'El Salvador',
    'HN': 'Honduras', 'NI': 'Nicaragua', 'CR': 'Costa Rica',
    'PA': 'Panamá', 'CU': 'Cuba', 'DO': 'República Dominicana',
    'PR': 'Puerto Rico', 'CO': 'Colombia', 'VE': 'Venezuela',
    'EC': 'Ecuador', 'PE': 'Perú', 'BO': 'Bolivia', 'CL': 'Chile',
    'AR': 'Argentina', 'UY': 'Uruguay', 'PY': 'Paraguay',
    'BR': 'Brasil', 'ES': 'España',
}

# El código postal es opcional. Cuando se captura, estas reglas evitan valores
# truncados o claramente incompatibles con el país elegido.
POSTAL_CODE_RULES = {
    'MX': (r'\d{5}', '5 dígitos'),
    'US': (r'\d{5}(?:-\d{4})?', '5 dígitos o ZIP+4'),
    'PR': (r'\d{5}(?:-\d{4})?', '5 dígitos o ZIP+4'),
    'CA': (r'[A-Z]\d[A-Z][ -]?\d[A-Z]\d', 'formato A1A 1A1'),
    'GT': (r'\d{5}', '5 dígitos'), 'SV': (r'\d{4}', '4 dígitos'),
    'HN': (r'\d{5}', '5 dígitos'), 'NI': (r'\d{5}', '5 dígitos'),
    'CR': (r'\d{5}', '5 dígitos'), 'PA': (r'\d{4}', '4 dígitos'),
    'CU': (r'\d{5}', '5 dígitos'), 'DO': (r'\d{5}', '5 dígitos'),
    'CO': (r'\d{6}', '6 dígitos'), 'VE': (r'\d{4}', '4 dígitos'),
    'EC': (r'\d{6}', '6 dígitos'), 'PE': (r'\d{5}', '5 dígitos'),
    'BO': (r'\d{4}', '4 dígitos'), 'CL': (r'\d{7}', '7 dígitos'),
    'AR': (r'(?:\d{4}|[A-Z]\d{4}[A-Z]{3})', '4 dígitos o CPA'),
    'UY': (r'\d{5}', '5 dígitos'), 'PY': (r'\d{4}', '4 dígitos'),
    'BR': (r'\d{5}-?\d{3}', '8 dígitos'), 'ES': (r'\d{5}', '5 dígitos'),
}


def normalize_country(country: str = 'MX') -> str:
    region = (country or 'MX').strip().upper()
    if region not in COUNTRY_NAMES:
        raise ValueError('Selecciona un país válido para el teléfono.')
    return region


def country_label(country: str) -> str:
    region = normalize_country(country)
    dial_code = phonenumbers.country_code_for_region(region)
    return f'{COUNTRY_NAMES[region]} (+{dial_code})'


def country_options() -> tuple[str, ...]:
    return tuple(COUNTRY_NAMES)


def phone_length_hint(country: str) -> str:
    region = normalize_country(country)
    metadata = phonenumbers.PhoneMetadata.metadata_for_region(region)
    lengths = tuple(metadata.general_desc.possible_length) if metadata else ()
    if not lengths:
        return 'número nacional sin lada internacional'
    if len(lengths) == 1:
        return f'{lengths[0]} dígitos'
    return f'{min(lengths)} a {max(lengths)} dígitos'


def normalize_phone(phone: str, country: str = 'MX') -> str:
    region = normalize_country(country)
    raw_phone = (phone or '').strip()
    if not raw_phone:
        raise ValueError('Captura un teléfono válido para dar seguimiento al cliente.')
    if len(raw_phone) > 40:
        raise ValueError('El teléfono no puede superar 40 caracteres.')
    try:
        parsed = phonenumbers.parse(raw_phone, region)
    except phonenumbers.NumberParseException as error:
        raise ValueError(
            f'Captura un teléfono válido de {COUNTRY_NAMES[region]} '
            f'({phone_length_hint(region)}).') from error
    if not phonenumbers.is_valid_number_for_region(parsed, region):
        raise ValueError(
            f'Captura un teléfono válido de {COUNTRY_NAMES[region]} '
            f'({phone_length_hint(region)}).')
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def national_phone_value(phone: str, country: str = 'MX') -> str:
    """Devuelve un valor amigable para editar, incluso con datos heredados."""
    raw_phone = (phone or '').strip()
    if not raw_phone:
        return ''
    region = normalize_country(country)
    try:
        parsed = phonenumbers.parse(raw_phone, region)
        if phonenumbers.is_possible_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    except phonenumbers.NumberParseException:
        pass
    return raw_phone


def normalize_email(email: str) -> str:
    raw_email = (email or '').strip()
    if not raw_email:
        return ''
    if len(raw_email) > 120:
        raise ValueError('El correo no puede superar 120 caracteres.')
    try:
        result = validate_email(
            raw_email, check_deliverability=False, allow_display_name=False)
    except EmailNotValidError as error:
        raise ValueError(
            'Captura un correo electrónico válido, por ejemplo nombre@dominio.com, '
            'o déjalo vacío.') from error
    if len(result.normalized) > 120:
        raise ValueError('El correo no puede superar 120 caracteres.')
    return result.normalized


def normalize_postal_code(postal_code: str, country: str = 'MX') -> str:
    region = normalize_country(country)
    normalized = re.sub(r'\s+', ' ', (postal_code or '').strip().upper())
    if not normalized:
        return ''
    if len(normalized) > 12:
        raise ValueError('El código postal no puede superar 12 caracteres.')
    rule = POSTAL_CODE_RULES.get(region)
    if rule is not None and re.fullmatch(rule[0], normalized) is None:
        raise ValueError(
            f'Captura un código postal válido de {COUNTRY_NAMES[region]} '
            f'({rule[1]}).')
    return normalized
