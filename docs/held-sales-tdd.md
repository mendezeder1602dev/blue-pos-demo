# Evidencia TDD: ventas en espera por caja

Origen: recorridos derivados de la solicitud de corregir compras guardadas.

| Garantía | Prueba | Resultado |
| --- | --- | --- |
| Una espera conserva precio y cantidad, y queda ligada a su caja. | `test_hold_sale_preserves_quantity_and_negotiated_price` | PASS |
| Otra caja no puede consultar ni eliminar una espera ajena. | `test_held_sales_cannot_be_viewed_or_deleted_from_another_cash_register` | PASS |
| Una base de datos previa recibe las columnas y asigna sus esperas a Caja principal. | `test_assigns_legacy_held_sales_to_the_main_cash_register` | PASS |
| Al cobrar una espera recuperada se eliminan su referencia, carrito, precios y widgets. | `test_completed_sale_cleanup_is_idempotent_and_removes_restored_wait` | PASS |
| El siguiente rerun limpia nuevamente antes de renderizar el carrito. | `test_sales_page_repeats_cleanup_before_rendering_cart_widgets` | PASS |
| El POS vive en una sola superficie reemplazable que se vacía antes del rerun posterior al cobro. | `test_sales_page_uses_one_replaceable_screen_and_clears_it_after_charge` | PASS |

RED: `python -m unittest tests.model.repository.test_operations_repository` falló porque `hold_sale` no aceptaba `register_id`.

GREEN: la misma prueba pasó con 9 pruebas. También se verificó la compilación de los módulos cambiados con `python -m py_compile`.

Regresión de finalización: ventas en espera, repositorios, flujo de venta y humo de Streamlit terminaron con **56 pruebas aprobadas**.

Cobertura pendiente: una prueba de navegador que complete un cobro real con impresora simulada. La persistencia, el aislamiento y las transiciones de estado quedan cubiertos por repositorio y contratos de interfaz.
