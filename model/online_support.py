"""Soporte general opcional mediante una API externa, sin datos del negocio."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
DEFAULT_MODEL = 'openai/gpt-oss-20b'
MAX_QUESTION_LENGTH = 600


class OnlineSupportError(RuntimeError):
    """Error seguro y presentable de la consulta externa."""


def is_available() -> bool:
    return bool(os.getenv('GROQ_API_KEY', '').strip())


def sanitize_question(question: str) -> str:
    """Limita y oculta identificadores comunes antes de transmitir una duda."""
    clean = ' '.join(str(question or '').strip().split())[:MAX_QUESTION_LENGTH]
    if not clean:
        raise ValueError('Escribe una pregunta antes de consultar soporte en línea.')
    replacements = (
        (r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[correo oculto]'),
        (r'(?i)\bVALE-[A-Z0-9-]{6,}\b', '[código de vale oculto]'),
        (r'(?i)\bV-\d{4,}\b', '[folio oculto]'),
        (r'(?i)\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b', '[RFC oculto]'),
        (r'(?i)\$\s*[\d,]+(?:\.\d{1,2})?\s*(?:MXN)?', '[importe oculto]'),
        (r'(?<!\d)(?:\+?52[\s.-]?)?(?:\d[\s.-]?){10}(?!\d)', '[teléfono oculto]'),
    )
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean)
    return clean


def ask_online_support(question: str, role: str, timeout: int = 20) -> str:
    """Consulta Groq con contexto mínimo y sin enviar bases, historiales o credenciales."""
    api_key = os.getenv('GROQ_API_KEY', '').strip()
    if not api_key:
        raise OnlineSupportError('El soporte en línea todavía no tiene una clave configurada.')
    safe_question = sanitize_question(question)
    safe_role = 'administrador' if role == 'admin' else 'vendedor'
    payload = {
        'model': os.getenv('GROQ_SUPPORT_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        'temperature': 0.15,
        'max_completion_tokens': 550,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Eres soporte técnico general de Puntos ECCOS, un punto de venta en '
                    'Windows construido con Streamlit. Responde en español claro y breve. '
                    'Sólo ayudas con diagnóstico general de Windows, impresoras térmicas, '
                    'navegadores, redes y uso seguro de software. No conoces los datos privados '
                    'ni el estado real del negocio. No inventes botones ni confirmes operaciones. '
                    'Nunca indiques alterar directamente la base de datos, saltar permisos, '
                    'compartir contraseñas o ejecutar comandos destructivos. Para ventas, caja, '
                    'vales, devoluciones o inventario, recuerda que prevalece el procedimiento '
                    'local de Puntos ECCOS y que las autorizaciones corresponden al administrador.'
                ),
            },
            {
                'role': 'user',
                'content': f'Perfil actual: {safe_role}. Consulta sanitizada: {safe_question}',
            },
        ],
    }
    request = Request(
        GROQ_ENDPOINT,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Puntos-ECCOS-Support/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
        answer = result['choices'][0]['message']['content'].strip()
        if not answer:
            raise OnlineSupportError('El proveedor no devolvió una respuesta utilizable.')
        return answer
    except HTTPError as error:
        if error.code == 401:
            message = 'La clave del soporte en línea no es válida.'
        elif error.code == 429:
            message = 'El límite gratuito está ocupado o se agotó. Intenta más tarde.'
        else:
            message = f'El soporte en línea respondió con el error HTTP {error.code}.'
        raise OnlineSupportError(message) from error
    except (URLError, TimeoutError) as error:
        raise OnlineSupportError(
            'No fue posible conectarse al soporte en línea. La ayuda local sigue disponible.'
        ) from error
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise OnlineSupportError('La respuesta del proveedor no tuvo el formato esperado.') from error
