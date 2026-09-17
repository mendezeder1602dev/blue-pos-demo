# Detalle y PDF de ventas · evidencia TDD

## Fuente y recorridos de usuario

No se utilizó un plan externo. Los recorridos se derivaron de la solicitud:

- Como usuario del POS, quiero abrir el detalle de una venta sin imprimir el ticket.
- Como usuario del POS, quiero descargar un PDF A4 independiente del ticket térmico.
- Como administrador o vendedor, quiero ver la hora exacta de cada operación de hoy.

## Informe de tareas

| Comportamiento | Ejecución | Validación | Garantía |
|---|---|---|---|
| Agrupar las filas por operación | Se agregó `build_sale_detail`, que conserva productos, cantidades, precios unitarios y total. | `python -m pytest tests/model/test_sales_history.py -q` | Una venta con varias unidades se muestra como un solo folio y precios distintos no se promedian. |
| Mostrar fecha y hora | El historial y el tablero del vendedor usan `created_at` con formato `dd/mm/aaaa` y `HH:mm:ss`. | `python -m pytest tests/test_sales_history_ui_contract.py -q` | Cada operación visible incluye su hora exacta; el acceso "Ventas de hoy" abre el filtro de hoy. |
| Consultar sin imprimir | Se agregó un diálogo de sólo lectura con productos, pago, cliente, responsable y caja. | `python -m pytest tests/test_sales_history_ui_contract.py -q` | El detalle se abre con "Ver detalle" y no invoca la impresora. |
| Descargar PDF independiente | El diálogo genera un reporte A4 diferido mediante el exportador general. | `python -m pytest tests/model/test_sales_history.py -q` | El archivo comienza con `%PDF-`, contiene metadatos, productos y totales, y no usa el flujo térmico. |

## Evidencia RED y GREEN

- RED inicial: `ModuleNotFoundError: No module named 'model.sales_history'` al ejecutar las pruebas nuevas.
- RED del filtro de hoy: faltaban `callback_args=('Hoy',)` y el filtro por `sale.date == mexico_today()`.
- GREEN focalizado: `9 passed in 0.76s`.
- Regresión de ventas y Streamlit: `33 passed in 28.41s`.
- Suite completa: `268 passed, 4 subtests passed in 156.49s`.
- Compilación: `python -m py_compile model/sales_history.py web/app.py` terminó con código 0.
- Aplicación local: `http://localhost:8501/_stcore/health` respondió `ok`.

## Especificación de pruebas

| # | Garantía | Prueba | Tipo | Resultado |
|---|---|---|---|---|
| 1 | Agrupa unidades iguales y conserva la hora exacta | `test_build_sale_detail_groups_lines_and_keeps_exact_sale_time` | Unit | PASS |
| 2 | No mezcla precios unitarios distintos | `test_build_sale_detail_does_not_merge_different_unit_prices` | Unit | PASS |
| 3 | El PDF incluye folio, fecha, hora, pago, cliente, responsable, caja y total | `test_sale_detail_pdf_sections_include_operation_metadata_and_totals` | Unit | PASS |
| 4 | Una operación vacía se rechaza de forma explícita | `test_build_sale_detail_rejects_an_empty_operation` | Unit | PASS |
| 5 | Las secciones producen un PDF real | `test_sale_detail_sections_generate_an_independent_a4_pdf` | Integration | PASS |
| 6 | La interfaz expone detalle, PDF, hora y filtro de hoy | `tests/test_sales_history_ui_contract.py` | UI contract | PASS |

## Cobertura, brechas y evidencia de integración

El entorno no tiene instalado `pytest-cov`, por lo que el comando de cobertura fue rechazado
por pytest y no se reporta un porcentaje inventado. Las ramas del nuevo helper están cubiertas
por pruebas unitarias, la creación del PDF por una prueba de integración y el arranque general
por la suite de Streamlit. Queda como comprobación manual opcional abrir un folio real y revisar
visualmente el archivo con los datos particulares del negocio.

No se crearon commits de checkpoint porque el árbol ya contenía cambios del usuario y no se
solicitó crear commits. La evidencia RED/GREEN se conserva en este documento.
