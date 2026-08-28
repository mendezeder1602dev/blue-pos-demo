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
    HelpTopic('¿Cómo registrar un producto en inventario?', 'Abre **Inventario**, completa todos los campos obligatorios y pulsa el botón de guardar. Puntos ECCOS valida nombres y códigos de barras repetidos para evitar duplicados. No uses Enter para intentar guardar el formulario.', 'Inventario', roles=('admin',), page='Inventario', keywords=('alta', 'codigo de barras', 'duplicado', 'inventario')),
    HelpTopic('¿Cómo importar mi inventario desde Excel?', '1. Abre **Inventario** y despliega **Importar inventario desde Excel**.\n2. Descarga la plantilla de Puntos ECCOS.\n3. Completa nombre, descripción, precio de costo, precio de venta, cantidad disponible y categoría. Código de barras y proveedor son opcionales.\n4. Conserva los encabezados y guarda el archivo como `.xlsx`. Formatea los códigos de barras como texto para no perder ceros iniciales.\n5. Carga el archivo y revisa la tabla editable: puedes corregir celdas o eliminar filas.\n6. Para productos existentes elige **sumar existencias**, **reemplazar existencias** u **omitir**.\n7. Confirma la revisión y pulsa **Importar productos al inventario**.\n\nPuntos ECCOS valida hasta 2,000 productos, evita duplicados y no guarda ninguna fila si encuentra un error.', 'Inventario', roles=('admin',), page='Inventario', keywords=('excel', 'plantilla', 'importar', 'migrar', 'stock', 'carga masiva')),
    HelpTopic('¿Cómo editar o eliminar un producto?', 'Abre **Inventario** y despliega **Editar o dar de baja un producto**. Selecciona el artículo para corregir sus datos o confirma **Eliminar del inventario**. La baja lo oculta de ventas y del catálogo, pero conserva tickets y movimientos anteriores para proteger la auditoría.', 'Inventario', roles=('admin',), page='Inventario', keywords=('editar', 'eliminar', 'baja', 'archivar', 'producto')),
    HelpTopic('¿Qué significan las alertas de inventario?', 'Una alerta **sin stock** indica cero unidades; **por agotarse** indica existencias iguales o menores al mínimo configurado. Revisa esos artículos antes de comprar mercancía o prometer una venta.', 'Inventario', page='Inventario', keywords=('alerta', 'agotado', 'existencias', 'stock')),
    HelpTopic('¿Cómo registrar mercancía comprada?', 'Abre **Entradas y mermas**, entra en **Entradas** y selecciona el producto recibido. Captura unidades, costo de compra, fecha, folio y observaciones. Revisa la existencia resultante y pulsa **Registrar entrada**. Si eliges actualizar el costo promedio, Puntos ECCOS pondera el costo anterior con la nueva compra sin modificar ventas pasadas.', 'Inventario', roles=('admin',), page='Movimientos', keywords=('entrada', 'compra', 'recibir', 'mercancia', 'reabastecer', 'proveedor', 'costo promedio')),
    HelpTopic('¿Cómo registrar una merma?', 'Abre **Entradas y mermas** y selecciona **Mermas**. Elige el producto, las unidades y el motivo; agrega una explicación y confirma el descuento. Puntos ECCOS no permite descontar más unidades de las disponibles y conserva responsable, fecha, existencia anterior y existencia final en el Kardex.', 'Inventario', roles=('admin',), page='Movimientos', keywords=('merma', 'dano', 'caducidad', 'robo', 'perdida', 'descontar')),
    HelpTopic('¿Cómo abrir la caja?', 'Antes de vender abre **Apertura de caja**, captura las denominaciones mexicanas, comprueba el fondo y asigna al responsable. Después de cerrar puedes abrir otro turno el mismo día; cada turno conserva su propio conteo y auditoría. El fondo no es una venta ni una ganancia.', 'Caja', page='Apertura de caja', keywords=('fondo', 'cambio', 'billetes', 'monedas', 'abrir caja', 'turno')),
    HelpTopic('¿Cómo hacer el corte o cierre de caja?', 'Abre **Cierre de caja**, cuenta físicamente billetes y monedas y compara el efectivo contado contra lo esperado desde la apertura del turno activo. Al confirmar termina únicamente ese turno; después el administrador puede abrir otro turno durante el mismo día.', 'Caja', page='Corte de caja', keywords=('arqueo', 'cierre', 'diferencia', 'corte', 'turno')),
    HelpTopic('¿Cómo registrar un retiro de efectivo?', 'Los retiros deben ser autorizados y registrados por el administrador, indicando importe y motivo. El retiro reduce el efectivo esperado en caja, pero no debe contabilizarse como una venta.', 'Caja', roles=('admin',), page='Corte de caja', keywords=('sacar dinero', 'retiro', 'efectivo')),
    HelpTopic('¿Cómo registrar, editar o eliminar un gasto?', 'En **Gastos**, captura concepto, importe y demás datos requeridos y guarda con el botón correspondiente. El administrador puede revisar el listado y editar o eliminar registros; conviene conservar el motivo para auditoría.', 'Administración', roles=('admin',), page='Gastos', keywords=('egreso', 'eliminar gasto', 'editar gasto', 'gasto')),
    HelpTopic('¿Cómo descargar reportes en PDF o Excel?', 'Abre **Reportes**, elige periodo y fecha, revisa el resumen y utiliza el botón de descarga PDF o Excel. Los documentos toman la identidad y datos guardados en **Mi perfil**.', 'Reportes', roles=('admin',), page='Reportes', keywords=('descargar', 'excel', 'pdf', 'reporte')),
    HelpTopic('¿Cómo personalizar los datos de mi negocio?', 'Abre **Mi perfil**, completa identidad, contacto, ubicación y textos de tickets. Puedes cargar logotipo y color de marca. Pulsa **Guardar** para aplicar los cambios en el sistema y los documentos.', 'Configuración', roles=('admin',), page='Mi perfil', keywords=('logo', 'negocio', 'perfil', 'personalizar')),
    HelpTopic('¿Cómo crear y compartir mi catálogo?', 'Abre **Mi página web** y completa los tres pasos: configuración, productos y vista previa. Selecciona qué artículos serán públicos, agrega fotografías y activa **Publicar catálogo**. Después comparte el enlace o descarga el código QR. El costo, proveedor y stock exacto nunca se muestran.', 'Configuración', roles=('admin',), page='Mi página web', keywords=('pagina web', 'catalogo', 'qr', 'publicar', 'whatsapp')),
    HelpTopic('¿Qué diferencia hay entre venta normal y venta express?', 'La **venta normal** usa productos existentes y descuenta inventario. **Venta express** sirve para un artículo ocasional que no está en el catálogo; después puedes decidir si conviene incorporarlo al inventario.', 'Ventas', roles=('seller',), page='Venta express', keywords=('rapida', 'fuera de inventario', 'express')),
    HelpTopic(
        '¿Cuál es la diferencia entre Solo cobrar y Cobrar e imprimir?',
        '**Solo cobrar** registra la venta, descuenta existencias y muestra una confirmación, pero no envía papel a la impresora. **Cobrar e imprimir** realiza exactamente el mismo cobro y además envía el ticket térmico a la impresora predeterminada. Si la impresión falla, la venta permanece guardada y puedes reimprimirla desde **Movimientos recientes**; no vuelvas a cobrarla.',
        'Ventas', page='Nueva venta',
        keywords=('solo cobrar', 'cobrar imprimir', 'confirmacion', 'movimientos recientes')),
    HelpTopic(
        '¿Cómo imprimo o reimprimo un ticket de 58 u 80 mm?',
        'Elige **58 mm** o **80 mm** antes de pulsar **Cobrar e imprimir**. El sistema ajusta el ancho, la altura y los márgenes al contenido real del ticket y utiliza la impresora predeterminada de Windows. Para otra copia, abre **Movimientos recientes**, selecciona el ancho y pulsa **Imprimir ahora**. También puedes descargar el PDF correspondiente. No fijes el tamaño Carta en el controlador de la impresora térmica.',
        'Impresión', page='Nueva venta',
        keywords=('ticket', 'imprimir', 'reimprimir', '58 mm', '80 mm', 'margen', 'papel', 'predeterminada')),
    HelpTopic(
        '¿Qué hago si la impresora repite tickets o deja mucho papel en blanco?',
        'Primero cancela el trabajo repetido en la cola de Windows. Si no responde, reinicia la **Cola de impresión (Spooler)** como administrador y elimina únicamente los trabajos pendientes. Después confirma en **Preferencias de impresión** que el papel sea térmico de 58 u 80 mm, sin tamaño Carta ni escalado adicional. Finalmente reimprime una sola vez desde **Movimientos recientes**.',
        'Impresión', page='Nueva venta',
        keywords=('spooler', 'cola', 'repite', 'papel blanco', 'margen largo', 'no para')),
    HelpTopic(
        '¿Cómo se realiza una devolución parcial?',
        'En **Devoluciones**, selecciona el ticket original. El sistema agrupa los artículos iguales y muestra la cantidad todavía disponible para devolver. Marca únicamente los productos correspondientes y ajusta sus cantidades; el resto de la venta se conserva. Indica condición, destino y motivo, revisa el importe y confirma **Autorizar devolución**.',
        'Devoluciones', roles=('admin',), page='Devoluciones',
        keywords=('devolucion parcial', 'producto repetido', 'cantidad', 'ticket original')),
    HelpTopic(
        '¿Qué destino elijo para un producto devuelto?',
        'Usa **Reintegrar a inventario** sólo cuando el artículo esté completo, funcional y apto para venderse otra vez. Usa **Enviar a revisión o merma** cuando esté dañado, incompleto o exista duda sobre su estado; no vuelve al inventario vendible. La selección queda registrada para auditoría y evita aumentar existencias por error.',
        'Devoluciones', roles=('admin',), page='Devoluciones',
        keywords=('buen estado', 'danado', 'merma', 'reintegrar', 'destino', 'revision')),
    HelpTopic(
        '¿Cómo cambio un producto por otro?',
        'Selecciona el ticket y las unidades a devolver, elige **Reemplazar producto** y selecciona el artículo que se entregará. El valor total del reemplazo debe coincidir con el valor autorizado de la devolución. El sistema registra la entrada o destino del artículo recibido y descuenta del inventario el artículo entregado, dejando ambos movimientos relacionados en la auditoría.',
        'Devoluciones', roles=('admin',), page='Devoluciones',
        keywords=('cambio', 'reemplazo', 'equipo', 'sustituir', 'entregar otro')),
    HelpTopic(
        '¿Cómo emitir un vale por una devolución?',
        'En **Devoluciones**, revisa productos, cantidades y condición; después elige **Entregar vale**. Al autorizar, el sistema crea un código único con el importe aprobado, lo registra en el historial y envía el comprobante a la impresora térmica predeterminada. El vale no representa efectivo retirado de caja y nunca debe crearse manualmente fuera de la devolución.',
        'Vales', roles=('admin',), page='Devoluciones',
        keywords=('emitir vale', 'nota de credito', 'saldo a favor', 'devolucion')),
    HelpTopic(
        '¿Cómo cobro una compra utilizando un vale?',
        'En **Nueva venta** o **Venta express**, selecciona **Vale** y escanea o captura su código. El sistema valida que esté activo y muestra su saldo. Si la compra supera el saldo, elige el complemento: **efectivo, tarjeta o transferencia**, y completa los datos solicitados. Un vale agotado o inexistente no puede utilizarse.',
        'Vales', page='Nueva venta',
        keywords=('pagar vale', 'cobrar vale', 'vale con efectivo', 'vale con tarjeta',
                  'vale con transferencia', 'codigo', 'escanear', 'combinado')),
    HelpTopic(
        '¿Qué ocurre si la compra cuesta menos que el saldo del vale?',
        'El código utilizado queda agotado y el sistema genera automáticamente **un vale nuevo por el remanente**. Ese nuevo código se imprime incluso cuando seleccionaste **Solo cobrar**, porque reemplaza al vale anterior. Entrégalo al cliente y verifica que el aviso muestre el nuevo importe; nunca escribas un saldo manual sobre el vale usado.',
        'Vales', page='Nueva venta',
        keywords=('remanente', 'sobrante', 'compra menor', 'saldo', 'nuevo vale', 'cambio')),
    HelpTopic(
        '¿Qué hago si el cliente perdió su vale?',
        'Busca el vale en **Historial de vales** por código, cliente o folio original. Verifica estado y saldo antes de reimprimir. **Reimprimir el mismo vale** conserva el mismo código y no duplica dinero. No generes otro vale para sustituirlo: si el original sigue activo, ambos papeles representarían el mismo saldo y sólo el código registrado será válido.',
        'Vales', roles=('admin',), page='Devoluciones',
        keywords=('vale perdido', 'historial', 'reimprimir', 'duplicado', 'saldo')),
    HelpTopic(
        '¿Dónde consulto los vales pendientes y cobrados?',
        'Abre **Historial de vales** desde **Nueva venta** o **Devoluciones**. Filtra por **Por cobrar** para ver códigos activos y su saldo; usa **Cobrados** para consultar los agotados. La búsqueda acepta código, cliente o folio original. Reimprimir no cambia el saldo y consumir un vale actualiza su estado automáticamente.',
        'Vales', page='Nueva venta',
        keywords=('historial vales', 'pendientes', 'cobrados', 'activos', 'agotados')),
    HelpTopic(
        '¿Cómo afectan los vales al corte de caja?',
        'El importe pagado con vale se registra como medio no efectivo y **no aumenta el dinero esperado en el cajón**. Si hubo complemento en efectivo, sólo esa parte suma al efectivo; tarjeta y transferencia aparecen en sus propios totales. El vale emitido por devolución tampoco es una salida física de efectivo. Cuenta únicamente billetes y monedas reales al cerrar.',
        'Caja', page='Corte de caja',
        keywords=('vale corte', 'cuadrar caja', 'efectivo esperado', 'metodo de pago', 'arqueo')),
    HelpTopic(
        '¿Qué hago cuando el efectivo supera el límite recomendado?',
        'Pulsa el botón **Ir a retiro de seguridad** que aparece en la alerta. Sólo administración puede autorizarlo. Captura el importe realmente retirado y el motivo; el sistema comprueba que no exceda el efectivo disponible, descuenta el retiro del efectivo esperado y conserva responsable, turno y fecha para el corte. Guarda físicamente el dinero según el protocolo del negocio.',
        'Caja', roles=('admin',), page='Apertura de caja',
        keywords=('limite caja', 'retiro seguridad', 'exceso efectivo', 'boton retiro')),
    HelpTopic(
        '¿Puede el vendedor autorizar devoluciones o retiros?',
        'No. El vendedor puede cobrar, consultar inventario y realizar su operación de turno, pero las devoluciones, reposiciones, emisión inicial de vales y retiros de seguridad requieren el perfil **Administrador**. Si necesitas una de esas operaciones, conserva el ticket o folio y solicita la autorización sin compartir la contraseña administrativa.',
        'Seguridad', roles=('seller',),
        keywords=('permiso vendedor', 'autorizar', 'administrador', 'devolucion', 'retiro')),
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
        keyword_bonus = 0.0
        for keyword in topic.keywords:
            normalized_keyword = normalize(keyword)
            if (len(normalized_keyword.split()) >= 2
                    and normalized_keyword in normalized_query):
                keyword_bonus = 0.22
                break
        similarity = SequenceMatcher(None, normalized_query, normalize(topic.question)).ratio()
        # Una similitud casual entre frases no basta: debe compartir vocabulario
        # operativo o ser prácticamente la misma pregunta.
        if overlap == 0 and similarity < 0.72:
            continue
        score = overlap * 0.65 + similarity * 0.35 + phrase_bonus + keyword_bonus
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic if best_score >= 0.34 else None
