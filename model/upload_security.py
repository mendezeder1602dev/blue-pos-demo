"""Validaciones de contenido para imágenes cargadas por usuarios."""

from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {
    'PNG': 'image/png',
    'JPEG': 'image/jpeg',
    'WEBP': 'image/webp',
}
MAX_IMAGE_PIXELS = 20_000_000


def validate_image_upload(content: bytes, max_bytes: int, allowed_formats=None):
    """Devuelve bytes y MIME solo si el archivo es una imagen real y segura."""
    if not content:
        raise ValueError('El archivo de imagen está vacío.')
    if len(content) > max_bytes:
        raise ValueError('La imagen supera el tamaño permitido.')
    formats = set(allowed_formats or ALLOWED_IMAGE_FORMATS)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image_format = (image.format or '').upper()
                width, height = image.size
                frames = int(getattr(image, 'n_frames', 1))
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('El archivo no es una imagen válida o segura.') from error
    if image_format not in formats:
        raise ValueError('El formato real de la imagen no está permitido.')
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError('La imagen tiene dimensiones no permitidas.')
    if frames != 1:
        raise ValueError('No se permiten imágenes animadas.')
    return content, ALLOWED_IMAGE_FORMATS[image_format]
