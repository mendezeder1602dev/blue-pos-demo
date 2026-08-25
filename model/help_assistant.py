"""Base de conocimiento local para el Asistente ECCOS, sin servicios externos."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata


@dataclass(frozen=True)
class HelpTopic:
    question: str
    answer: str
    category: str
    roles: tuple[str, ...] = ('admin', 'seller')
    page: str | None = None
    keywords: tuple[str, ...] = ()


TOPICS = (
    HelpTopic('¿Cómo realizar una nueva venta?', '1. Abre **Nueva venta**.\n2. Busca o escanea un producto.\n3. Agrégalo al carrito y ajusta la cantidad.\n4. Selecciona el método de pago.\n5. Verifica el total y pulsa **Cobrar**.\n\nTodos los artículos del carrito se registran como una sola operación.', 'Ventas', page='Nueva venta', keywords=('cobrar', 'carrito', 'vender', 'venta')),
    HelpTopic('¿Cómo funciona el pago con tarjeta?', 'En la venta selecciona **Tarjeta**, indica si es débito o crédito y confirma el total antes de cobrar. No registres la operación hasta que la terminal bancaria haya aprobado el pago.', 'Ventas', page='Nueva venta', keywords=('debito', 'credito', 'terminal', 'tarjeta')),
    HelpTopic('¿Cómo crear y cobrar una cotización?', 'Abre **Cotizaciones**, selecciona productos del inventario y ajusta cantidades. Guarda la propuesta y genera su PDF si lo necesitas. Cuando el cliente la acepte, envíala a la venta para revisar y cobrar el carrito.', 'Cotizaciones', page='Cotizaciones', keywords=('presupuesto', 'pdf', 'aprobar', 'cotizacion')),
    HelpTopic('¿Qué hago si un producto no aparece?', 'Comprueba que el producto exista en **Inventario**, tenga stock disponible y que el filtro de búsqueda esté limpio. Si no existe, un administrador debe registrarlo. Para un artículo ocasional que no pertenecerá al catálogo, utiliza **Venta express**.', 'Inventario', page='Inventario', keywords=('buscar', 'no aparece', 'sin stock', 'producto')),
    HelpTopic('¿Cómo registrar un producto en inventario?', 'Abre **Inventario**, completa todos los campos obligatorios y pulsa el botón de guardar. Blue POS valida nombres y códigos de barras repetidos para evitar duplicados. No uses Enter para intentar guardar el formulario.', 'Inventario', roles=('admin',), page='Inventario', keywords=('alta', 'codigo de barras', 'duplicado', 'inventario')),
    HelpTopic('¿Cómo editar o eliminar un producto?', 'Abre **Inventario** y despliega **Editar o dar de baja un producto**. Selecciona el artículo para corregir sus datos o confirma **Eliminar del inventario**. La baja lo oculta de ventas y del catálogo, pero conserva tickets y movimientos anteriores para proteger la auditoría.', 'Inventario', roles=('admin',), page='Inventario', keywords=('editar', 'eliminar', 'baja', 'archivar', 'producto')),
    HelpTopic('¿Qué significan las alertas de inventario?', 'Una alerta **sin stock** indica cero unidades; **por agotarse** indica existencias iguales o menores al mínimo configurado. Revisa esos artículos antes de comprar mercancía o prometer una venta.', 'Inventario', page='Inventario', keywords=('alerta', 'agotado', 'existencias', 'stock')),
    HelpTopic('¿Cómo abrir la caja?', 'Antes de la primera venta abre **Apertura de caja**, captura la cantidad de cada denominación mexicana, comprueba el total del fondo de cambio y confirma la apertura. Ese importe no es una venta ni una ganancia.', 'Caja', page='Apertura de caja', keywords=('fondo', 'cambio', 'billetes', 'monedas', 'abrir caja')),
    HelpTopic('¿Cómo hacer el corte o cierre de caja?', 'Abre **Corte de caja**, cuenta físicamente billetes y monedas, registra las denominaciones y compara el efectivo contado contra el esperado. Revisa diferencias, ventas, gastos y retiros antes de confirmar el cierre.', 'Caja', page='Corte de caja', keywords=('arqueo', 'cierre', 'diferencia', 'corte')),
    HelpTopic('¿Cómo registrar un retiro de efectivo?', 'Los retiros deben ser autorizados y registrados por el administrador, indicando importe y motivo. El retiro reduce el efectivo esperado en caja, pero no debe contabilizarse como una venta.', 'Caja', roles=('admin',), page='Corte de caja', keywords=('sacar dinero', 'retiro', 'efectivo')),
    HelpTopic('¿Cómo registrar, editar o eliminar un gasto?', 'En **Gastos**, captura concepto, importe y demás datos requeridos y guarda con el botón correspondiente. El administrador puede revisar el listado y editar o eliminar registros; conviene conservar el motivo para auditoría.', 'Administración', roles=('admin',), page='Gastos', keywords=('egreso', 'eliminar gasto', 'editar gasto', 'gasto')),
    HelpTopic('¿Cómo descargar reportes en PDF o Excel?', 'Abre **Reportes**, elige periodo y fecha, revisa el resumen y utiliza el botón de descarga PDF o Excel. Los documentos toman la identidad y datos guardados en **Mi perfil**.', 'Reportes', roles=('admin',), page='Reportes', keywords=('descargar', 'excel', 'pdf', 'reporte')),
    HelpTopic('¿Cómo personalizar los datos de mi negocio?', 'Abre **Mi perfil**, completa identidad, contacto, ubicación y textos de tickets. Puedes cargar logotipo y color de marca. Pulsa **Guardar** para aplicar los cambios en el sistema y los documentos.', 'Configuración', roles=('admin',), page='Mi perfil', keywords=('logo', 'negocio', 'perfil', 'personalizar')),
    HelpTopic('¿Cómo crear y compartir mi catálogo?', 'Abre **Mi página web** y completa los tres pasos: configuración, productos y vista previa. Selecciona qué artículos serán públicos, agrega fotografías y activa **Publicar catálogo**. Después comparte el enlace o descarga el código QR. El costo, proveedor y stock exacto nunca se muestran.', 'Configuración', roles=('admin',), page='Mi página web', keywords=('pagina web', 'catalogo', 'qr', 'publicar', 'whatsapp')),
    HelpTopic('¿Qué diferencia hay entre venta normal y venta express?', 'La **venta normal** usa productos existentes y descuenta inventario. **Venta express** sirve para un artículo ocasional que no está en el catálogo; después puedes decidir si conviene incorporarlo al inventario.', 'Ventas', roles=('seller',), page='Venta express', keywords=('rapida', 'fuera de inventario', 'express')),
)

STOP_WORDS = frozenset(('a', 'al', 'como', 'de', 'el', 'en', 'es', 'la', 'las',
                        'lo', 'los', 'mi', 'o', 'para', 'por', 'que', 'se', 'un',
                        'una', 'y'))


def normalize(text):
    text = unicodedata.normalize('NFKD', str(text).lower())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def topics_for_role(role):
    normalized_role = 'admin' if role == 'admin' else 'seller'
    return tuple(topic for topic in TOPICS if normalized_role in topic.roles)


def find_answer(query, role):
    """Devuelve el tema más probable o None cuando la confianza es baja."""
    normalized_query = normalize(query)
    if not normalized_query:
        return None
    query_tokens = set(normalized_query.split()) - STOP_WORDS
    best_topic, best_score = None, 0.0
    for topic in topics_for_role(role):
        searchable = normalize(' '.join((topic.question, topic.category, *topic.keywords)))
        searchable_tokens = set(searchable.split()) - STOP_WORDS
        overlap = len(query_tokens & searchable_tokens) / max(1, len(query_tokens))
        phrase_bonus = 0.25 if normalized_query in searchable else 0.0
        similarity = SequenceMatcher(None, normalized_query, normalize(topic.question)).ratio()
        # Una similitud casual entre frases no basta: debe compartir vocabulario
        # operativo o ser prácticamente la misma pregunta.
        if overlap == 0 and similarity < 0.72:
            continue
        score = overlap * 0.65 + similarity * 0.35 + phrase_bonus
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic if best_score >= 0.34 else None
