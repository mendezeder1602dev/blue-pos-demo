# Evidencia TDD: sin descuento automático por mayoreo

Origen: solicitud de impedir descuentos automáticos por cantidad en ventas.

| Garantía | Prueba | Resultado |
| --- | --- | --- |
| Aumentar la cantidad no activa el precio de mayoreo. | `test_quantity_never_applies_the_wholesale_price_automatically` | PASS |
| Un precio explícito o recuperado de una espera se conserva. | `test_explicit_and_restored_prices_are_preserved` | PASS |

RED: la prueba falló inicialmente porque la regla independiente de precios aún no existía y el carrito contenía una sustitución automática por mayoreo.

GREEN: `python -m unittest tests.model.test_sales_pricing` pasó 2 pruebas. La prueba de humo de la interfaz pasó 23 pruebas.
