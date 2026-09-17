# Puntos ECCOS

**Puntos ECCOS** es un sistema web comercial de punto de venta para pequeños y
medianos negocios. Fue creado y desarrollado en Tabasco, México, por
**Grupo ECCOS**. Centraliza ventas, inventario, caja, gastos,
clientes, abastecimiento, reportes, estadísticas y catálogo comercial desde el
navegador.

El proyecto funciona exclusivamente como aplicación web con Streamlit. Es
software propietario y no se distribuye gratuitamente. La
interfaz de escritorio basada en PyQt fue retirada y ya no forma parte del
producto.

## Funciones principales

- Venta normal y venta exprés con ticket.
- Inventario, entradas, mermas, ajustes y alertas de existencias.
- Importación de inventario desde Excel y exportación a Excel/PDF.
- Apertura y cierre de caja en pesos mexicanos.
- Gastos, clientes, proveedores y abastecimiento sugerido.
- Cotizaciones, reportes, estadísticas y auditoría.
- Catálogo web configurable con los datos del negocio.
- Perfiles de administrador y vendedor.
- Centro de notificaciones e incidencias con responsables, prioridad y seguimiento.
- Crédito a clientes, puntos de lealtad y métricas de desempeño de vendedores.
- Precios de mayoreo, descuentos autorizados y ventas en espera.
- Órdenes de compra con recepción, actualización de costos y Kardex.
- Copias de seguridad automáticas, descarga y restauración validada de SQLite.

Todas estas funciones trabajan de forma local y no requieren APIs ni servicios de
pago. Las copias automáticas se guardan junto a la base de datos, en `backups/`.

## Ejecutar localmente en Windows

Requiere Python 3.11 o superior.

```powershell
cd "C:\Users\HP\Desktop\blue-pos-master"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run web\app.py
```

Después abre `http://localhost:8501` en el navegador.

Las credenciales y códigos privados deben configurarse mediante variables de
entorno o secretos de Streamlit; no deben guardarse en el repositorio.

## Salida a producción

Antes de operar con ventas reales:

1. Copia [`.env.example`](.env.example) a `.env` en el servidor y configura
   contraseñas largas que no se reutilicen.
2. Configura `BLUE_POS_DATABASE_URL` con PostgreSQL administrado. SQLite queda
   reservado para uso local de una sola caja.
3. Inicia la aplicación una vez para aplicar y registrar las migraciones en
   `schema_migrations`; conserva una copia de la base antes de actualizar.
4. Realiza y verifica una restauración de respaldo antes del primer día de venta.
5. Simula apertura, venta, devolución, retiro y corte con la impresora y lector
   de códigos reales.

No actives `BLUE_POS_DEMO_RESET` en producción.

## Ejecutar pruebas

```powershell
.\.venv\Scripts\python.exe runtests.py
```

## Documentación para desarrolladores

La arquitectura, el ciclo de Streamlit, las reglas de inventario, ventas, caja,
permisos y caché están explicados en
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Es el punto de entrada recomendado
para cualquier persona que vaya a mantener el sistema.

## Publicación

Las instrucciones de Streamlit Community Cloud están en
[`DEPLOYMENT.md`](DEPLOYMENT.md). El archivo principal de la aplicación es
`web/app.py`.

## Autoría y contacto

Creado y desarrollado en Tabasco, México, por **Grupo ECCOS**.

Contacto: [mendezeder@gmail.com](mailto:mendezeder@gmail.com)

© 2026 Grupo ECCOS. Todos los derechos reservados.

Condiciones de uso: consulta [`LICENSE`](LICENSE).
