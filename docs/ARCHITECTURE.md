# Guía técnica de Puntos ECCOS

Esta guía explica cómo recorrer el proyecto sin conocer previamente el código. La
aplicación es un punto de venta web construido con Streamlit y SQLAlchemy.

## Recorrido recomendado

1. Empieza en `web/app.py`. Ahí viven la interfaz, la navegación y la coordinación
   de cada caso de uso.
2. Revisa `model/entity/models.py` para conocer las tablas y relaciones.
3. Busca el repositorio correspondiente en `model/repository/` para entender las
   lecturas, validaciones y transacciones.
4. Consulta `model/schema.py` para ver cómo se crea y migra una base existente.
5. Ejecuta `python runtests.py` antes y después de modificar reglas de negocio.

## Capas y responsabilidades

```text
Navegador
   │
   ▼
web/app.py                 Interfaz, formularios, estado y navegación
   │
   ▼
model/repository/          Reglas operativas y persistencia transaccional
   │
   ▼
model/entity/models.py     Entidades y esquema SQLAlchemy
   │
   ▼
SQLite / base configurada  Información operativa del negocio
```

Los archivos `model/report/` generan tickets, PDF y Excel. `model/inventory_excel.py`
valida importaciones masivas. `model/authorization.py` protege operaciones exclusivas
del administrador aunque alguien intente invocarlas fuera de la interfaz.

## Ciclo de una ejecución Streamlit

Streamlit vuelve a ejecutar `web/app.py` ante una interacción. `main()` decide entre
el catálogo público, el acceso o la aplicación autenticada. `_render_app()` recupera
el perfil, construye la barra lateral y ejecuta únicamente la función de la página
seleccionada en `ADMIN_PAGES` o `SELLER_PAGES`.

El carrito, página activa, mensajes pendientes y usuario viven en
`st.session_state`; nunca deben guardarse como variables globales de módulo.

## Acceso y permisos

- El administrador se autentica con usuario y contraseña.
- El vendedor conserva el acceso rápido actual, sin contraseña.
- Ocultar un botón no es una autorización. Las operaciones sensibles vuelven a
  validar el rol mediante `require_role('superuser')` dentro del repositorio.
- La base de credenciales está separada de la base operativa.

## Datos y transacciones

`RepositoryFactory` entrega repositorios que comparten una sesión SQLAlchemy aislada
por hilo. Una operación de escritura valida, modifica y confirma con `commit()` como
una unidad. Si se agregan nuevas escrituras masivas, deben usar una única transacción
y hacer `rollback()` ante cualquier error.

No se deben eliminar ventas, gastos o productos con historial si se pierde la
evidencia. Los flujos normales usan estados, bajas lógicas, devoluciones y auditoría.

## Inventario

- `Product.quantity` representa la existencia disponible.
- Una venta reduce existencias dentro de la misma transacción.
- Entradas, mermas y ajustes generan un `StockMovement` (Kardex).
- Los productos temporales de venta exprés no forman parte del inventario normal.
- Nombre y código de barras se validan para evitar duplicados.

## Ventas y folios

Una venta comercial puede contener varias líneas `Sale`. Todas comparten
`transaction_id`; por eso deben contarse como un ticket, no como varias operaciones.
El folio visible se construye con `_sale_folio()`. El identificador interno sigue
existiendo para relaciones y auditoría, pero no se presenta al cliente.

## Caja

La apertura registra el fondo inicial. Las ventas en efectivo, gastos que afectan
caja, entradas autorizadas y retiros forman el efectivo esperado. El cierre compara
ese resultado con el conteo físico por denominaciones mexicanas. La diferencia de
caja se reporta separada de la utilidad comercial.

## Ganancias

```text
Ventas brutas = total cobrado
Utilidad bruta = ventas brutas - costo de mercancía vendida
Utilidad neta  = utilidad bruta - gastos operativos
```

Un sobrante o faltante de caja no se mezcla con la utilidad neta.

## Caché y rendimiento

- Los PDF y Excel se generan de forma diferida al pulsar Descargar.
- El resultado se conserva en una caché acotada durante diez minutos.
- No se cachean el carrito, las credenciales, la apertura ni la existencia usada al
  confirmar una venta.
- Estadísticas agrupa información en SQL; no se debe volver al patrón de consultar
  cada día en un ciclo.
- Las pestañas costosas deben renderizar únicamente su contenido visible.

## Convenciones para cambios nuevos

- Los textos visibles se escriben en español claro y en pesos mexicanos.
- Los formularios de captura usan `enter_to_submit=False`.
- Toda acción importante deja una notificación y, si es sensible, una auditoría.
- La interfaz no contiene reglas críticas que no estén también en el repositorio.
- Las consultas que pueden crecer deben filtrar, agrupar o paginar en SQL.
- Nunca se guardan secretos, números completos de tarjeta ni CVV.
- Los comentarios deben explicar el motivo o la regla, no repetir literalmente el
  nombre de la instrucción.

## Verificación local

```powershell
.\.venv\Scripts\python.exe runtests.py
.\.venv\Scripts\streamlit.exe run web\app.py
```

Comprueba los perfiles Administrador y Vendedor después de cambiar navegación,
permisos, inventario, ventas o caja.
